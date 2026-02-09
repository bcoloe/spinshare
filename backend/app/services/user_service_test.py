import pydantic
import pytest
from app.models import User
from app.schemas.user import UserCreate
from app.utils import security
from fastapi import HTTPException, status


class TestUserServiceCreate:
    """Test creation endpoints for UserService."""

    def test_create_user_success(self, sample_user_service):
        """Test that user creation is successful."""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        user = sample_user_service.create_user(user_data=user_data)

        assert user.email == user_data.email
        assert user.username == user_data.username
        assert user.password_hash != user_data.password
        assert security.verify_password(user_data.password, user.password_hash)

    def test_create_user_duplicate_email(self, sample_user_service):
        """Test that creating a user with the same email returns an error."""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        _ = sample_user_service.create_user(user_data=user_data)

        new_user_data = UserCreate(
            email=user_data.email, username="sebastian", password="a-Fine-ButNew-Password123!"
        )
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.create_user(user_data=new_user_data)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Email already registered"

    def test_create_user_duplicate_username(self, sample_user_service):
        """Test that creating a user with the same username returns an error."""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        _ = sample_user_service.create_user(user_data=user_data)

        new_user_data = UserCreate(
            email="different@test.com",
            username=user_data.username,
            password="a-Fine-ButNew-Password123!",
        )
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.create_user(user_data=new_user_data)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Username already taken"

    @pytest.mark.parametrize(
        "password,expect_reasons",
        [
            # test too short
            ("1tooS!", [security.PasswordStrengthConditions.Length]),
            # test too long
            ("a-FINE-password123!" * 100, [security.PasswordStrengthConditions.Length]),
            # test missing uppercase
            ("a-fine-password123!", [security.PasswordStrengthConditions.UppercaseLetter]),
            # test missing lowercase
            (
                "a-fine-password123!".upper(),
                [security.PasswordStrengthConditions.LowercaseLetter],
            ),
            # test missing numbers
            ("a-FINE-password!", [security.PasswordStrengthConditions.Number]),
            # test spaces
            ("a FINE password123!", [security.PasswordStrengthConditions.NoSpaces]),
            # test no special characters
            ("a-FINE-password123", [security.PasswordStrengthConditions.SpecialCharacters]),
            # test multiple violations
            (
                "a-FINE password",
                [
                    security.PasswordStrengthConditions.SpecialCharacters,
                    security.PasswordStrengthConditions.Number,
                    security.PasswordStrengthConditions.NoSpaces,
                ],
            ),
        ],
    )
    def test_create_user_bad_password(self, password, expect_reasons):
        """Test that creating a user with a weak password returns an error."""
        with pytest.raises(pydantic.ValidationError):
            UserCreate(email="user@test.com", username="test_user", password=password)


class TestUserServiceRead:
    """Unit tests of read endpoints from UserService"""

    def test_get_user_by_id(self, sample_user_service):
        """Test retrieval of user from ID"""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        user = sample_user_service.create_user(user_data=user_data)
        user_ret = sample_user_service.get_user_by_id(user.id)
        assert user == user_ret

    def test_get_user_by_id_invalid(self, sample_user_service):
        """Test attempt to get non-existent user by ID throws"""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.get_user_by_id(42)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "User not found"

    def test_get_user_by_email(self, sample_user_service):
        """Test retrieval of user from email"""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        user = sample_user_service.create_user(user_data=user_data)
        user_ret = sample_user_service.get_user_by_email(user.email)
        assert user == user_ret

    def test_get_user_by_email_invalid(self, sample_user_service):
        """Test attempt to get non-existent user by email returns None"""
        assert sample_user_service.get_user_by_email("bad@test.com") is None

    def test_get_user_by_username(self, sample_user_service):
        """Test retrieval of user from email"""
        user_data = UserCreate(
            email="user@test.com", username="test_user", password="a-Fine-Password123!"
        )
        user = sample_user_service.create_user(user_data=user_data)
        user_ret = sample_user_service.get_user_by_username(user.username)
        assert user == user_ret

    def test_get_user_by_username_invalid(self, sample_user_service):
        """Test attempt to get non-existent user by username returns None"""
        assert sample_user_service.get_user_by_username("fake_user") is None

    def test_get_all_users_in_limit(self, sample_user_service):
        """Test get all users within limit"""
        users_created = []
        for idx in range(10):
            user_data = UserCreate(
                email=f"user{idx}@test.com",
                username=f"test_user{idx}",
                password="a-Fine-Password123!",
            )
            user = sample_user_service.create_user(user_data=user_data)
            users_created.append(user)
        users = sample_user_service.get_all_users()
        assert len(users) == len(users_created)

    def test_get_all_users_limited(self, sample_user_service):
        """Test get all users limited"""
        users_created = []
        for idx in range(10):
            user_data = UserCreate(
                email=f"user{idx}@test.com",
                username=f"test_user{idx}",
                password="a-Fine-Password123!",
            )
            user = sample_user_service.create_user(user_data=user_data)
            users_created.append(user)
        limit = 3
        users = sample_user_service.get_all_users(limit=limit)
        assert len(users) <= limit
        for u in users:
            assert u in users_created

    def test_get_all_users_with_offset(self, sample_user_service):
        """Test get all users with skip"""
        users_created = []
        for idx in range(10):
            user_data = UserCreate(
                email=f"user{idx}@test.com",
                username=f"test_user{idx}",
                password="a-Fine-Password123!",
            )
            user = sample_user_service.create_user(user_data=user_data)
            users_created.append(user)
        offset = 3
        users = sample_user_service.get_all_users(skip=offset)
        assert len(users) == len(users_created) - offset
        for u in users:
            assert u in users_created

    def test_search_users_matching_email(self, sample_user_service):
        """Test searching users with matching email"""
        emails = ["foo", "bar", "baz", "food"]
        users_created: list[User] = []
        for idx, email in enumerate(emails):
            user_data = UserCreate(
                email=f"{email}@test.com", username=f"user{idx}", password="a-Fine-Password123!"
            )
            users_created.append(sample_user_service.create_user(user_data))

        matched_users = sample_user_service.search_users(query="foo")
        assert len(matched_users) == 2
        for user in matched_users:
            assert "foo" in user.email

    def test_search_users_matching_username(self, sample_user_service):
        """Test searching users with matching email"""
        usernames = ["foo", "bar", "baz", "food"]
        users_created: list[User] = []
        for idx, username in enumerate(usernames):
            user_data = UserCreate(
                email=f"test{idx}@test.com", username=f"{username}", password="a-Fine-Password123!"
            )
            users_created.append(sample_user_service.create_user(user_data))

        matched_users = sample_user_service.search_users(query="foo")
        assert len(matched_users) == 2
        for user in matched_users:
            assert "foo" in user.username


class TestUserServiceUpdate:
    """Unit tests for update endpoints of UserService."""

    # TODO
