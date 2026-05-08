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
    GuessOptionsResponse,
    NominationCountResponse,
    NominationGuessCreate,
)
from app.services.group_album_service import GroupAlbumService
from fastapi import APIRouter, Depends, Query, status

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


@router.post("/{group_id}/albums/select-today", response_model=list[GroupAlbumResponse])
def trigger_daily_selection(
    group_id: int,
    force_chaos: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Trigger random daily album selection if none have been chosen today.
    Idempotent — safe to call concurrently. Requires membership.
    Set force_chaos=true to fill all slots from the global pool when the nomination
    pool is empty and chaos mode is enabled (FULL CHAOS MODE).
    """
    gas = svc.trigger_daily_selection(group_id, current_user, force_chaos=force_chaos)
    return [GroupAlbumResponse.from_orm(ga) for ga in gas]


# ==================== NOMINATION POOL ====================


@router.get("/{group_id}/nominations/count", response_model=NominationCountResponse)
def get_nomination_count(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return the number of pending (unselected) nominations remaining in the pool."""
    count = svc.get_pending_nomination_count(group_id, current_user)
    return NominationCountResponse(pending_count=count)


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
    "/{group_id}/albums/{group_album_id}/guess/options",
    response_model=GuessOptionsResponse,
)
def get_guess_options(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return the deterministic, capped pool of users to present as nomination-guess candidates.

    The pool always contains at least one nominator. All members see the same choices for a
    given album. Pool size is controlled by the group's guess_user_cap setting (default 5).
    """
    return svc.get_guess_options(group_id, group_album_id, current_user)


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
