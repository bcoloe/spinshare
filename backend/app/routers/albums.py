# backend/app/routers/albums.py

import difflib

from app.database import SessionLocal
from app.dependencies import get_album_service, get_current_user, get_review_service
from app.models import User
from app.schemas.album import (
    AlbumCreate,
    AlbumResponse,
    AlbumReviewItem,
    AlbumSearchPage,
    AlbumSearchResult,
    AlbumStatsResponse,
    AlbumUrlResolveRequest,
    GroupAlbumCreate,
    GroupAlbumResponse,
    GroupAlbumStatusUpdate,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.album_service import AlbumService
from app.services.review_service import ReviewService
from app.utils import apple_music_client, spotify_client
from app.utils.album_search import merge_search_results, normalize_title_for_dedup
from app.utils.url_parser import MusicService, detect_service, extract_apple_music_album_id, extract_spotify_album_id, extract_youtube_music_id, scrape_bandcamp_metadata
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

albums_router = APIRouter(prefix="/albums", tags=["albums"])
group_albums_router = APIRouter(prefix="/groups", tags=["group-albums"])

# Similarity thresholds for Spotify backfill matching (mirrors Apple Music client values).
_TITLE_THRESHOLD = 0.82
_ARTIST_THRESHOLD = 0.60


# ==================== ALBUMS ====================


_SEARCH_PAGE_SIZE = 10


def _backfill_apple_music_id_bg(album_id: int, title: str, artist: str) -> None:
    """Background task that resolves the Apple Music album ID in its own DB session."""
    db = SessionLocal()
    try:
        AlbumService(db).backfill_apple_music_id(album_id, title, artist)
    finally:
        db.close()


def _find_spotify_album(title: str, artist: str):
    """Search Spotify for an album and return the best fuzzy match, or None.

    Used when backfilling Spotify metadata from a non-Spotify source (e.g. Bandcamp, YTM).
    Returns a SpotifyAlbumResult or None.
    """
    try:
        page = spotify_client.search_albums(artist=artist, album=title, limit=5)
    except HTTPException:
        return None
    if not page.items:
        return None
    q_title = normalize_title_for_dedup(title)
    q_artist = artist.lower()
    for result in page.items:
        c_title = normalize_title_for_dedup(result.title)
        c_artist = result.artist.lower()
        title_sim = difflib.SequenceMatcher(None, q_title, c_title).ratio()
        artist_sim = difflib.SequenceMatcher(None, q_artist, c_artist).ratio()
        if title_sim >= _TITLE_THRESHOLD and artist_sim >= _ARTIST_THRESHOLD:
            return result
    return None


@albums_router.get("/search", response_model=AlbumSearchPage)
def search_albums(
    q: str | None = Query(default=None, min_length=2),
    artist: str | None = Query(default=None),
    album: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Search for albums. Results start with any matching albums already in the system,
    then Spotify and Apple Music results deduplicated against them.

    On the first page (offset=0) results are merged from both services and deduplicated.
    Subsequent pages contain Spotify results only (Apple Music was fully included on page 1).
    """
    if not any([q, artist, album]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one search parameter (q, artist, album) is required",
        )

    # --- DB-first: surface already-registered albums ---
    db_albums = album_service.search_albums_in_db(query=q or "", artist=artist, album=album)
    db_keys: set[tuple[str, str]] = set()
    db_results: list[AlbumSearchResult] = []
    for a in db_albums:
        key = (normalize_title_for_dedup(a.title), a.artist.lower())
        if key not in db_keys:
            db_keys.add(key)
            db_results.append(AlbumSearchResult(
                album_id=a.id,
                spotify_album_id=a.spotify_album_id,
                apple_music_album_id=a.apple_music_album_id,
                youtube_music_id=a.youtube_music_id,
                artist_url=a.artist_url,
                title=a.title,
                artist=a.artist,
                release_date=a.release_date,
                cover_url=a.cover_url,
                genres=[g.name for g in a.genres],
            ))

    # --- External API search ---
    spotify_items = []
    next_offset = None
    try:
        page = spotify_client.search_albums(q or "", limit=_SEARCH_PAGE_SIZE, offset=offset, artist=artist, album=album)
        spotify_items = page.items
        next_offset = offset + _SEARCH_PAGE_SIZE if offset + _SEARCH_PAGE_SIZE < page.total else None
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            raise
        # Spotify unavailable — continue with Apple Music results only

    apple_items = []
    if offset == 0:
        apple_items = apple_music_client.search_albums_catalog(
            query=q or "", artist=artist, album=album
        )

    unified = merge_search_results(spotify_items, apple_items)

    # Exclude API results already represented by a DB album
    api_results = [
        AlbumSearchResult(
            spotify_album_id=r.spotify_album_id,
            apple_music_album_id=r.apple_music_album_id,
            title=r.title,
            artist=r.artist,
            release_date=r.release_date,
            cover_url=r.cover_url,
            genres=r.genres,
        )
        for r in unified
        if (normalize_title_for_dedup(r.title), r.artist.lower()) not in db_keys
    ]

    return AlbumSearchPage(
        items=db_results + api_results,
        next_offset=next_offset,
    )


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Return an existing album by Spotify ID or create it if not yet registered.

    On first creation, schedules a background task to resolve the Apple Music album ID.
    """
    is_new = album_service.find_existing_album(data) is None
    album = album_service.get_or_create_album(data)
    if is_new and album.apple_music_album_id is None:
        background_tasks.add_task(_backfill_apple_music_id_bg, album.id, data.title, data.artist)
    return AlbumResponse.from_orm_with_genres(album)


@albums_router.post(
    "/resolve-url", response_model=AlbumResponse, status_code=status.HTTP_200_OK
)
def resolve_album_url(
    data: AlbumUrlResolveRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Resolve an album from a streaming service or artist URL.

    Supported services:
      - Spotify: https://open.spotify.com/album/{id}
      - Apple Music: https://music.apple.com/{storefront}/album/.../{id}
      - YouTube Music: https://music.youtube.com/browse/{browseId} or /playlist?list={id}
      - Bandcamp: https://{artist}.bandcamp.com/album/{slug}  (requires artist + album fields)

    Returns the stored album, creating it if necessary and backfilling other service IDs.
    """
    service = detect_service(data.url)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unrecognized URL — supported services: Spotify, Apple Music, YouTube Music, Bandcamp",
        )

    if service == MusicService.Spotify:
        album_id = extract_spotify_album_id(data.url)
        if not album_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract Spotify album ID from URL",
            )
        result = spotify_client.get_album_by_id(album_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found on Spotify",
            )
        album_data = AlbumCreate(
            spotify_album_id=result.spotify_album_id,
            title=result.title,
            artist=result.artist,
            release_date=result.release_date,
            cover_url=result.cover_url,
            genres=result.genres,
        )
        is_new = album_service.find_existing_album(album_data) is None
        album = album_service.get_or_create_album(album_data)
        if is_new and album.apple_music_album_id is None:
            background_tasks.add_task(_backfill_apple_music_id_bg, album.id, album.title, album.artist)
        return AlbumResponse.from_orm_with_genres(album)

    if service == MusicService.AppleMusic:
        album_id = extract_apple_music_album_id(data.url)
        if not album_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract Apple Music album ID from URL",
            )
        result = apple_music_client.get_album_by_id(album_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found on Apple Music",
            )
        album_data = AlbumCreate(
            apple_music_album_id=result.id,
            title=result.title,
            artist=result.artist,
            release_date=result.release_date,
            cover_url=result.cover_url,
            genres=result.genres,
        )
        album = album_service.get_or_create_album(album_data)
        return AlbumResponse.from_orm_with_genres(album)

    if service == MusicService.YouTubeMusic:
        from app.utils.ytmusic_client import get_album_details

        ytm_id = extract_youtube_music_id(data.url)
        if not ytm_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract YouTube Music album ID from URL",
            )
        details = get_album_details(ytm_id)
        if not details:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Album not found on YouTube Music",
            )
        title = details["title"]
        artist = details["artist"]
        browse_id = details.get("browse_id") or ytm_id

        # Try to backfill Spotify and Apple Music IDs
        spotify_id = None
        apple_id = None
        cover_url = details.get("cover_url")
        release_date = details.get("release_date")
        genres: list[str] = []

        spotify_result = _find_spotify_album(title, artist)
        if spotify_result:
            spotify_id = spotify_result.spotify_album_id
            cover_url = cover_url or spotify_result.cover_url
            release_date = release_date or spotify_result.release_date

        apple_result = apple_music_client.find_apple_music_album(title, artist)
        if apple_result:
            apple_id = apple_result.id
            cover_url = cover_url or apple_result.cover_url
            genres = apple_result.genres

        album_data = AlbumCreate(
            spotify_album_id=spotify_id,
            apple_music_album_id=apple_id,
            youtube_music_id=browse_id,
            title=title,
            artist=artist,
            release_date=release_date,
            cover_url=cover_url,
            genres=genres,
        )
        album = album_service.get_or_create_album(album_data)
        return AlbumResponse.from_orm_with_genres(album)

    # Bandcamp — try auto-scraping first, then fall back to manual fields
    scraped = scrape_bandcamp_metadata(data.url)
    if scraped:
        title = scraped["title"]
        artist = scraped["artist"]
        scraped_cover: str | None = scraped.get("cover_url")
    elif data.artist and data.album:
        title = data.album
        artist = data.artist
        scraped_cover = None
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not auto-detect album info from this Bandcamp URL — please provide artist and album name",
        )

    # Try to backfill Spotify and Apple Music IDs
    spotify_id = None
    apple_id = None
    cover_url = None
    release_date = None
    genres: list[str] = []

    spotify_result = _find_spotify_album(title, artist)
    if spotify_result:
        spotify_id = spotify_result.spotify_album_id
        cover_url = spotify_result.cover_url
        release_date = spotify_result.release_date

    apple_result = apple_music_client.find_apple_music_album(title, artist)
    if apple_result:
        apple_id = apple_result.id
        cover_url = cover_url or apple_result.cover_url
        genres = apple_result.genres

    # Fall back to Bandcamp-scraped cover if no higher-quality source resolved one
    cover_url = cover_url or scraped_cover

    album_data = AlbumCreate(
        spotify_album_id=spotify_id,
        apple_music_album_id=apple_id,
        artist_url=data.url,
        title=title,
        artist=artist,
        release_date=release_date,
        cover_url=cover_url,
        genres=genres,
    )
    album = album_service.get_or_create_album(album_data)
    return AlbumResponse.from_orm_with_genres(album)


@albums_router.get("/apple-music/{apple_music_album_id}", response_model=AlbumResponse)
def get_album_by_apple_music_id(
    apple_music_album_id: str,
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Look up a registered album by its Apple Music album ID."""
    album = album_service.get_album_by_apple_music_id(apple_music_album_id)
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


# ==================== GROUP REVIEWS ====================


@group_albums_router.get("/{group_id}/reviews/me", response_model=list[ReviewResponse])
def get_my_group_reviews(
    group_id: int,
    current_user: User = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
):
    """Get the current user's reviews for all albums in a group."""
    return review_service.get_my_reviews_for_group(group_id, current_user.id)


@group_albums_router.get("/{group_id}/reviews", response_model=list[AlbumReviewItem])
def get_group_reviews(
    group_id: int,
    current_user: User = Depends(get_current_user),
    review_service: ReviewService = Depends(get_review_service),
):
    """Get all published reviews for all albums in a group."""
    return review_service.get_all_reviews_for_group(group_id, current_user.id)


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
