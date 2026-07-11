"""Dealer-mode workflow service: per-member album rolls from the group backlog.

Deal lifecycle (per user, per group):
  - revealed_at IS NULL     → queued: pre-drawn as part of today's allotment, not yet shown
  - revealed_at IS NOT NULL → dealt: surfaced to the user; part of their personal history

The first roll of a user's day samples their entire remaining daily allotment in one
query and stores it as queued rows (the day's cache); each subsequent roll reveals the
next queued row without re-running the pool query.
"""

import random
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Album, AlbumDeal, GroupAlbum, GroupSettings, Review, User
from app.schemas.album import GroupAlbumResponse
from app.schemas.group_album import DealRollResponse, DealsTodayResponse
from app.services import group_service as gs
from app.utils.time_helpers import DEFAULT_TZ, date_in_tz, group_today


class DealerService:
    """Workflow service for per-member rolls in dealer-mode groups."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== ROLL ====================

    def roll(self, group_id: int, user: User) -> DealRollResponse:
        """Roll the dice: reveal the next album from the user's daily allotment.

        On the first roll of the user's day (in the group's timezone), samples the
        remaining allotment from the eligible pool in one query and caches it as
        queued deals; subsequent rolls reveal the next queued deal directly.

        Serialized per group via a row lock on group_settings (same pattern as
        trigger_daily_selection); the unique deal constraint backstops any race.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If group settings not found.
            HTTPException 409: If dealer mode is off ("dealer_mode_disabled"),
                the daily allotment is used up ("no_rolls_remaining"), or the
                pool is exhausted ("dealer_pool_empty").
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
        if not settings.dealer_mode:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="dealer_mode_disabled",
            )

        tz_name = settings.timezone or DEFAULT_TZ
        today = group_today(tz_name)

        # Unclaimed queue rows from previous days return to the pool
        self.db.query(AlbumDeal).filter(
            AlbumDeal.group_id == group_id,
            AlbumDeal.user_id == user.id,
            AlbumDeal.revealed_at.is_(None),
            date_in_tz(AlbumDeal.dealt_at, tz_name) != today,
        ).delete(synchronize_session="fetch")

        # Drop queued rows that became ineligible after they were drawn: albums
        # selected for the whole group (dealer mode was toggled off and a shared
        # draw ran) or since reviewed by the user. Revealing them would waste a
        # roll on an album that is already in the user's history.
        selected_subq = select(GroupAlbum.album_id).where(
            GroupAlbum.group_id == group_id, GroupAlbum.selected_date.isnot(None)
        )
        reviewed_subq = select(Review.album_id).where(
            Review.user_id == user.id, Review.is_draft == False  # noqa: E712
        )
        self.db.query(AlbumDeal).filter(
            AlbumDeal.group_id == group_id,
            AlbumDeal.user_id == user.id,
            AlbumDeal.revealed_at.is_(None),
            or_(
                AlbumDeal.album_id.in_(selected_subq),
                AlbumDeal.album_id.in_(reviewed_subq),
            ),
        ).delete(synchronize_session="fetch")

        rolls_used = self._rolls_used_today(group_id, user.id, tz_name, today)
        if rolls_used >= settings.dealer_rolls_per_day:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="no_rolls_remaining",
            )

        queued = (
            self.db.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == group_id,
                AlbumDeal.user_id == user.id,
                AlbumDeal.revealed_at.is_(None),
            )
            .order_by(AlbumDeal.id)
            .all()
        )
        if not queued:
            pool = self._eligible_album_ids(group_id, user.id)
            if not pool:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="dealer_pool_empty",
                )
            draw_n = min(settings.dealer_rolls_per_day - rolls_used, len(pool))
            queued = [
                AlbumDeal(group_id=group_id, user_id=user.id, album_id=album_id)
                for album_id in random.sample(pool, draw_n)
            ]
            self.db.add_all(queued)
            self.db.flush()
            queued.sort(key=lambda deal: deal.id)

        deal = queued[0]
        deal.revealed_at = datetime.now(tz=timezone.utc)
        self.db.commit()
        self.db.refresh(deal)

        canonical = self._canonical_group_albums(group_id, [deal.album_id])
        self._heal_genres(list(canonical.values()))

        return DealRollResponse(
            deal=self._deal_response(canonical[deal.album_id], deal),
            rolls_used_today=rolls_used + 1,
            rolls_per_day=settings.dealer_rolls_per_day,
            pool_remaining=self.get_pool_count(group_id, user.id),
        )

    # ==================== READS ====================

    def get_todays_deals(self, group_id: int, user: User) -> DealsTodayResponse:
        """Return the user's deals revealed today (group timezone) plus roll accounting.

        Returns an empty response (rolls_per_day=0) when dealer mode is off, mirroring
        how get_catchup_albums degrades when its feature toggle is disabled.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        settings = self.db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
        if settings is None or not settings.dealer_mode:
            return DealsTodayResponse(deals=[], rolls_used_today=0, rolls_per_day=0, pool_remaining=0)

        tz_name = settings.timezone or DEFAULT_TZ
        today = group_today(tz_name)

        deals = (
            self.db.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == group_id,
                AlbumDeal.user_id == user.id,
                AlbumDeal.revealed_at.isnot(None),
                date_in_tz(AlbumDeal.revealed_at, tz_name) == today,
            )
            .order_by(AlbumDeal.revealed_at, AlbumDeal.id)
            .all()
        )

        canonical = self._canonical_group_albums(group_id, [d.album_id for d in deals])
        return DealsTodayResponse(
            deals=[
                self._deal_response(canonical[d.album_id], d)
                for d in deals
                if d.album_id in canonical
            ],
            rolls_used_today=len(deals),
            rolls_per_day=settings.dealer_rolls_per_day,
            pool_remaining=self.get_pool_count(group_id, user.id),
        )

    def get_member_history(self, group_id: int, user: User) -> list[GroupAlbumResponse]:
        """Return the member's review history for a group.

        The history is the union of the group's shared selections and the caller's
        revealed deals — one canonical entry per album, newest first. In groups that
        were never in dealer mode the deal set is empty, so this matches the shared
        selected-album history exactly.

        Raises:
            HTTPException 403: If user is not a group member.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        selected_album_ids = {
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.selected_date.isnot(None))
            .distinct()
            .all()
        }
        deal_by_album = {
            deal.album_id: deal
            for deal in self.db.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == group_id,
                AlbumDeal.user_id == user.id,
                AlbumDeal.revealed_at.isnot(None),
            )
            .all()
        }

        canonical = self._canonical_group_albums(
            group_id, list(selected_album_ids | set(deal_by_album))
        )
        responses = [
            self._deal_response(ga, deal_by_album.get(album_id))
            for album_id, ga in canonical.items()
        ]
        responses.sort(key=lambda r: (r.dealt_at or r.selected_date or r.added_at), reverse=True)
        return responses

    def get_pool_count(self, group_id: int, user_id: int) -> int:
        """Return the number of albums still available for this user to draw.

        Queued (pre-drawn, unrevealed) albums count as available: they will be
        revealed by the user's next rolls, or purged back to the pool.
        """
        return len(self._eligible_album_ids(group_id, user_id, exclude_queued=False))

    # ==================== HELPERS ====================

    def _eligible_album_ids(
        self, group_id: int, user_id: int, *, exclude_queued: bool = True
    ) -> list[int]:
        """Distinct albums still dealable to this user: pending nominations in the
        group, minus albums already dealt to the user, minus albums the user has a
        published review for.

        With exclude_queued=True (the sampling pool), queued rows also exclude their
        album so a new draw can never duplicate the pre-drawn allotment. Pass
        exclude_queued=False for the user-facing availability count, where queued
        albums are still theirs to draw.
        """
        deal_filters = [AlbumDeal.group_id == group_id, AlbumDeal.user_id == user_id]
        if not exclude_queued:
            deal_filters.append(AlbumDeal.revealed_at.isnot(None))
        dealt_subq = select(AlbumDeal.album_id).where(*deal_filters)
        reviewed_subq = select(Review.album_id).where(
            Review.user_id == user_id, Review.is_draft == False  # noqa: E712
        )
        return [
            row[0]
            for row in self.db.query(GroupAlbum.album_id)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.selected_date.is_(None),
                GroupAlbum.album_id.notin_(dealt_subq),
                GroupAlbum.album_id.notin_(reviewed_subq),
            )
            .distinct()
            .all()
        ]

    def _rolls_used_today(self, group_id: int, user_id: int, tz_name: str, today) -> int:
        return (
            self.db.query(AlbumDeal)
            .filter(
                AlbumDeal.group_id == group_id,
                AlbumDeal.user_id == user_id,
                AlbumDeal.revealed_at.isnot(None),
                date_in_tz(AlbumDeal.revealed_at, tz_name) == today,
            )
            .count()
        )

    def _canonical_group_albums(self, group_id: int, album_ids: list[int]) -> dict[int, GroupAlbum]:
        """Return {album_id: canonical GroupAlbum} (lowest id per album) with the
        nomination_count / nominator_user_ids enrichment used by GroupAlbumResponse.

        Albums whose nomination rows were all removed are absent from the result;
        callers skip those deals (same degradation as deleted selected albums).
        """
        if not album_ids:
            return {}
        subq = (
            self.db.query(
                GroupAlbum.album_id.label("album_id"),
                func.min(GroupAlbum.id).label("canonical_id"),
                func.count(GroupAlbum.id).label("nomination_count"),
            )
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.album_id.in_(album_ids))
            .group_by(GroupAlbum.album_id)
            .subquery()
        )
        rows = (
            self.db.query(GroupAlbum, subq.c.nomination_count)
            .join(subq, GroupAlbum.id == subq.c.canonical_id)
            .options(
                selectinload(GroupAlbum.albums).selectinload(Album.genres),
                selectinload(GroupAlbum.albums).selectinload(Album.reviews),
            )
            .all()
        )

        raw = (
            self.db.query(GroupAlbum.album_id, GroupAlbum.added_by)
            .filter(GroupAlbum.group_id == group_id, GroupAlbum.album_id.in_(album_ids))
            .all()
        )
        nominators_by_album: dict[int, list[int]] = {}
        for album_id, added_by in raw:
            if added_by is not None:
                nominators_by_album.setdefault(album_id, []).append(added_by)

        result: dict[int, GroupAlbum] = {}
        for ga, count in rows:
            ga.nomination_count = count
            ga.nominator_user_ids = nominators_by_album.get(ga.album_id, [])
            result[ga.album_id] = ga
        return result

    def _deal_response(self, ga: GroupAlbum, deal: AlbumDeal | None) -> GroupAlbumResponse:
        response = GroupAlbumResponse.from_orm(ga)
        if deal is not None:
            response.dealt_at = deal.revealed_at
        return response

    def _heal_genres(self, group_albums: list[GroupAlbum]) -> None:
        """Backfill genres for dealt albums that have none (mirrors selection paths)."""
        from app.services.album_service import AlbumService

        album_svc = AlbumService(self.db)
        for ga in group_albums:
            album = ga.albums
            if album and not album.genres:
                album_svc.backfill_genres(album.id, album.title, album.artist)
