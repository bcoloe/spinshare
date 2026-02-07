import pytest
from app.services import user_service


@pytest.fixture(scope="function")
def sample_user_service(db_session):
    return user_service.UserService(db_session)
