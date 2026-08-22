import pytest
from app.models import Album, GroupAlbum
from app.models.group import Group, GroupRole, group_members
from app.models.group_settings import GroupSettings
from app.models.user import User
from app.schemas.group import GroupCreate
from app.schemas.user import UserCreate
from app.services import group_service, user_service
from app.services.admin_service import AdminService
from app.services.album_service import AlbumService
from app.services.artist_service import ArtistService
from app.services.dealer_service import DealerService
from app.services.group_album_service import GroupAlbumService
from app.services.link_report_service import LinkReportService
from app.services.message_service import MessageService
from app.services.review_service import ReviewService
from app.services.stats_service import StatsService
from sqlalchemy import update

# Placeholder hash — GroupService never verifies passwords, so bcrypt is unnecessary.
_DUMMY_HASH = "dummy_hash_for_testing"


def _insert_user(db_session, *, email: str, username: str) -> User:
    """Insert a User directly, bypassing bcrypt for fast test setup."""
    user = User(email=email, username=username, password_hash=_DUMMY_HASH)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def sample_user_service(db_session):
    return user_service.UserService(db_session)


@pytest.fixture(scope="function")
def sample_user(db_session) -> User:
    return _insert_user(db_session, email="user@test.com", username="test_user")


@pytest.fixture(scope="function")
def hashed_user(sample_user_service, test_password) -> User:
    """User created via UserService so password_hash is a real bcrypt hash.

    Only use this in tests that call authenticate_user or login — bcrypt is
    intentionally avoided in other fixtures to keep the suite fast.
    """
    user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
    return sample_user_service.create_user(user_data=user_data)


@pytest.fixture(scope="function")
def user_factory(db_session):
    """User creation factory — inserts rows directly to avoid bcrypt overhead."""

    def _create_user(*, email="user@test.com", username="test_user", **_):
        return _insert_user(db_session, email=email, username=username)

    return _create_user


@pytest.fixture(scope="function")
def group_factory(sample_group_service, sample_user):
    """User creation factory"""

    def _create_group(*, name: str = "test", is_public: bool = True, user: User | None = None):
        group_data = GroupCreate(name=name, is_public=is_public)
        if user is None:
            user = sample_user
        return sample_group_service.create_group(group_data, user)

    return _create_group


@pytest.fixture(scope="function")
def sample_group_service(db_session):
    return group_service.GroupService(db_session)


@pytest.fixture(scope="function")
def sample_group_name() -> str:
    return "Bumblebees"


@pytest.fixture(scope="function")
def set_user_role(db_session):
    def _set_user_role(*, user_id: int, group_id: int, role: GroupRole):
        stmt = (
            update(group_members)
            .where(
                group_members.c.user_id == user_id,
                group_members.c.group_id == group_id,
            )
            .values(role=role.value)
        )
        db_session.execute(stmt)
        db_session.commit()

    return _set_user_role


@pytest.fixture(scope="function")
def sample_group(sample_group_service, sample_user, sample_group_name) -> Group:
    group_data = GroupCreate(name=sample_group_name)
    return sample_group_service.create_group(group_data, sample_user)


@pytest.fixture(scope="function")
def album_service(db_session) -> AlbumService:
    return AlbumService(db_session)


@pytest.fixture(scope="function")
def link_report_service(db_session) -> LinkReportService:
    return LinkReportService(db_session)


@pytest.fixture(scope="function")
def admin_service(db_session) -> AdminService:
    return AdminService(db_session)


@pytest.fixture(scope="function")
def admin_user(db_session) -> User:
    """A site admin (users.is_admin), not a group admin."""
    user = _insert_user(db_session, email="admin@test.com", username="admin")
    user.is_admin = True
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def review_service(db_session) -> ReviewService:
    return ReviewService(db_session)


@pytest.fixture(scope="function")
def artist_service(db_session) -> ArtistService:
    return ArtistService(db_session)


@pytest.fixture(scope="function")
def group_album_service(db_session) -> GroupAlbumService:
    return GroupAlbumService(db_session)


@pytest.fixture(scope="function")
def dealer_service(db_session) -> DealerService:
    return DealerService(db_session)


@pytest.fixture(scope="function")
def stats_service(db_session) -> StatsService:
    return StatsService(db_session)


@pytest.fixture(scope="function")
def message_service(db_session) -> MessageService:
    return MessageService(db_session)


@pytest.fixture(scope="function")
def group_member(db_session, sample_group, user_factory) -> User:
    """A second, non-owner member of ``sample_group``.

    Chat tests need two people in a room far more often than one, and mention
    resolution is only meaningful against another member.
    """
    member = _insert_user(db_session, email="member@test.com", username="member_user")
    db_session.execute(
        group_members.insert().values(
            group_id=sample_group.id, user_id=member.id, role=GroupRole.Member.value
        )
    )
    db_session.commit()
    return member


@pytest.fixture(scope="function")
def sample_album(db_session) -> Album:
    album = Album(
        spotify_album_id="spotify_abc123",
        title="OK Computer",
        artist="Radiohead",
        release_date="1997-05",
        cover_url="https://example.com/cover.jpg",
    )
    db_session.add(album)
    db_session.commit()
    db_session.refresh(album)
    return album


@pytest.fixture(scope="function")
def global_group(db_session) -> Group:
    """Return the platform global group, creating it if the migration hasn't seeded it yet.

    In CI, alembic upgrade head runs first and seeds the group. In local tests,
    Base.metadata.create_all is used (no migration data), so we create it here.
    """
    existing = db_session.query(Group).filter(Group.is_global == True).first()  # noqa: E712
    if existing:
        return existing
    group = Group(name="spinshare", is_public=True, is_global=True, created_by=None)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    settings = GroupSettings(group_id=group.id, allow_guessing=False)
    db_session.add(settings)
    db_session.commit()
    return group


@pytest.fixture(scope="function")
def sample_group_album(db_session, sample_group, sample_album, sample_user) -> GroupAlbum:
    ga = GroupAlbum(
        group_id=sample_group.id,
        album_id=sample_album.id,
        added_by=sample_user.id,
    )
    db_session.add(ga)
    db_session.commit()
    db_session.refresh(ga)
    return ga
