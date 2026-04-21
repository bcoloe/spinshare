# backend/app/routers/stats.py

from app.dependencies import get_current_user, get_stats_service
from app.models import User
from app.schemas.stats import (
    AlbumGuessStatsResponse,
    AlbumReviewStatsResponse,
    UserGuessStatsResponse,
)
from app.services.stats_service import StatsService
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/groups/{group_id}/members/{user_id}/guesses",
    response_model=UserGuessStatsResponse,
)
def get_user_guess_stats(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    svc: StatsService = Depends(get_stats_service),
):
    """Guess accuracy for a user within a group. Requires group membership."""
    return svc.get_user_guess_stats(user_id, group_id)


@router.get(
    "/groups/{group_id}/albums/{group_album_id}/guesses",
    response_model=AlbumGuessStatsResponse,
)
def get_album_guess_stats(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    svc: StatsService = Depends(get_stats_service),
):
    """Per-member guess breakdown for a group album. Requires group membership."""
    return svc.get_album_guess_stats(group_id, group_album_id)


@router.get("/albums/{album_id}/reviews", response_model=AlbumReviewStatsResponse)
def get_album_review_stats(
    album_id: int,
    current_user: User = Depends(get_current_user),
    svc: StatsService = Depends(get_stats_service),
):
    """Aggregate review score stats (avg, min, max) for an album."""
    return svc.get_album_review_stats(album_id)
