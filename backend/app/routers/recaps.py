# backend/app/routers/recaps.py
"""Weekly recap endpoints — browse frozen per-group weekly recaps and drive the
first-login-of-the-week pop-up."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.config import get_settings
from app.dependencies import get_current_user, get_recap_service
from app.models import User
from app.schemas.recap import RecapResponse, RecapSummary
from app.services.recap_service import RecapService

router = APIRouter(tags=["recaps"])


@router.get("/groups/{group_id}/recaps", response_model=list[RecapResponse])
def list_group_recaps(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """All weekly recaps for a group, newest first. Requires membership."""
    return svc.list_for_group(group_id, current_user)


@router.get("/groups/{group_id}/recaps/latest", response_model=RecapResponse | None)
def get_latest_group_recap(
    group_id: int,
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """The most recent weekly recap for a group, or null. Requires membership."""
    return svc.latest_for_group(group_id, current_user)


@router.get("/groups/{group_id}/recaps/{recap_id}", response_model=RecapResponse)
def get_group_recap(
    group_id: int,
    recap_id: int,
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """A single weekly recap. Requires membership."""
    return svc.get_recap(group_id, recap_id, current_user)


@router.post("/groups/{group_id}/recaps/{recap_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_recap_seen(
    group_id: int,
    recap_id: int,
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """Mark a recap as seen for the current user (suppresses the login pop-up)."""
    svc.mark_seen(group_id, recap_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users/me/recaps/pending", response_model=list[RecapSummary])
def get_pending_recaps(
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """Latest unseen recap per group — drives the first-login-of-the-week pop-up."""
    return svc.pending_for_user(current_user)


@router.post("/groups/{group_id}/recaps/generate", response_model=RecapResponse)
def generate_group_recap(
    group_id: int,
    week_start: date,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    svc: RecapService = Depends(get_recap_service),
):
    """Generate a recap for an arbitrary past week — non-production only.

    Lets test/dev environments produce and view a recap without waiting a week.
    Returns 404 in production so the endpoint is invisible there.
    """
    if get_settings().ENVIRONMENT == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    svc._require_membership(current_user, group_id)
    recap = svc.generate_for_group(group_id, week_start, force=force)
    return svc.get_recap(group_id, recap.id, current_user)
