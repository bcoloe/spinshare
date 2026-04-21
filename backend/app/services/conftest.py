import pytest
from app.models import Album, GroupAlbum
from app.models.group import Group, GroupRole, group_members
from app.models.user import User
from app.schemas.group import GroupCreate
from app.schemas.user import UserCreate
from app.services import group_service, user_service
from app.services.album_service import AlbumService
from app.services.group_album_service import GroupAlbumService
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
def review_service(db_session) -> ReviewService:
    return ReviewService(db_session)


@pytest.fixture(scope="function")
def group_album_service(db_session) -> GroupAlbumService:
    return GroupAlbumService(db_session)


@pytest.fixture(scope="function")
def stats_service(db_session) -> StatsService:
    return StatsService(db_session)


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
def sample_group_album(db_session, sample_group, sample_album, sample_user) -> GroupAlbum:
    ga = GroupAlbum(
        group_id=sample_group.id,
        album_id=sample_album.id,
        added_by=sample_user.id,
        status="pending",
    )
    db_session.add(ga)
    db_session.commit()
    db_session.refresh(ga)
    return ga
