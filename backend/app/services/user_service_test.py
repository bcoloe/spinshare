import pytest
from app.schemas.user import UserCreate
from app.utils import security
from fastapi import HTTPException, status


@pytest.mark.skip(reason="This class is currently not relevant for the test suite")
class TestUserService:
    def test_create_user_success(self, sample_user_service):
        """Test that user creation is successful."""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        user = sample_user_service.create_user(user_data=user_data)

        assert user.email == user_data.email
        assert user.username == user_data.username
        assert user.password_has != user_data.password
        assert security.verify_password(user_data.password, user.password_hash)

    def test_create_user_duplicate_email(self, sample_user_service):
        """Test that creating a user with the same email returns an error."""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        _ = sample_user_service.create_user(user_data=user_data)

        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.create_user(user_data=user_data)

        assert exc_info.status_code == status.HTTP_409_CONFLICT
        assert exc_info.detail == "Email already registered"
