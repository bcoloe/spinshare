"""Public daily draw: a shared, read-only 3-album spin shown to anonymous
visitors on the landing page and inside the anonymous global-group view.

Unlike dealer-mode rolls, there is no per-visitor identity or session tracking:
exactly one draw is computed per calendar day and cached, and every anonymous
visitor sees the same three albums for that day.
"""

import random

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PublicSpinDraw
from app.schemas.album import GroupAlbumResponse
from app.schemas.public_spin import PublicSpinResponse
from app.services import group_service as gs
from app.services.dealer_service import DealerService, _global_candidate_album_ids
from app.utils.time_helpers import DEFAULT_TZ, group_today

DRAW_SIZE = 3


class PublicSpinService:
    """Service for the anonymous-visitor public daily draw."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_todays_draw(self) -> PublicSpinResponse:
        """Return today's shared 3-album draw, creating it on first request.

        Raises:
            HTTPException 503: If the global group hasn't been seeded yet.
        """
        group_service = gs.GroupService(self.db)
        global_group = group_service.get_global_group()
        if global_group is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Global group not configured",
            )

        today = group_today(DEFAULT_TZ)
        draw = self.db.query(PublicSpinDraw).filter(PublicSpinDraw.draw_date == today).first()

        if draw is None:
            pool = [
                row[0]
                for row in _global_candidate_album_ids(self.db, global_group.id).distinct().all()
            ]
            draw_n = min(DRAW_SIZE, len(pool))
            album_ids = random.sample(pool, draw_n) if draw_n else []

            draw = PublicSpinDraw(draw_date=today, album_ids=album_ids)
            self.db.add(draw)
            try:
                self.db.commit()
            except IntegrityError:
                # Another request created today's row first — use theirs.
                self.db.rollback()
                draw = self.db.query(PublicSpinDraw).filter(PublicSpinDraw.draw_date == today).first()
            else:
                self.db.refresh(draw)

        dealer = DealerService(self.db)
        album_ids = draw.album_ids or []
        if album_ids:
            dealer.ensure_global_canonical_rows(global_group.id, album_ids)
        canonical = dealer.canonical_group_albums(global_group.id, album_ids)
        dealer.heal_genres(list(canonical.values()))

        albums = [GroupAlbumResponse.from_orm(canonical[aid]) for aid in album_ids if aid in canonical]
        return PublicSpinResponse(draw_date=draw.draw_date, albums=albums)
