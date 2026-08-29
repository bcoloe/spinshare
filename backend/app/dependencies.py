# backend/app/dependencies.py
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.admin_service import AdminService
from app.services.album_service import AlbumService
from app.services.artist_service import ArtistService
from app.services.dealer_service import DealerService
from app.services.explore_service import ExploreService
from app.services.group_album_service import GroupAlbumService
from app.services.group_service import GroupService
from app.services.invitation_service import InvitationService
from app.services.invite_link_service import InviteLinkService
from app.services.link_report_service import LinkReportService
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.participation_service import ParticipationService
from app.services.public_spin_service import PublicSpinService
from app.services.recap_service import RecapService
from app.services.review_service import ReviewService
from app.services.stats_service import StatsService
from app.services.user_service import UserService
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="user/login", auto_error=False)


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


def get_artist_service(db: Session = Depends(get_db)) -> ArtistService:
    """Dependency to get ArtistService"""
    return ArtistService(db)


def get_group_album_service(db: Session = Depends(get_db)) -> GroupAlbumService:
    """Dependency to get GroupAlbumService"""
    return GroupAlbumService(db)


def get_dealer_service(db: Session = Depends(get_db)) -> DealerService:
    """Dependency to get DealerService"""
    return DealerService(db)


def get_participation_service(db: Session = Depends(get_db)) -> ParticipationService:
    """Dependency to get ParticipationService"""
    return ParticipationService(db)


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    """Dependency to get NotificationService"""
    return NotificationService(db)


def get_link_report_service(db: Session = Depends(get_db)) -> LinkReportService:
    """Dependency to get LinkReportService"""
    return LinkReportService(db)


def get_admin_service(db: Session = Depends(get_db)) -> AdminService:
    """Dependency to get AdminService"""
    return AdminService(db)


def get_invitation_service(db: Session = Depends(get_db)) -> InvitationService:
    """Dependency to get InvitationService"""
    return InvitationService(db)


def get_invite_link_service(db: Session = Depends(get_db)) -> InviteLinkService:
    """Dependency to get InviteLinkService"""
    return InviteLinkService(db)


def get_message_service(db: Session = Depends(get_db)) -> MessageService:
    """Dependency to get MessageService"""
    return MessageService(db)


def get_stats_service(db: Session = Depends(get_db)) -> StatsService:
    """Dependency to get StatsService"""
    return StatsService(db)


def get_recap_service(db: Session = Depends(get_db)) -> RecapService:
    """Dependency to get RecapService"""
    return RecapService(db)


def get_explore_service(db: Session = Depends(get_db)) -> ExploreService:
    """Dependency to get ExploreService"""
    return ExploreService(db)


def get_public_spin_service(db: Session = Depends(get_db)) -> PublicSpinService:
    """Dependency to get PublicSpinService"""
    return PublicSpinService(db)


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


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
) -> User | None:
    """
    Get the current authenticated user from JWT token if present and valid.

    A genuinely anonymous request (no token at all) resolves to None so callers
    can allow anonymous access. But a request that *does* carry a token which is
    expired or otherwise invalid raises 401 rather than silently downgrading to
    anonymous. That distinction lets a logged-in client whose 15-minute access
    token has expired mid-session receive a 401, transparently refresh, and
    retry — instead of getting a 200 that reports them as a non-member (see the
    "not in group until refreshed" bug, issue #140). Truly anonymous callers
    never send a token, so they are unaffected.
    """
    if token is None:
        return None

    return get_current_user(token=token, db=db)


@dataclass(frozen=True)
class SocketIdentity:
    """Who is opening a chat socket, and which rooms they belong to."""

    user_id: int
    username: str
    group_ids: list[int]


def get_socket_identity(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> SocketIdentity:
    """Resolve the caller's identity for a chat ticket, preferring token claims.

    Every other authenticated dependency loads the user row because the endpoint
    behind it needs the row. This one needs three things — an id, a display name,
    and a room list — and the access token already carries all three, so it can
    answer without a query.

    That matters more than it looks. A client whose socket is unstable mints a
    ticket on every reconnect; at one reconnect a minute, the reads behind that
    were enough on their own to stop Neon's compute from ever auto-suspending.
    Skipping them decouples socket churn from database wakefulness entirely.

    Tokens issued before these claims existed fall back to a lookup, so sessions
    already in flight when this deploys keep working rather than failing closed.
    The ``db`` session is opened lazily by SQLAlchemy, so the fast path costs no
    connection despite the dependency being declared.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    raw_user_id = payload.get("sub")
    if raw_user_id is None:
        raise credentials_exception
    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        raise credentials_exception from None

    username = payload.get("username")
    groups = payload.get("groups")
    if isinstance(username, str) and isinstance(groups, list):
        try:
            return SocketIdentity(user_id, username, [int(gid) for gid in groups])
        except (TypeError, ValueError):
            raise credentials_exception from None

    # Legacy token, or claims we cannot trust the shape of: resolve from the row.
    try:
        user = UserService(db).get_user_by_id(user_id)
    except HTTPException as e:
        raise credentials_exception from e
    return SocketIdentity(user.id, user.username, [group.id for group in user.groups])


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
