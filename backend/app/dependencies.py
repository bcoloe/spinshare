# backend/app/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.album_service import AlbumService
from app.services.group_album_service import GroupAlbumService
from app.services.group_service import GroupService
from app.services.invitation_service import InvitationService
from app.services.invite_link_service import InviteLinkService
from app.services.notification_service import NotificationService
from app.services.review_service import ReviewService
from app.services.explore_service import ExploreService
from app.services.stats_service import StatsService
from app.services.user_service import UserService
from app.utils.cache import AUTH_USER_TTL, _key, cache
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")


def get_group_service(db: Session = Depends(get_db)) -> GroupService:
    """Dependency to get GroupService"""
    return GroupService(db)


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Dependency to get UserService"""
    return UserService(db)


def get_album_service(db: Session = Depends(get_db)) -> AlbumService:
    """Dependency to get AlbumService"""
    return AlbumService(db)


def get_review_service(db: Session = Depends(get_db)) -> ReviewService:
    """Dependency to get ReviewService"""
    return ReviewService(db)


def get_group_album_service(db: Session = Depends(get_db)) -> GroupAlbumService:
    """Dependency to get GroupAlbumService"""
    return GroupAlbumService(db)


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    """Dependency to get NotificationService"""
    return NotificationService(db)


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    """Dependency to get InvitationService"""
    return InvitationService(db)


def get_invite_link_service(db: Session = Depends(get_db)) -> InviteLinkService:
    """Dependency to get InviteLinkService"""
    return InviteLinkService(db)


def get_stats_service(db: Session = Depends(get_db)) -> StatsService:
    """Dependency to get StatsService"""
    return StatsService(db)


def get_explore_service(db: Session = Depends(get_db)) -> ExploreService:
    """Dependency to get ExploreService"""
    return ExploreService(db)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Get the current authenticated user from JWT token.

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    user_id = int(user_id_str)

    # Fast path: return the cached detached User without touching the database.
    # The object is expunged before storage so only scalar columns are accessed
    # (id, username, email, is_admin, …). Route handlers and services that need
    # a session-bound user (e.g. to traverse relationships) call get_user_by_id
    # themselves via their own db dependency.
    ck = _key("users", user_id, "auth")
    cached = cache.get(ck)
    if cached is not None:
        return cached

    user_service = UserService(db)
    try:
        user = user_service.get_user_by_id(user_id)
    except HTTPException as e:
        raise credentials_exception from e

    # Detach from the current session before caching. Scalar columns remain
    # readable; lazy relationships will raise DetachedInstanceError if accessed,
    # but get_current_user consumers only read scalars (id, is_admin, etc.).
    db.expunge(user)
    cache.set(ck, user, AUTH_USER_TTL)
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current user and assert they have admin privileges.

    Raises:
        HTTPException 403: If the user is not an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
