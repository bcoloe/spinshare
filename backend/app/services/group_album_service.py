"""GroupAlbum workflow service: daily selection, guessing, and instant nomination reveal.

Selection lifecycle (driven by cron, not admin action):
  - selected_date IS NULL  → available for future selection
  - selected_date IS NOT NULL → selected on that date (historical / today's spin)

Guess lifecycle (per-user, instant feedback):
  - Member submits guess → immediately receives correct/incorrect + nominator identity
"""

import random
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Album, Group, GroupAlbum, GroupSettings, NominationGuess, User
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


_CHAOS_PROBABILITY = 0.10
_DEFAULT_TIMEZONE = "America/New_York"


def _group_today(tz_name: str) -> date:
    """Return the current date in the given IANA timezone."""
    return datetime.now(tz=ZoneInfo(tz_name)).date()


def _date_in_tz(col, tz_name: str):
    """SQLAlchemy expression: extract date from a UTC timestamptz column in the given timezone."""
    return func.date(func.timezone(tz_name, col))


class GroupAlbumService:
    """Workflow service for the nomination → daily-selection → guess lifecycle."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== DAILY SELECTION (cron-driven) ====================

    def select_daily_albums(self, group_id: int, n: int = 1) -> list[GroupAlbum]:
        """Randomly select N unselected albums as today's daily spins for a group.

        Idempotent: if albums were already selected today, returns the existing selection
        without adding more. Safe to call multiple times on the same day (e.g. cron retry).

        For the global group, samples from all nominations across every non-global group.
        For regular groups, operates on distinct pending nominations within the group.
        If the group has chaos_mode enabled, each slot has a 20% chance of being filled
        from the global album pool (any album not already in the group) instead of from
        group nominations.

        If fewer than N albums are available (but at least 1), selects all available and
        notifies group members that the pool is exhausted.

        Raises:
            HTTPException 409: If no eligible distinct albums are available.
        """
        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        tz_name = settings.timezone if settings else _DEFAULT_TIMEZONE
        today = _group_today(tz_name)
        existing = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                _date_in_tz(GroupAlbum.selected_date, tz_name) == today,
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
            return self._select_global_daily_albums(group_id, n)

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
            return self._select_normal_albums(group_id, group, available_album_ids, n)
        return self._select_with_chaos(group_id, group, available_album_ids, n)

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

        tz_name = settings.timezone
        today = _group_today(tz_name)
        existing = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                _date_in_tz(GroupAlbum.selected_date, tz_name) == today,
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
            return canonical

        n = settings.daily_album_count

        if force_chaos:
            if not settings.chaos_mode:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chaos mode is not enabled for this group",
                )
            group = self.db.query(Group).filter(Group.id == group_id).first()
            return self._select_full_chaos(group_id, group, n)

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

        return self.select_daily_albums(group_id, n=n)

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

    def get_todays_albums(self, group_id: int, user: User) -> list[GroupAlbum]:
        """Return albums selected as today's daily spins for a group. Requires membership.

        When an album has multiple nominations they are all selected together;
        this returns one canonical GroupAlbum (earliest nomination) per album.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        tz_name = settings.timezone if settings else _DEFAULT_TIMEZONE
        today = _group_today(tz_name)
        all_today = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                _date_in_tz(GroupAlbum.selected_date, tz_name) == today,
            )
            .order_by(GroupAlbum.id)
            .all()
        )

        # Deduplicate by album_id, keeping the canonical (lowest id) row
        seen: set[int] = set()
        canonical = []
        for ga in all_today:
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
        - Album must have been selected (selected_date IS NOT NULL).
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
        if group_album.selected_date is None:
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
        )

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

        return GuessOptionsResponse(
            options=[
                GuessOptionUser(user_id=u.id, username=u.username, display_name=u.display_name)
                for u in pool
            ],
            has_chaos_option=settings.chaos_mode if settings else False,
        )

    # ==================== NOMINATION POOL ====================

    def get_pending_nomination_count(self, group_id: int, user: User) -> int:
        """Return the number of distinct albums available for future selection.

        For regular groups: distinct unselected nominations within the group.
        For the global group: distinct albums nominated in any non-global group
        that have not yet been spun globally.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

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

        today = date.today()
        return (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.added_by == user.id,
                func.date(GroupAlbum.added_at) == today,
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
