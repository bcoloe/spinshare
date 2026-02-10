import pytest
from app.models.user import User
from app.schemas.user import UserCreate
from app.services import user_service


@pytest.fixture(scope="function")
def sample_user_service(db_session):
    return user_service.UserService(db_session)


@pytest.fixture(scope="function")
def add_sample_user(sample_user_service, test_password) -> User:
    user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
    return sample_user_service.create_user(user_data)
