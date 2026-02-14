import pytest
from app.models.group import Group, GroupRole, group_members
from app.models.user import User
from app.schemas.group import GroupCreate
from app.schemas.user import UserCreate
from app.services import group_service, user_service
from sqlalchemy import update


@pytest.fixture(scope="function")
def sample_user_service(db_session):
    return user_service.UserService(db_session)


@pytest.fixture(scope="function")
def sample_user(sample_user_service, test_password) -> User:
    user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
    return sample_user_service.create_user(user_data)


@pytest.fixture(scope="function")
def user_factory(sample_user_service, test_password):
    """User creation factory"""

    def _create_user(*, email="user@test.com", username="test_user", password=test_password):
        user_data = UserCreate(email=email, username=username, password=password)
        return sample_user_service.create_user(user_data)

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
