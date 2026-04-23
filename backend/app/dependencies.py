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
from app.services.notification_service import NotificationService
from app.services.review_service import ReviewService
from app.services.stats_service import StatsService
from app.services.user_service import UserService
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


def get_stats_service(db: Session = Depends(get_db)) -> StatsService:
    """Dependency to get StatsService"""
    return StatsService(db)


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

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user_service = UserService(db)
    try:
        user = user_service.get_user_by_id(int(user_id))
    except HTTPException as e:
        raise credentials_exception from e

    return user
