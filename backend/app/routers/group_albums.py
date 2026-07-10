# backend/app/routers/group_albums.py
#
# Workflow endpoints for the GroupAlbum lifecycle.
# Selection is cron-driven (see scripts/daily_album_selector.py).
# Guessing returns instant nominator feedback.
#
# IMPORTANT: registered before the CRUD group_albums_router so that literal
# path segments (/today, /guess/me) are matched before /{group_album_id}.

from app.dependencies import get_current_user, get_dealer_service, get_group_album_service
from app.models import User
from app.schemas.album import GroupAlbumResponse
from app.schemas.group_album import (
    CheckGuessResponse,
    DealRollResponse,
    DealsTodayResponse,
    GuessOptionsResponse,
    NominationCountResponse,
    NominationGuessCreate,
)
from app.services.dealer_service import DealerService
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


@router.get("/{group_id}/albums/catchup", response_model=list[GroupAlbumResponse])
def get_catchup_albums(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return up to 10 most-recently-selected albums the user has not yet reviewed (catch-up mode).

    Excludes today's spin. Returns [] when catch_up_enabled is False on the group's settings.
    Requires membership.
    """
    gas = svc.get_catchup_albums(group_id, current_user)
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


# ==================== DEALER MODE ====================


@router.post("/{group_id}/deals/roll", response_model=DealRollResponse)
def roll_deal(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: DealerService = Depends(get_dealer_service),
):
    """Roll the dice in a dealer-mode group: reveal the next album from the caller's
    daily allotment. Requires membership and dealer mode enabled.
    409 details: dealer_mode_disabled, no_rolls_remaining, dealer_pool_empty.
    """
    return svc.roll(group_id, current_user)


@router.get("/{group_id}/deals/today", response_model=DealsTodayResponse)
def get_todays_deals(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: DealerService = Depends(get_dealer_service),
):
    """Return the caller's deals revealed today plus roll accounting. Requires membership.
    Returns an empty response (rolls_per_day=0) when dealer mode is off.
    """
    return svc.get_todays_deals(group_id, current_user)


@router.get("/{group_id}/albums/history", response_model=list[GroupAlbumResponse])
def get_member_history(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: DealerService = Depends(get_dealer_service),
):
    """Return the caller's review history for the group: the union of shared daily
    selections and albums dealt to the caller (dealer mode), newest first.
    Requires membership.
    """
    return svc.get_member_history(group_id, current_user)


# ==================== NOMINATION POOL ====================


@router.get("/{group_id}/nominations/count", response_model=NominationCountResponse)
def get_nomination_count(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return the number of pending nominations in the pool and today's nominations by the caller."""
    pending_count = svc.get_pending_nomination_count(group_id, current_user)
    today_count = svc.get_today_nomination_count(group_id, current_user)
    return NominationCountResponse(pending_count=pending_count, today_count=today_count)


# ==================== GUESSING ====================


@router.get("/{group_id}/guesses/me", response_model=list[CheckGuessResponse])
def get_my_group_guesses(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: GroupAlbumService = Depends(get_group_album_service),
):
    """Return all of the current user's nomination guesses for albums in a group."""
    return svc.get_my_guesses_for_group(group_id, current_user.id)


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
