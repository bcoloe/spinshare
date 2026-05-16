# backend/app/routers/users.py

from app.config import get_settings
from app.dependencies import get_album_service, get_current_user, get_user_service
from app.models import User
from app.schemas.album import AlbumResponse, UserNominationResponse
from app.services.album_service import AlbumService
from app.schemas.user import (
    DecadeBreakdownItem,
    LoginRequest,
    LoginResponse,
    NominationDecadeBreakdownResponse,
    PublicProfileResponse,
    ReviewStatsResponse,
    SpotifyConnectUrlResponse,
    SpotifyTokenResponse,
    UserCreate,
    UserGroupItem,
    UserResponse,
    UserReviewResponse,
    UserUpdate,
    UserWithStats,
)
from app.services.user_service import UserService
from app.utils import spotify_client
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate, user_service: UserService = Depends(get_user_service)):
    """Register a new user"""
    return user_service.create_user(user_data)


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, user_service: UserService = Depends(get_user_service)):
    """Login and get access token"""
    return user_service.login(credentials)


@router.post("/refresh", response_model=LoginResponse)
def refresh_access_token(refresh_token: str, user_service: UserService = Depends(get_user_service)):
    """Exchange a valid REFRESH token for a new ACCESS token."""
    return user_service.refresh(refresh_token)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information via ACCESS token"""
    return current_user


@router.get("/me/nominations", response_model=list[UserNominationResponse])
def get_my_nominations(
    current_user: User = Depends(get_current_user),
    album_service: AlbumService = Depends(get_album_service),
):
    """Get all distinct albums the current user has nominated across all groups."""
    entries = album_service.get_my_nominations(current_user.id)
    return [
        UserNominationResponse(
            album=AlbumResponse.from_orm_with_genres(album),
            nominated_group_ids=group_ids,
        )
        for album, group_ids in entries
    ]


@router.get("/me/stats", response_model=UserWithStats)
def get_my_stats(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get current user statistics"""
    stats = user_service.get_user_stats(current_user.id)
    return {**current_user.__dict__, **stats}


@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update current user information"""
    return user_service.update_user(current_user.id, user_data)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Delete current user account"""
    user_service.delete_user(current_user.id)


@router.get("/{username}/profile", response_model=PublicProfileResponse)
def get_user_profile(
    username: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get public profile stats for a user by username."""
    return user_service.get_public_profile(username)


@router.get("/{username}/reviews", response_model=list[UserReviewResponse])
def get_user_reviews(
    username: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get all published reviews for a user."""
    return user_service.get_user_reviews_for_profile(username)


@router.get("/{username}/nominations/breakdown", response_model=NominationDecadeBreakdownResponse)
def get_user_nomination_breakdown(
    username: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get nomination decade breakdown for a user."""
    return user_service.get_nomination_decade_breakdown(username)


@router.get("/{username}/groups", response_model=list[UserGroupItem])
def get_user_groups_public(
    username: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get public-facing group list for a user's profile."""
    return user_service.get_groups_for_public_profile(username, current_user.id)


@router.get("/{username}/review-stats", response_model=ReviewStatsResponse)
def get_user_review_stats(
    username: str,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get review statistics (histogram, averages, guess accuracy) for a user."""
    return user_service.get_review_stats(username)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, user_service: UserService = Depends(get_user_service)):
    """Get user by ID"""
    return user_service.get_user_by_id(user_id)


@router.get("/", response_model=list[UserResponse])
def list_users(
    skip: int = 0, limit: int = 100, user_service: UserService = Depends(get_user_service)
):
    """List all users"""
    return user_service.get_all_users(skip=skip, limit=limit)


@router.get("/search/{query}", response_model=list[UserResponse])
def search_users(
    query: str, limit: int = 10, user_service: UserService = Depends(get_user_service)
):
    """Search users by username or email"""
    return user_service.search_users(query, limit=limit)


@router.get("/apple-music/developer-token")
def get_apple_music_developer_token():
    """Return a developer token for initializing MusicKit JS.

    No authentication required — developer tokens are public-facing and not user-specific.

    Raises:
        HTTPException 503: If Apple Music credentials are not configured.
    """
    from app.utils import apple_music_client

    token = apple_music_client.generate_developer_token()
    return {"developer_token": token}


@router.get("/spotify/token", response_model=SpotifyTokenResponse)
def get_spotify_token(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Return a valid Spotify access token for the current user, refreshing if needed.

    Returns 404 if no Spotify connection exists, 401 if the connection has expired
    and requires the user to reconnect.
    """
    token = user_service.get_valid_spotify_token(current_user.id)
    return SpotifyTokenResponse(access_token=token)


@router.get("/spotify/connect-url", response_model=SpotifyConnectUrlResponse)
def get_spotify_connect_url(current_user: User = Depends(get_current_user)):
    """Return the Spotify OAuth authorization URL for the current user."""
    url = spotify_client.get_auth_url(current_user.id)
    return SpotifyConnectUrlResponse(url=url)


@router.get("/spotify/callback")
def spotify_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    user_service: UserService = Depends(get_user_service),
):
    """Handle the Spotify OAuth callback.

    Exchanges the authorization code for tokens, stores the connection,
    then redirects the browser back to the frontend profile page.
    """
    settings = get_settings()
    frontend_url = settings.FRONTEND_URL

    if error or not code or not state:
        return RedirectResponse(url=f"{frontend_url}/profile?spotify=error")

    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: int = payload["user_id"]
    except (JWTError, KeyError):
        return RedirectResponse(url=f"{frontend_url}/profile?spotify=error")

    try:
        tokens = spotify_client.exchange_code_for_tokens(code)
        user_service.connect_spotify(
            user_id=user_id,
            spotify_user_id=tokens["spotify_user_id"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=tokens["expires_at"],
        )
    except Exception:
        return RedirectResponse(url=f"{frontend_url}/profile?spotify=error")

    return RedirectResponse(url=f"{frontend_url}/profile?spotify=connected")


@router.delete("/spotify", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_spotify(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Disconnect the current user's Spotify account."""
    user_service.disconnect_spotify(current_user.id)
