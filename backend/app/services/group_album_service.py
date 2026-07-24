"""GroupAlbum workflow service: daily selection, guessing, and instant nomination reveal.

Selection lifecycle (driven by cron, not admin action):
  - selected_date IS NULL  → available for future selection
  - selected_date IS NOT NULL → selected on that date (historical / today's spin)

Guess lifecycle (per-user, instant feedback):
  - Member submits guess → immediately receives correct/incorrect + nominator identity
"""

import random
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Album, AlbumDeal, Group, GroupAlbum, GroupSettings, NominationGuess, Review, User
from app.models.group import group_members
from app.schemas.group_album import (
    CheckGuessResponse,
    GuessOptionUser,
    GuessOptionsResponse,
    NominationGuessCreate,
    NominationGuessResponse,
)
from app.schemas.notification import NotificationType
from app.services import group_service as gs
from app.services.notification_service import NotificationService
from app.utils.time_helpers import (
    DEFAULT_TZ,
    date_in_tz,
    group_today,
    most_recent_scheduled_date,
    utc_today_range,
)

_CHAOS_PROBABILITY = 0.10


class GroupAlbumService:
    """Workflow service for the nomination → daily-selection → guess lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== DAILY SELECTION (cron-driven) ====================

    def select_daily_albums(
        self, group_id: int, n: int = 1, *, bypass_schedule: bool = False
    ) -> list[GroupAlbum]:
        """Randomly select N unselected albums as today's daily spins for a group.

        Idempotent: if albums were already selected today (in the group's timezone), returns
        the existing selection without adding more. Safe to call multiple times (e.g. hourly cron).

        Respects the group's ``selection_days`` schedule: if today (in the group's timezone) is
        not a scheduled day, returns [] immediately without selecting. Pass
        ``bypass_schedule=True`` to override (used by manual triggers).

        For the global group, samples from all nominations across every non-global group.
        For regular groups, operates on distinct pending nominations within the group.
        If the group has chaos_mode enabled, each slot has a 10% chance of being filled
        from the global album pool (any album not already in the group) instead of from
        group nominations.

        If fewer than N albums are available (but at least 1), selects all available and
        notifies group members that the pool is exhausted.

        Raises:
            HTTPException 409: If no eligible distinct albums are available.
        """
        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()

        # Dealer groups have no shared daily selection — members roll individually
        if settings is not None and settings.dealer_mode:
            return []

        tz_name = (settings.timezone if settings else None) or DEFAULT_TZ

        today = group_today(tz_name)

        # Skip selection on unscheduled days (cron path only; manual triggers bypass this)
        if not bypass_schedule and settings is not None:
            weekday = today.isoweekday() - 1  # isoweekday: 1=Mon…7=Sun → 0=Mon…6=Sun
            if weekday not in settings.selection_days:
                return []

        existing = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                date_in_tz(GroupAlbum.selected_date, tz_name) == today,
            )
            .order_by(GroupAlbum.id)
            .all()
        )
        if existing:
            seen: set[int] = set()
            canonical: list[GroupAlbum] = []
            for ga in existing:
                if ga.album_id not in seen:
                    seen.add(ga.album_id)
                    canonical.append(ga)
            return canonical

        group = self.db.query(Group).filter(Group.id == group_id).first()
        if group and group.is_global:
            selected = self._select_global_daily_albums(group_id, n)
            self._heal_genres(selected)
            return selected

        chaos_mode = settings.chaos_mode if settings else False

        available_album_ids = [
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.is_(None))
            .distinct()
            .all()
        ]
        if len(available_album_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No unselected albums available",
            )

        if not chaos_mode:
            selected = self._select_normal_albums(group_id, group, available_album_ids, n)
        else:
            selected = self._select_with_chaos(group_id, group, available_album_ids, n)
        self._heal_genres(selected)
        return selected

    def _select_normal_albums(
        self, group_id: int, group: Group | None, available_album_ids: list[int], n: int
    ) -> list[GroupAlbum]:
        pool_short = len(available_album_ids) < n
        actual_n = len(available_album_ids) if pool_short else n
        chosen_album_ids = random.sample(available_album_ids, actual_n)
        now = datetime.now(tz=timezone.utc)

        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id.in_(chosen_album_ids),
                GroupAlbum.selected_date.is_(None),
            )
            .all()
        )
        for ga in all_nominations:
            ga.selected_date = now

        self.db.commit()

        canonical: dict[int, GroupAlbum] = {}
        for ga in all_nominations:
            self.db.refresh(ga)
            if ga.album_id not in canonical or ga.id < canonical[ga.album_id].id:
                canonical[ga.album_id] = ga

        if pool_short and group:
            self._notify_pool_exhausted(group_id, group.name, actual_n, n)

        return list(canonical.values())

    def _select_with_chaos(
        self, group_id: int, group: Group | None, available_album_ids: list[int], n: int
    ) -> list[GroupAlbum]:
        """Selection variant for chaos-mode groups.

        Each of the N slots independently has a CHAOS_PROBABILITY chance of being
        filled from the global album pool (albums not yet in this group) rather than
        from the group's pending nominations.
        """
        chaos_count = sum(1 for _ in range(n) if random.random() < _CHAOS_PROBABILITY)
        normal_count = n - chaos_count

        # Albums not yet associated with this group at all (pending or selected)
        all_group_album_ids = {
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id)
            .distinct()
            .all()
        }
        chaos_pool_ids = [
            row[0]
            for row in self.db.query(Album.id)
            .filter(Album.id.notin_(all_group_album_ids))
            .all()
        ] if all_group_album_ids else [row[0] for row in self.db.query(Album.id).all()]

        # If fewer chaos albums exist than slots, convert excess to normal
        actual_chaos = min(chaos_count, len(chaos_pool_ids))
        actual_normal = normal_count + (chaos_count - actual_chaos)

        # Cap normal picks to what's available
        pool_short = len(available_album_ids) < actual_normal
        actual_normal = min(actual_normal, len(available_album_ids))

        now = datetime.now(tz=timezone.utc)
        result: list[GroupAlbum] = []

        # Fill normal slots from group nominations
        if actual_normal > 0:
            chosen_normal_ids = random.sample(available_album_ids, actual_normal)
            all_nominations = (
                self.db.query(GroupAlbum)
                .filter(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.album_id.in_(chosen_normal_ids),
                    GroupAlbum.selected_date.is_(None),
                )
                .all()
            )
            for ga in all_nominations:
                ga.selected_date = now
            canonical: dict[int, GroupAlbum] = {}
            for ga in all_nominations:
                if ga.album_id not in canonical or ga.id < canonical[ga.album_id].id:
                    canonical[ga.album_id] = ga
            result.extend(canonical.values())

        # Fill chaos slots from the global pool
        if actual_chaos > 0:
            chosen_chaos_ids = random.sample(chaos_pool_ids, actual_chaos)
            for album_id in chosen_chaos_ids:
                chaos_ga = GroupAlbum(
                    group_id=group_id,
                    album_id=album_id,
                    added_by=None,
                    selected_date=now,
                    is_chaos_selection=True,
                )
                self.db.add(chaos_ga)
                result.append(chaos_ga)

        self.db.commit()
        for ga in result:
            self.db.refresh(ga)

        if pool_short and group:
            self._notify_pool_exhausted(group_id, group.name, actual_normal, n)

        return result

    def _select_global_daily_albums(self, global_group_id: int, n: int) -> list[GroupAlbum]:
        """Select N albums for the global group by sampling across all non-global-group nominations.

        Albums already spun in the global group are excluded. Creates a GroupAlbum record in the
        global group for each chosen album, attributed to the original nominator.
        """
        already_spun = {
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == global_group_id)
            .distinct()
            .all()
        }

        q = (
            self.db.query(GroupAlbum.album_id)
            .join(Group, GroupAlbum.group_id == Group.id)
            .filter(Group.is_global == False)  # noqa: E712
            .distinct()
        )
        if already_spun:
            q = q.filter(GroupAlbum.album_id.notin_(already_spun))

        available_album_ids = [row[0] for row in q.all()]

        if len(available_album_ids) < n:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Not enough unselected albums: need {n}, have {len(available_album_ids)}",
            )

        chosen_album_ids = random.sample(available_album_ids, n)
        now = datetime.now(tz=timezone.utc)

        result = []
        for album_id in chosen_album_ids:
            original = (
                self.db.query(GroupAlbum)
                .join(Group, GroupAlbum.group_id == Group.id)
                .filter(GroupAlbum.album_id == album_id, Group.is_global == False)  # noqa: E712
                .order_by(GroupAlbum.id)
                .first()
            )
            ga = GroupAlbum(
                group_id=global_group_id,
                album_id=album_id,
                added_by=original.added_by if original else None,
                selected_date=now,
            )
            self.db.add(ga)
            result.append(ga)

        self.db.commit()
        for ga in result:
            self.db.refresh(ga)
        return result

    def _heal_genres(self, group_albums: list[GroupAlbum]) -> None:
        """Attempt to backfill genres for any selected album that has none.

        Runs synchronously during selection so albums surfaced to users already have
        genres populated. Errors are swallowed per album so a single failure does not
        block the selection.
        """
        from app.services.album_service import AlbumService

        album_svc = AlbumService(self.db)
        for ga in group_albums:
            album = ga.albums
            if album and not album.genres:
                album_svc.backfill_genres(album.id, album.title, album.artist)

    def trigger_daily_selection(
        self, group_id: int, user: User, force_chaos: bool = False
    ) -> list[GroupAlbum]:
        """Trigger random daily album selection if none have been chosen today.

        Idempotent — returns existing selections if today's albums are already chosen.
        Race-condition safe: acquires a row-level lock on group_settings to serialize
        concurrent calls from multiple members clicking simultaneously.
        Any group member may trigger selection (not restricted to admins).

        When chaos_mode is enabled and the nomination pool is empty:
        - force_chaos=False raises 409 with detail "no_nominations_chaos_available" so
          the caller can prompt the user before proceeding.
        - force_chaos=True fills all slots from the global album pool (FULL CHAOS MODE).

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 409: If not enough unselected albums are available.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = (
            self.db.query(GroupSettings)
            .filter(GroupSettings.group_id == group_id)
            .with_for_update()
            .first()
        )
        if settings is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Group settings not found",
            )
        if settings.dealer_mode:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="dealer_mode_enabled",
            )

        tz_name = (settings.timezone if settings else None) or DEFAULT_TZ
        today = group_today(tz_name)
        existing = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                date_in_tz(GroupAlbum.selected_date, tz_name) == today,
            )
            .order_by(GroupAlbum.id)
            .all()
        )
        if existing:
            seen: set[int] = set()
            canonical = []
            for ga in existing:
                if ga.album_id not in seen:
                    seen.add(ga.album_id)
                    canonical.append(ga)
            self._heal_genres(canonical)
            return canonical

        n = settings.daily_album_count

        if force_chaos:
            if not settings.chaos_mode:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chaos mode is not enabled for this group",
                )
            group = self.db.query(Group).filter(Group.id == group_id).first()
            selected = self._select_full_chaos(group_id, group, n)
            self._heal_genres(selected)
            return selected

        if settings.chaos_mode:
            pool_empty = not (
                self.db.query(GroupAlbum.album_id)
                .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.is_(None))
                .limit(1)
                .first()
            )
            if pool_empty:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="no_nominations_chaos_available",
                )

        return self.select_daily_albums(group_id, n=n, bypass_schedule=True)

    def _select_full_chaos(self, group_id: int, group: Group | None, n: int) -> list[GroupAlbum]:
        """Fill all N daily slots from the global album pool (FULL CHAOS MODE).

        Picks albums not yet associated with this group in any way.

        Raises:
            HTTPException 409: If no global albums are available.
        """
        all_group_album_ids = {
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id)
            .distinct()
            .all()
        }
        chaos_pool_ids = [
            row[0]
            for row in self.db.query(Album.id)
            .filter(Album.id.notin_(all_group_album_ids))
            .all()
        ] if all_group_album_ids else [row[0] for row in self.db.query(Album.id).all()]

        if not chaos_pool_ids:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No albums available for chaos selection",
            )

        actual_n = min(n, len(chaos_pool_ids))
        chosen_ids = random.sample(chaos_pool_ids, actual_n)
        now = datetime.now(tz=timezone.utc)

        result = []
        for album_id in chosen_ids:
            chaos_ga = GroupAlbum(
                group_id=group_id,
                album_id=album_id,
                added_by=None,
                selected_date=now,
                is_chaos_selection=True,
            )
            self.db.add(chaos_ga)
            result.append(chaos_ga)

        self.db.commit()
        for ga in result:
            self.db.refresh(ga)

        if actual_n < n and group:
            self._notify_pool_exhausted(group_id, group.name, actual_n, n)

        return result

    def get_catchup_albums(self, group_id: int, user: User, limit: int = 10) -> list[GroupAlbum]:
        """Return up to `limit` most-recently-selected albums the user has not submitted a review for.

        Albums with in-progress (draft) reviews are included. Excludes albums that were selected
        on the most recent draw date (today's spin).
        Requires catch_up_enabled on the group's settings. Returns [] immediately when
        catch_up_enabled is False.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        if settings is None or not settings.catch_up_enabled or settings.dealer_mode:
            return []

        tz_name = (settings.timezone if settings else None) or DEFAULT_TZ
        today = group_today(tz_name)

        # Subquery: album_ids the user has submitted (non-draft) reviews for
        reviewed_subq = (
            self.db.query(Review.album_id)
            .filter(Review.user_id == user.id, Review.is_draft == False)  # noqa: E712
            .subquery()
        )

        # One canonical GroupAlbum row per album_id (lowest id), most recently selected first,
        # excluding today and albums the user has already submitted a review for.
        canonical_id_subq = (
            self.db.query(func.min(GroupAlbum.id))
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.selected_date.isnot(None),
                date_in_tz(GroupAlbum.selected_date, tz_name) != today,
                GroupAlbum.album_id.notin_(reviewed_subq),
            )
            .group_by(GroupAlbum.album_id)
            .order_by(func.max(GroupAlbum.selected_date).desc())
            .limit(limit)
            .subquery()
        )

        results = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.id.in_(canonical_id_subq))
            .options(
                selectinload(GroupAlbum.albums).selectinload(Album.genres),
                selectinload(GroupAlbum.albums).selectinload(Album.reviews),
            )
            .order_by(GroupAlbum.selected_date.desc(), GroupAlbum.id)
            .all()
        )

        return results

    def get_todays_albums(self, group_id: int, user: User) -> list[GroupAlbum]:
        """Return albums from the most recent scheduled draw for a group. Requires membership.

        On non-draw days, falls back to the previous scheduled draw's albums so members
        always see the current spin until the next draw replaces it. Returns [] only when
        the most recent scheduled draw ran but found nothing (pool exhausted) or no draws
        have ever occurred.

        When an album has multiple nominations they are all selected together;
        this returns one canonical GroupAlbum (earliest nomination) per album.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        tz_name = (settings.timezone if settings else None) or DEFAULT_TZ
        today = group_today(tz_name)

        selection_days = list(settings.selection_days) if settings and settings.selection_days else list(range(7))

        # Most recent date with an actual draw (schedule-agnostic — handles post-schedule-change state)
        raw = (
            self.db.query(func.max(date_in_tz(GroupAlbum.selected_date, tz_name)))
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.isnot(None))
            .scalar()
        )
        most_recent_drawn = date.fromisoformat(raw) if isinstance(raw, str) else raw

        scheduled = most_recent_scheduled_date(today, selection_days)
        candidates = [d for d in [most_recent_drawn, scheduled] if d is not None]
        target_date = max(candidates) if candidates else today

        all_for_date = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                date_in_tz(GroupAlbum.selected_date, tz_name) == target_date,
            )
            .options(
                selectinload(GroupAlbum.albums).selectinload(Album.genres),
                selectinload(GroupAlbum.albums).selectinload(Album.reviews),
            )
            .order_by(GroupAlbum.id)
            .all()
        )

        # Deduplicate by album_id, keeping the canonical (lowest id) row
        seen: set[int] = set()
        canonical = []
        for ga in all_for_date:
            if ga.album_id not in seen:
                seen.add(ga.album_id)
                canonical.append(ga)
        return canonical

    # ==================== GUESSING ====================

    def check_guess(
        self, group_id: int, group_album_id: int, user: User, data: NominationGuessCreate
    ) -> CheckGuessResponse:
        """Submit a nomination guess and receive instant feedback.

        Rules:
        - Album must have been selected (selected_date IS NOT NULL) or dealt to the user.
        - User must be a group member.
        - User cannot guess themselves (for non-chaos guesses).
        - One guess per user per album (409 on duplicate).
        - guessed_user_id=None represents a "chaos" guess (outside-of-group pick).

        Returns the stored guess plus whether it was correct and the actual nominator.

        Raises:
            HTTPException 403: If user is not a member or guesses themselves.
            HTTPException 409: If album has not been selected or guess already submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        group_album = self._get_group_album_or_404(group_id, group_album_id)
        if group_album.selected_date is None and not self._user_has_revealed_deal(
            group_id, user.id, group_album.album_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guesses can only be submitted for albums that have been selected",
            )

        if data.guessed_user_id is not None and data.guessed_user_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot guess yourself as the nominator",
            )

        # Always collect nominations for instant nominator reveal on feedback
        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == group_album.album_id,
            )
            .all()
        )
        nominator_ids = {ga.added_by for ga in all_nominations if ga.added_by is not None}

        if data.guessed_user_id is None:
            # Chaos guess: correct only if this album was actually a chaos pick
            correct = group_album.is_chaos_selection
        else:
            # Guessing a specific user is never correct for a chaos album
            correct = not group_album.is_chaos_selection and data.guessed_user_id in nominator_ids

        guess = NominationGuess(
            group_album_id=group_album_id,
            guessing_user_id=user.id,
            guessed_user_id=data.guessed_user_id,
            correct=correct,
        )
        try:
            self.db.add(guess)
            self.db.flush()
        except IntegrityError as e:
            self.db.rollback()
            if "unique_guess_per_user_album" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You have already submitted a guess for this album",
                ) from None
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Guess could not be saved due to a constraint violation",
            ) from None

        self.db.commit()
        self.db.refresh(guess)

        nominators = [ga.added_by_user for ga in all_nominations if ga.added_by_user is not None]

        return CheckGuessResponse(
            guess=NominationGuessResponse.model_validate(guess),
            correct=correct,
            nominator_user_ids=[n.id for n in nominators],
            nominator_usernames=[n.username for n in nominators],
            is_chaos_selection=group_album.is_chaos_selection,
            guessed_username=guess.guessed_user.username if guess.guessed_user_id is not None else None,
        )

    def get_my_guess(self, group_id: int, group_album_id: int, user: User) -> CheckGuessResponse:
        """Get the current user's prior guess for a group album, including nominator details.

        Returns the same shape as check_guess so callers always get nominator context.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If no guess has been submitted.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)
        group_album = self._get_group_album_or_404(group_id, group_album_id)
        guess = self._get_guess(group_album_id, user.id, raise_on_missing=True)

        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == group_album.album_id,
            )
            .all()
        )
        nominators = [ga.added_by_user for ga in all_nominations if ga.added_by_user is not None]

        return CheckGuessResponse(
            guess=NominationGuessResponse.model_validate(guess),
            correct=guess.correct,
            nominator_user_ids=[n.id for n in nominators],
            nominator_usernames=[n.username for n in nominators],
            is_chaos_selection=group_album.is_chaos_selection,
            guessed_username=guess.guessed_user.username if guess.guessed_user_id is not None else None,
        )

    def get_my_guesses_for_group(self, group_id: int, user_id: int) -> list[CheckGuessResponse]:
        """Return all of the current user's guesses for albums in a group.

        Each response includes the same nominator-reveal context as check_guess.
        Uses 3 queries regardless of group size (no N+1).
        """
        group_albums = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.group_id == group_id)
            .all()
        )
        if not group_albums:
            return []

        ga_ids = [ga.id for ga in group_albums]
        ga_by_id = {ga.id: ga for ga in group_albums}

        guesses = (
            self.db.query(NominationGuess)
            .filter(
                NominationGuess.group_album_id.in_(ga_ids),
                NominationGuess.guessing_user_id == user_id,
            )
            .all()
        )
        if not guesses:
            return []

        nominator_ids = {ga.added_by for ga in group_albums if ga.added_by is not None}
        guessed_user_ids = {g.guessed_user_id for g in guesses if g.guessed_user_id is not None}
        all_user_ids = nominator_ids | guessed_user_ids
        user_map = {
            u.id: u
            for u in self.db.query(User).filter(User.id.in_(all_user_ids)).all()
        } if all_user_ids else {}
        nominator_map = {uid: user_map[uid] for uid in nominator_ids if uid in user_map}

        album_nominators: dict[int, list[User]] = {}
        for ga in group_albums:
            nominators = album_nominators.setdefault(ga.album_id, [])
            if ga.added_by and ga.added_by in nominator_map:
                nominators.append(nominator_map[ga.added_by])

        results = []
        for guess in guesses:
            ga = ga_by_id[guess.group_album_id]
            nominators = album_nominators.get(ga.album_id, [])
            guessed_username = user_map[guess.guessed_user_id].username if guess.guessed_user_id and guess.guessed_user_id in user_map else None
            results.append(CheckGuessResponse(
                guess=NominationGuessResponse.model_validate(guess),
                correct=guess.correct,
                nominator_user_ids=[n.id for n in nominators],
                nominator_usernames=[n.username for n in nominators],
                is_chaos_selection=ga.is_chaos_selection,
                guessed_username=guessed_username,
            ))
        return results

    def get_guess_options(self, group_id: int, group_album_id: int, user: User) -> GuessOptionsResponse:
        """Return a deterministic, capped pool of users to present as guessing candidates.

        The pool always contains at least one nominator when one exists. Remaining slots
        are filled from other group members sorted by user_id, so every member sees the
        same choices for a given album (idempotent across callers).

        Pool size is bounded by the group's ``guess_user_cap`` setting (default 5).

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If the group album is not found.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        group = self.db.query(Group).filter(Group.id == group_id).first()
        group_album = self._get_group_album_or_404(group_id, group_album_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        cap = settings.guess_user_cap if settings else 5

        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == group_album.album_id,
            )
            .all()
        )
        nominator_ids = {ga.added_by for ga in all_nominations if ga.added_by is not None}

        # All group members sorted deterministically by user_id
        all_members = (
            self.db.query(User)
            .join(group_members, group_members.c.user_id == User.id)
            .filter(group_members.c.group_id == group_id)
            .order_by(User.id)
            .all()
        )

        # Nominators always appear first in the pool; fill the rest with non-nominators
        nominators = [u for u in all_members if u.id in nominator_ids]
        non_nominators = [u for u in all_members if u.id not in nominator_ids]

        pool = nominators[:cap]
        remaining = cap - len(pool)
        if remaining > 0:
            pool.extend(non_nominators[:remaining])

        is_global = group.is_global if group else False
        show_name_in_context = not is_global and not user.is_bot
        return GuessOptionsResponse(
            options=[
                GuessOptionUser(
                    user_id=u.id,
                    username=u.username,
                    first_name=u.first_name if (u.name_is_public or show_name_in_context) else None,
                    last_name=u.last_name if (u.name_is_public or show_name_in_context) else None,
                )
                for u in pool
            ],
            has_chaos_option=settings.chaos_mode if settings else False,
        )

    # ==================== NOMINATION POOL ====================

    def get_pending_nomination_count(self, group_id: int, user: User) -> int:
        """Return the number of distinct albums available for future selection.

        For regular groups: distinct unselected nominations within the group.
        For dealer groups: albums still dealable to the calling user.
        For the global group: distinct albums nominated in any non-global group
        that have not yet been spun globally.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        if settings is not None and settings.dealer_mode:
            from app.services.dealer_service import DealerService  # local import avoids circular dependency

            return DealerService(self.db).get_pool_count(group_id, user.id)

        group = self.db.query(Group).filter(Group.id == group_id).first()
        if group and group.is_global:
            already_spun = {
                row[0]
                for row in self.db.query(GroupAlbum.album_id)
                .filter(GroupAlbum.group_id == group_id)
                .distinct()
                .all()
            }
            q = (
                self.db.query(GroupAlbum.album_id)
                .join(Group, GroupAlbum.group_id == Group.id)
                .filter(Group.is_global == False)  # noqa: E712
                .distinct()
            )
            if already_spun:
                q = q.filter(GroupAlbum.album_id.notin_(already_spun))
            return q.count()

        return (
            self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.is_(None))
            .distinct()
            .count()
        )

    def get_today_nomination_count(self, group_id: int, user: User) -> int:
        """Return the number of albums the user has nominated in this group today.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        today_start, tomorrow_start = utc_today_range()
        return (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.added_by == user.id,
                GroupAlbum.added_at >= today_start,
                GroupAlbum.added_at < tomorrow_start,
            )
            .count()
        )

    # ==================== HELPERS ====================

    def _notify_pool_exhausted(
        self, group_id: int, group_name: str, selected: int, requested: int
    ) -> None:
        """Send a pool-low notification to every member of the group."""
        member_ids = list(
            self.db.scalars(
                select(group_members.c.user_id).where(
                    group_members.c.group_id == group_id
                )
            ).all()
        )
        message = (
            f"Today's spin for {group_name} could only pull {selected} of {requested} albums — "
            f"the nomination pool is now empty. Add more albums to keep the daily spin going!"
        )
        ns = NotificationService(self.db)
        for uid in member_ids:
            ns.create(
                user_id=uid,
                type=NotificationType.nomination_pool_low,
                message=message,
                group_id=group_id,
            )

    def _user_has_revealed_deal(self, group_id: int, user_id: int, album_id: int) -> bool:
        """Whether the album has been dealt (revealed) to this user in this group."""
        return (
            self.db.query(AlbumDeal.id)
            .filter(
                AlbumDeal.group_id == group_id,
                AlbumDeal.user_id == user_id,
                AlbumDeal.album_id == album_id,
                AlbumDeal.revealed_at.isnot(None),
            )
            .first()
            is not None
        )

    def _get_group_album_or_404(self, group_id: int, group_album_id: int) -> GroupAlbum:
        ga = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.id == group_album_id, GroupAlbum.group_id == group_id)
            .first()
        )
        if not ga:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group album {group_album_id} not found in group {group_id}",
            )
        return ga

    def _get_guess(
        self, group_album_id: int, user_id: int, *, raise_on_missing: bool = False
    ) -> NominationGuess | None:
        guess = (
            self.db.query(NominationGuess)
            .filter(
                NominationGuess.group_album_id == group_album_id,
                NominationGuess.guessing_user_id == user_id,
            )
            .first()
        )
        if not guess and raise_on_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No guess found for this album",
            )
        return guess
