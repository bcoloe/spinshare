# backend/app/routers/group_albums.py
#
# Workflow endpoints for the GroupAlbum lifecycle:
# nomination → selection → guessing → review → reveal.
#
# IMPORTANT: this router is registered before the CRUD group_albums_router from
# albums.py so that literal path segments (/selected, /select) are matched
# before the /{group_album_id} parameter route.

from app.dependencies import get_current_user, get_group_album_service
from app.models import User
from app.schemas.group_album import (
    NominationGuessCreate,
    NominationGuessResponse,
    NominationRevealResponse,
    SelectAlbumRequest,
)
from app.schemas.album import GroupAlbumResponse
from app.services.group_album_service import GroupAlbumService
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/groups", tags=["group-album-workflow"])


# ==================== SELECTION ====================


@router.post(
    "/{group_id}/albums/select",
    response_model=GroupAlbumResponse,
    status_code=status.HTTP_200_OK,
)
def select_album(
    group_id: int,
    request: SelectAlbumRequest,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Select an album as the group's active daily spin. Requires Admin or Owner.
    Pass group_album_id to select a specific album, or omit for a random pick
    from pending nominations.
    """
    ga = svc.select_album(group_id, current_user, request)
    return GroupAlbumResponse.from_orm(ga)


@router.get("/{group_id}/albums/selected", response_model=GroupAlbumResponse)
def get_selected_album(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Get the album currently selected as the group's daily spin. Requires membership."""
    ga = svc.get_selected_album(group_id, current_user)
    return GroupAlbumResponse.from_orm(ga)


# ==================== GUESSING ====================


@router.post(
    "/{group_id}/albums/{group_album_id}/guess",
    response_model=NominationGuessResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_guess(
    group_id: int,
    group_album_id: int,
    data: NominationGuessCreate,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Submit a guess for who nominated the currently selected album.
    Album must be in 'selected' status. One guess per member.
    """
    return svc.submit_guess(group_id, group_album_id, current_user, data)


@router.put(
    "/{group_id}/albums/{group_album_id}/guess",
    response_model=NominationGuessResponse,
)
def update_guess(
    group_id: int,
    group_album_id: int,
    data: NominationGuessCreate,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Update your nomination guess while the album is still in 'selected' status."""
    return svc.update_guess(group_id, group_album_id, current_user, data)


@router.get(
    "/{group_id}/albums/{group_album_id}/guess/me",
    response_model=NominationGuessResponse,
)
def get_my_guess(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Get your current guess for a group album."""
    return svc.get_my_guess(group_id, group_album_id, current_user)


# ==================== REVIEW PHASE ====================


@router.post(
    "/{group_id}/albums/{group_album_id}/complete",
    response_model=GroupAlbumResponse,
)
def complete_review_phase(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Mark a selected album's review phase as complete (selected → reviewed).
    Requires Admin or Owner. Unlocks the nomination reveal.
    """
    ga = svc.complete_review_phase(group_id, group_album_id, current_user)
    return GroupAlbumResponse.from_orm(ga)


# ==================== REVEAL ====================


@router.get(
    "/{group_id}/albums/{group_album_id}/reveal",
    response_model=NominationRevealResponse,
)
def reveal_nominator(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Reveal who nominated the album and show each member's guess accuracy.
    Only available once the album has reached 'reviewed' status.
    """
    return svc.reveal_nominator(group_id, group_album_id, current_user)
