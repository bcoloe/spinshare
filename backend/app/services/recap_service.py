"""Weekly recap service — computes, persists, and serves per-group weekly recaps.

A recap is a frozen snapshot of one group's activity over a completed Mon–Sun
week (in the group's timezone). It is generated once and stored as an immutable
JSON blob so later views never change. See ``app/schemas/recap.py`` for the
payload shape and the plan in ``plans/`` for the design rationale.
"""

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.services.group_service as gs
from app.models import (
    Album,
    Group,
    GroupAlbum,
    GroupRecap,
    NominationGuess,
    RecapView,
    Review,
    User,
)
from app.schemas.recap import (
    GuessAccuracy,
    LeaderboardEntry,
    MemberGuessAccuracy,
    RecapAlbumCard,
    RecapData,
    RecapResponse,
    RecapSummary,
)
from app.services.user_service import UserService
from app.utils.time_helpers import DEFAULT_TZ, completed_week_bounds, week_bounds_for

# Smoothing threshold for the Bayesian weighted score, matching explore_service so
# "favorite/least favorite weighted by number of reviews" is consistent app-wide.
_BAYESIAN_MIN_VOTES = 3
_PRIOR_MEAN = 5.0  # neutral fallback when a group has no rating history yet


class RecapService:
    def __init__(self, db: Session):
        self.db = db

    # ==================== GENERATION (write path) ====================

    def generate_due(self, group_id: int) -> GroupRecap | None:
        """Generate the recap for the most recently completed week if it's missing.

        Idempotent and safe to run repeatedly (e.g. hourly cron). Returns the
        recap (existing or newly created) or ``None`` for groups that never get a
        recap (global, bot, or dealer-mode groups).
        """
        group = self.db.query(Group).filter(Group.id == group_id).first()
        if group is None or not self._recap_eligible(group):
            return None

        tz_name = (group.settings.timezone if group.settings else None) or DEFAULT_TZ
        week_start, _ = completed_week_bounds(tz_name)

        existing = self._get_recap_row(group_id, week_start)
        if existing is not None:
            return existing
        return self.generate_for_group(group_id, week_start)

    def generate_for_group(self, group_id: int, week_start: date, *, force: bool = False) -> GroupRecap:
        """Compute and persist the recap for ``group_id`` covering the week that
        begins on ``week_start`` (a group-tz Monday).

        Idempotent: returns the existing row for the week unless ``force`` is set,
        in which case the existing snapshot is deleted and recomputed (dev/test).
        """
        group = self.db.query(Group).filter(Group.id == group_id).first()
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        if not self._recap_eligible(group):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Weekly recaps are not generated for global, bot, or dealer-mode groups",
            )

        existing = self._get_recap_row(group_id, week_start)
        if existing is not None:
            if not force:
                return existing
            self.db.delete(existing)
            self.db.flush()

        tz_name = (group.settings.timezone if group.settings else None) or DEFAULT_TZ
        week_end = week_start + timedelta(days=7)
        start, end = week_bounds_for(week_start, tz_name)
        member_ids = [m.id for m in group.members]

        data = RecapData(
            albums_added=self._albums_added(group_id, start, end),
            albums_reviewed=self._albums_reviewed(group_id, member_ids, start, end),
            favorite_album=None,
            least_favorite_album=None,
            guess_accuracy=self._guess_accuracy(group_id, start, end),
        )
        favorite, least_favorite = self._favorite_albums(group_id, member_ids, start, end)
        data.favorite_album = favorite
        data.least_favorite_album = least_favorite

        recap = GroupRecap(
            group_id=group_id,
            week_start=week_start,
            week_end=week_end,
            data=data.model_dump(),
        )
        self.db.add(recap)
        self.db.commit()
        self.db.refresh(recap)
        return recap

    # ---- section computations ----

    def _albums_added(self, group_id: int, start, end) -> list[LeaderboardEntry]:
        """Nominations added to the pool during the week, ranked by member."""
        rows = (
            self.db.query(User.username, func.count(GroupAlbum.id).label("n"))
            .join(User, User.id == GroupAlbum.added_by)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.added_at >= start,
                GroupAlbum.added_at < end,
            )
            .group_by(User.username)
            .order_by(func.count(GroupAlbum.id).desc(), User.username)
            .all()
        )
        return [LeaderboardEntry(username=u, count=n) for u, n in rows]

    def _albums_reviewed(self, group_id: int, member_ids: list[int], start, end) -> list[LeaderboardEntry]:
        """Non-draft reviews of this group's albums during the week, ranked by member."""
        if not member_ids:
            return []
        group_album_ids = self.db.query(GroupAlbum.album_id).filter(GroupAlbum.group_id == group_id)
        rows = (
            self.db.query(User.username, func.count(Review.id).label("n"))
            .join(User, User.id == Review.user_id)
            .filter(
                Review.is_draft.is_(False),
                Review.user_id.in_(member_ids),
                Review.album_id.in_(group_album_ids),
                Review.reviewed_at >= start,
                Review.reviewed_at < end,
            )
            .group_by(User.username)
            .order_by(func.count(Review.id).desc(), User.username)
            .all()
        )
        return [LeaderboardEntry(username=u, count=n) for u, n in rows]

    def _favorite_albums(
        self, group_id: int, member_ids: list[int], start, end
    ) -> tuple[RecapAlbumCard | None, RecapAlbumCard | None]:
        """Highest / lowest Bayesian-weighted albums among those drawn this week.

        Only albums with at least one non-draft member review qualify. Least
        favorite is omitted unless at least two distinct albums qualify (so a
        lone reviewed album isn't shown as both best and worst).
        """
        drawn_album_ids = [
            row[0]
            for row in (
                self.db.query(GroupAlbum.album_id)
                .filter(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.selected_date >= start,
                    GroupAlbum.selected_date < end,
                )
                .distinct()
                .all()
            )
        ]
        if not drawn_album_ids or not member_ids:
            return None, None

        stats = {
            album_id: (int(count), float(avg))
            for album_id, count, avg in (
                self.db.query(
                    Review.album_id,
                    func.count(Review.id),
                    func.avg(Review.rating),
                )
                .filter(
                    Review.album_id.in_(drawn_album_ids),
                    Review.is_draft.is_(False),
                    Review.user_id.in_(member_ids),
                    Review.rating.isnot(None),
                )
                .group_by(Review.album_id)
                .all()
            )
        }
        if not stats:
            return None, None

        # Prior mean: this group's overall member rating average (fallback neutral).
        group_avg = (
            self.db.query(func.avg(Review.rating))
            .join(GroupAlbum, GroupAlbum.album_id == Review.album_id)
            .filter(
                GroupAlbum.group_id == group_id,
                Review.is_draft.is_(False),
                Review.user_id.in_(member_ids),
                Review.rating.isnot(None),
            )
            .scalar()
        )
        prior = float(group_avg) if group_avg is not None else _PRIOR_MEAN

        albums = {a.id: a for a in self.db.query(Album).filter(Album.id.in_(stats.keys())).all()}
        cards: list[RecapAlbumCard] = []
        for album_id, (count, avg) in stats.items():
            album = albums.get(album_id)
            if album is None:
                continue
            weighted = (count * avg + _BAYESIAN_MIN_VOTES * prior) / (count + _BAYESIAN_MIN_VOTES)
            cards.append(
                RecapAlbumCard(
                    album_id=album_id,
                    spotify_album_id=album.spotify_album_id,
                    title=album.title,
                    artist=album.artist,
                    cover_url=album.cover_url,
                    avg_rating=round(avg, 2),
                    review_count=count,
                    weighted_score=round(weighted, 4),
                )
            )

        if not cards:
            return None, None
        cards.sort(key=lambda c: c.weighted_score, reverse=True)
        favorite = cards[0]
        least_favorite = cards[-1] if len(cards) >= 2 else None
        return favorite, least_favorite

    def _guess_accuracy(self, group_id: int, start, end) -> GuessAccuracy:
        """Nomination-guessing accuracy for guesses submitted during the week."""
        correct_case = case((NominationGuess.correct.is_(True), 1), else_=0)

        # Group totals in a single aggregate round-trip.
        total, correct = (
            self.db.query(
                func.count(NominationGuess.id),
                func.coalesce(func.sum(correct_case), 0),
            )
            .join(GroupAlbum, GroupAlbum.id == NominationGuess.group_album_id)
            .filter(
                GroupAlbum.group_id == group_id,
                NominationGuess.created_at >= start,
                NominationGuess.created_at < end,
            )
            .one()
        )
        total, correct = int(total), int(correct)

        member_rows = (
            self.db.query(User.username, func.count(NominationGuess.id), func.coalesce(func.sum(correct_case), 0))
            .join(GroupAlbum, GroupAlbum.id == NominationGuess.group_album_id)
            .join(User, User.id == NominationGuess.guessing_user_id)
            .filter(
                GroupAlbum.group_id == group_id,
                NominationGuess.created_at >= start,
                NominationGuess.created_at < end,
            )
            .group_by(User.username)
            .order_by(func.count(NominationGuess.id).desc(), User.username)
            .all()
        )
        per_member = [
            MemberGuessAccuracy(
                username=u,
                total=int(t),
                correct=int(c),
                pct=round(100.0 * int(c) / int(t), 1) if t else 0.0,
            )
            for u, t, c in member_rows
        ]
        return GuessAccuracy(
            total_guesses=total,
            correct_guesses=correct,
            pct=round(100.0 * correct / total, 1) if total else 0.0,
            per_member=per_member,
        )

    # ==================== READ PATH ====================

    def list_for_group(self, group_id: int, user: User) -> list[RecapResponse]:
        """All recaps for a group, newest first. Requires membership."""
        self._require_membership(user, group_id)
        recaps = (
            self.db.query(GroupRecap)
            .filter(GroupRecap.group_id == group_id)
            .order_by(GroupRecap.week_start.desc())
            .all()
        )
        seen_ids = self._seen_recap_ids(user.id, [r.id for r in recaps])
        return [self._to_response(r, r.id in seen_ids) for r in recaps]

    def get_recap(self, group_id: int, recap_id: int, user: User) -> RecapResponse:
        """A single recap. Requires membership."""
        self._require_membership(user, group_id)
        recap = self._get_recap_or_404(group_id, recap_id)
        seen = bool(self._seen_recap_ids(user.id, [recap.id]))
        return self._to_response(recap, seen)

    def latest_for_group(self, group_id: int, user: User) -> RecapResponse | None:
        """The most recent recap for a group, or None. Requires membership."""
        self._require_membership(user, group_id)
        recap = (
            self.db.query(GroupRecap)
            .filter(GroupRecap.group_id == group_id)
            .order_by(GroupRecap.week_start.desc())
            .first()
        )
        if recap is None:
            return None
        seen = bool(self._seen_recap_ids(user.id, [recap.id]))
        return self._to_response(recap, seen)

    def mark_seen(self, group_id: int, recap_id: int, user: User) -> None:
        """Record that the user has seen a recap (idempotent). Requires membership."""
        self._require_membership(user, group_id)
        recap = self._get_recap_or_404(group_id, recap_id)
        if self._seen_recap_ids(user.id, [recap.id]):
            return
        self.db.add(RecapView(recap_id=recap.id, user_id=user.id))
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()  # concurrent insert — already seen

    def pending_for_user(self, user: User) -> list[RecapSummary]:
        """Latest unseen recap per group for the login pop-up.

        Runs on every page load, so it uses a constant number of queries
        regardless of how many groups the user belongs to: one to fetch the
        latest recap per group, one to check which of those are already seen.
        """
        groups = UserService(self.db).get_user_groups(user.id)
        name_by_id = {g.id: g.name for g in groups}
        if not name_by_id:
            return []

        # Latest recap (by week_start) for each of the user's groups, in one query.
        latest_week = (
            self.db.query(
                GroupRecap.group_id,
                func.max(GroupRecap.week_start).label("ws"),
            )
            .filter(GroupRecap.group_id.in_(name_by_id.keys()))
            .group_by(GroupRecap.group_id)
            .subquery()
        )
        latest_recaps = (
            self.db.query(GroupRecap)
            .join(
                latest_week,
                and_(
                    GroupRecap.group_id == latest_week.c.group_id,
                    GroupRecap.week_start == latest_week.c.ws,
                ),
            )
            .order_by(GroupRecap.week_start.desc())
            .all()
        )
        if not latest_recaps:
            return []

        # A group is pending only if its *latest* recap is unseen (an older unseen
        # recap must not resurface once the newest has been acknowledged).
        seen = self._seen_recap_ids(user.id, [r.id for r in latest_recaps])
        return [
            RecapSummary(
                id=r.id,
                group_id=r.group_id,
                group_name=name_by_id[r.group_id],
                week_start=r.week_start,
                week_end=r.week_end,
            )
            for r in latest_recaps
            if r.id not in seen
        ]

    # ==================== HELPERS ====================

    def _to_response(self, recap: GroupRecap, seen: bool) -> RecapResponse:
        return RecapResponse(
            id=recap.id,
            group_id=recap.group_id,
            week_start=recap.week_start,
            week_end=recap.week_end,
            generated_at=recap.generated_at,
            data=RecapData(**recap.data),
            seen=seen,
        )

    def _get_recap_row(self, group_id: int, week_start: date) -> GroupRecap | None:
        return (
            self.db.query(GroupRecap)
            .filter(GroupRecap.group_id == group_id, GroupRecap.week_start == week_start)
            .first()
        )

    def _get_recap_or_404(self, group_id: int, recap_id: int) -> GroupRecap:
        recap = (
            self.db.query(GroupRecap)
            .filter(GroupRecap.id == recap_id, GroupRecap.group_id == group_id)
            .first()
        )
        if recap is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recap not found")
        return recap

    def _seen_recap_ids(self, user_id: int, recap_ids: list[int]) -> set[int]:
        if not recap_ids:
            return set()
        rows = (
            self.db.query(RecapView.recap_id)
            .filter(RecapView.user_id == user_id, RecapView.recap_id.in_(recap_ids))
            .all()
        )
        return {rid for (rid,) in rows}

    def _require_membership(self, user: User, group_id: int) -> None:
        gs.GroupService(self.db).require_membership(user.id, group_id)

    @staticmethod
    def _recap_eligible(group: Group) -> bool:
        """Weekly recaps are only produced for regular member groups.

        Global groups, bot-sourced groups, and dealer-mode groups don't have the
        shared weekly cadence a recap summarizes, so they're excluded.
        """
        if group.is_global or bool(group.bot_sources):
            return False
        if group.settings is not None and group.settings.dealer_mode:
            return False
        return True
