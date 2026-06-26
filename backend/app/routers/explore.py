# backend/app/routers/explore.py

from app.dependencies import get_current_user, get_explore_service
from app.models import User
from app.schemas.explore import ExploreAlbumsPage, ExploreGroupsPage, ExploreUsersPage, SiteStatsResponse
from app.services.explore_service import ExploreService
from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/explore", tags=["explore"])

_VALID_SORT_OPTIONS = {"top_rated", "bottom_rated", "most_reviewed", "most_nominated", "recent"}
_VALID_GROUP_TYPES = {"all", "human", "bot"}


@router.get("/albums", response_model=ExploreAlbumsPage)
def explore_albums(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    min_reviews: int | None = Query(default=None, ge=0),
    sort_by: str = Query(default="top_rated"),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    svc: ExploreService = Depends(get_explore_service),
):
    """Browse all nominated albums across the platform.

    q filters by partial match on artist or album title (case-insensitive).
    sort_by: top_rated | bottom_rated | most_reviewed | most_nominated | recent
    Results are paginated via offset/limit for infinite-scroll clients.
    """
    if sort_by not in _VALID_SORT_OPTIONS:
        sort_by = "top_rated"
    return svc.get_explore_albums(
        offset=offset, limit=limit, min_reviews=min_reviews, sort_by=sort_by, q=q or None
    )


@router.get("/groups", response_model=ExploreGroupsPage)
def explore_groups(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    group_type: str = Query(default="all"),
    current_user: User = Depends(get_current_user),
    svc: ExploreService = Depends(get_explore_service),
):
    """Browse groups on the platform (human and bot groups).

    q filters by partial name match (case-insensitive).
    group_type: all | human | bot
    Admins see all groups including private ones.
    Results are ordered alphabetically and paginated for infinite scroll.
    """
    if group_type not in _VALID_GROUP_TYPES:
        group_type = "all"
    return svc.get_explore_groups(
        offset=offset, limit=limit, q=q or None, group_type=group_type,
        include_private=current_user.is_admin,
    )


@router.get("/users", response_model=ExploreUsersPage)
def explore_users(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    svc: ExploreService = Depends(get_explore_service),
):
    """Browse all users on the platform.

    q filters by partial username match (case-insensitive).
    Results are ordered alphabetically and paginated for infinite scroll.
    """
    return svc.get_explore_users(offset=offset, limit=limit, q=q or None)


@router.get("/stats", response_model=SiteStatsResponse)
def explore_stats(
    current_user: User = Depends(get_current_user),
    svc: ExploreService = Depends(get_explore_service),
):
    """Return platform-wide statistics: totals and ranked album/artist lists."""
    return svc.get_site_stats()
