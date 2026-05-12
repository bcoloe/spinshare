# backend/app/routers/albums.py

from app.dependencies import get_album_service, get_current_user, get_review_service
from app.models import User
from app.schemas.album import (
    AlbumCreate,
    AlbumResponse,
    AlbumReviewItem,
    AlbumSearchResult,
    AlbumStatsResponse,
    GroupAlbumCreate,
    GroupAlbumResponse,
    GroupAlbumStatusUpdate,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.album_service import AlbumService
from app.services.review_service import ReviewService
from app.utils import spotify_client
from fastapi import APIRouter, Depends, HTTPException, Query, status

albums_router = APIRouter(prefix="/albums", tags=["albums"])
group_albums_router = APIRouter(prefix="/groups", tags=["group-albums"])


# ==================== ALBUMS ====================


@albums_router.get("/search", response_model=list[AlbumSearchResult])
def search_albums(
    q: str | None = Query(default=None, min_length=2),
    artist: str | None = Query(default=None),
    album: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Search for albums via Spotify. At least one of q, artist, or album is required."""
    if not any([q, artist, album]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search parameter (q, artist, album) is required",
        )
    results = spotify_client.search_albums(q or "", artist=artist, album=album)
    return [
        AlbumSearchResult(
            spotify_album_id=r.spotify_album_id,
            title=r.title,
            artist=r.artist,
            release_date=r.release_date,
            cover_url=r.cover_url,
            genres=r.genres,
        )
        for r in results
    ]


@albums_router.post("/", response_model=AlbumResponse, status_code=status.HTTP_201_CREATED)
def create_album(
    data: AlbumCreate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Register a new album. Returns 409 if the Spotify ID is already registered."""
    album = album_service.create_album(data)
    return AlbumResponse.from_orm_with_genres(album)


@albums_router.post(
    "/get-or-create", response_model=AlbumResponse, status_code=status.HTTP_200_OK
)
def get_or_create_album(
    data: AlbumCreate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Return an existing album by Spotify ID or create it if not yet registered."""
    album = album_service.get_or_create_album(data)
    return AlbumResponse.from_orm_with_genres(album)


@albums_router.get("/spotify/{spotify_album_id}", response_model=AlbumResponse)
def get_album_by_spotify_id(
    spotify_album_id: str,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Look up a registered album by its Spotify album ID."""
    album = album_service.get_album_by_spotify_id(spotify_album_id)
    return AlbumResponse.from_orm_with_genres(album)


@albums_router.get("/{album_id}", response_model=AlbumResponse)
def get_album(
    album_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Get a registered album by its internal ID."""
    album = album_service.get_album_by_id(album_id)
    return AlbumResponse.from_orm_with_genres(album)


# ==================== REVIEWS ====================


@albums_router.post(
    "/{album_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED
)
def create_review(
    album_id: int,
    data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """Submit a review for an album. One review per user per album."""
    album_service.get_album_by_id(album_id)
    return review_service.create_review(album_id, current_user.id, data)


@albums_router.get("/{album_id}/reviews", response_model=list[AlbumReviewItem])
def list_reviews(
    album_id: int,
    group_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """List all published reviews for an album, including each reviewer's username."""
    album_service.get_album_by_id(album_id)
    return review_service.get_reviews_for_album(album_id, viewer_id=current_user.id, group_id=group_id)


@albums_router.get("/{album_id}/stats", response_model=AlbumStatsResponse)
def get_album_stats(
    album_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """Return global rating stats and histogram for an album."""
    album_service.get_album_by_id(album_id)
    return review_service.get_album_stats(album_id)


@albums_router.get("/{album_id}/reviews/me", response_model=ReviewResponse)
def get_my_review(
    album_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """Get the current user's review for an album."""
    album_service.get_album_by_id(album_id)
    return review_service.get_review_by_user_and_album(album_id, current_user.id)


@albums_router.patch("/{album_id}/reviews/{review_id}", response_model=ReviewResponse)
def update_review(
    album_id: int,
    review_id: int,
    data: ReviewUpdate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """Update your review for an album."""
    album_service.get_album_by_id(album_id)
    return review_service.update_review(review_id, current_user.id, data)


@albums_router.delete(
    "/{album_id}/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_review(
    album_id: int,
    review_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
    review_service: ReviewService = Depends(get_review_service),
):
    """Delete your review for an album."""
    album_service.get_album_by_id(album_id)
    review_service.delete_review(review_id, current_user.id)


# ==================== GROUP ALBUMS ====================


@group_albums_router.post(
    "/{group_id}/albums",
    response_model=GroupAlbumResponse,
    status_code=status.HTTP_201_CREATED,
)
def nominate_album(
    group_id: int,
    data: GroupAlbumCreate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Nominate an album to a group's catalog. Requires group membership."""
    ga = album_service.nominate_album(group_id, data.album_id, current_user)
    return GroupAlbumResponse.from_orm(ga)


@group_albums_router.get("/{group_id}/albums", response_model=list[GroupAlbumResponse])
def list_group_albums(
    group_id: int,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """List all albums in a group's catalog, optionally filtered by status."""
    gas = album_service.get_group_albums(group_id, status_filter=status)
    return [GroupAlbumResponse.from_orm(ga) for ga in gas]


@group_albums_router.get("/{group_id}/albums/today", response_model=list[GroupAlbumResponse])
def get_todays_albums(
    group_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Return albums selected for today in this group."""
    gas = album_service.get_todays_albums(group_id)
    return [GroupAlbumResponse.from_orm(ga) for ga in gas]


@group_albums_router.get(
    "/{group_id}/albums/{group_album_id}", response_model=GroupAlbumResponse
)
def get_group_album(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Get a specific nominated album entry from a group catalog."""
    ga = album_service.get_group_album(group_id, group_album_id)
    return GroupAlbumResponse.from_orm(ga)


@group_albums_router.delete(
    "/{group_id}/albums/{group_album_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_group_album(
    group_id: int,
    group_album_id: int,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Remove an album nomination from a group. Requires Admin/Owner or being the nominator."""
    album_service.remove_group_album(group_id, group_album_id, current_user)


@group_albums_router.patch(
    "/{group_id}/albums/{group_album_id}/status", response_model=GroupAlbumResponse
)
def update_group_album_status(
    group_id: int,
    group_album_id: int,
    data: GroupAlbumStatusUpdate,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Update the status of a nominated album (pending/selected/reviewed). Requires Admin/Owner."""
    ga = album_service.update_group_album_status(group_id, group_album_id, data, current_user)
    return GroupAlbumResponse.from_orm(ga)
