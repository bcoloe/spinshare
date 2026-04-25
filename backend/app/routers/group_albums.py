# backend/app/routers/group_albums.py
#
# Workflow endpoints for the GroupAlbum lifecycle.
# Selection is cron-driven (see scripts/daily_album_selector.py).
# Guessing returns instant nominator feedback.
#
# IMPORTANT: registered before the CRUD group_albums_router so that literal
# path segments (/today, /guess/me) are matched before /{group_album_id}.

from app.dependencies import get_current_user, get_group_album_service
from app.models import User
from app.schemas.album import GroupAlbumResponse
from app.schemas.group_album import (
    CheckGuessResponse,
    NominationGuessCreate,
)
from app.services.group_album_service import GroupAlbumService
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/groups", tags=["group-album-workflow"])


# ==================== DAILY SELECTION ====================


@router.get("/{group_id}/albums/today", response_model=list[GroupAlbumResponse])
def get_todays_albums(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return the albums selected as today's daily spins for the group. Requires membership."""
    gas = svc.get_todays_albums(group_id, current_user)
    return [GroupAlbumResponse.from_orm(ga) for ga in gas]


# ==================== GUESSING ====================


@router.post(
    "/{group_id}/albums/{group_album_id}/check-guess",
    response_model=CheckGuessResponse,
    status_code=status.HTTP_201_CREATED,
)
def check_guess(
    group_id: int,
    group_album_id: int,
    data: NominationGuessCreate,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Submit a nomination guess and receive instant feedback.
    Returns whether the guess was correct and who the actual nominator was.
    Album must have been selected. One guess per member.
    """
    return svc.check_guess(group_id, group_album_id, current_user, data)


@router.get(
    "/{group_id}/albums/{group_album_id}/guess/me",
    response_model=CheckGuessResponse,
)
def get_my_guess(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Retrieve your previously submitted nomination guess for a group album."""
    return svc.get_my_guess(group_id, group_album_id, current_user)
