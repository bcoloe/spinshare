"""Unit tests of the UserService interactions."""

import pydantic
import pytest
from app.models import User
from app.schemas.user import LoginRequest, UserCreate, UserUpdate
from app.utils import security
from fastapi import HTTPException, status


class TestUserServiceCreate:
    """Test creation endpoints for UserService."""

    def test_create_user_success(self, sample_user_service, test_password):
        """Test that user creation is successful."""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        user = sample_user_service.create_user(user_data=user_data)

        assert user.email == user_data.email
        assert user.username == user_data.username
        assert user.password_hash != user_data.password
        assert security.verify_password(user_data.password, user.password_hash)

    def test_create_user_duplicate_email(self, sample_user_service, test_password):
        """Test that creating a user with the same email returns an error."""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        _ = sample_user_service.create_user(user_data=user_data)

        new_user_data = UserCreate(
            email=user_data.email, username="sebastian", password="a-Fine-ButNew-Password123!"
        )
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.create_user(user_data=new_user_data)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Email already registered"

    def test_create_user_duplicate_username(self, sample_user_service, test_password):
        """Test that creating a user with the same username returns an error."""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
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

    def test_get_user_by_id(self, sample_user_service, test_password):
        """Test retrieval of user from ID"""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        user = sample_user_service.create_user(user_data=user_data)
        user_ret = sample_user_service.get_user_by_id(user.id)
        assert user == user_ret

    def test_get_user_by_id_invalid(self, sample_user_service):
        """Test attempt to get non-existent user by ID throws"""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.get_user_by_id(42)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "User not found"

    def test_get_user_by_email(self, sample_user_service, test_password):
        """Test retrieval of user from email"""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        user = sample_user_service.create_user(user_data=user_data)
        user_ret = sample_user_service.get_user_by_email(user.email)
        assert user == user_ret

    def test_get_user_by_email_invalid(self, sample_user_service):
        """Test attempt to get non-existent user by email returns None"""
        assert sample_user_service.get_user_by_email("bad@test.com") is None

    def test_get_user_by_username(self, sample_user_service, test_password):
        """Test retrieval of user from email"""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
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

    def test_update_user_email(self, sample_user_service, sample_user):
        """Test that updating the email of a user works."""
        update_data = UserUpdate(email="new@test.com")
        sample_user_dict = sample_user.__dict__.copy()
        updated_user = sample_user_service.update_user(
            user_id=sample_user.id, user_data=update_data
        )
        assert updated_user.email != sample_user_dict.get("email")
        assert updated_user.email == "new@test.com"
        assert updated_user.id == sample_user_dict.get("id")
        assert updated_user.username == sample_user_dict.get("username")
        assert updated_user.password_hash == sample_user_dict.get("password_hash")

    def test_update_user_email_conflict(self, sample_user_service, sample_user):
        """Test that updating the email to that of existing user throws"""
        other_user = sample_user_service.create_user(
            UserCreate(email="new@test.com", username="updated_name", password="a-Fine-pwd123455!")
        )

        # Attempt to update to same email as other_user
        update_data = UserUpdate(email=other_user.email)
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.update_user(user_id=sample_user.id, user_data=update_data)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Email already in use"

    def test_update_username(self, sample_user_service, sample_user):
        """Test that updating the username of a user works."""
        update_data = UserUpdate(username="updated_name")
        sample_user_dict = sample_user.__dict__.copy()
        updated_user = sample_user_service.update_user(
            user_id=sample_user.id, user_data=update_data
        )
        assert updated_user.email == sample_user_dict.get("email")
        assert updated_user.id == sample_user_dict.get("id")
        assert updated_user.username != sample_user_dict.get("username")
        assert updated_user.username == "updated_name"
        assert updated_user.password_hash == sample_user_dict.get("password_hash")

    @pytest.mark.parametrize("casing", [("exact", "lower", "upper", "title")])
    def test_update_user_username_conflict(self, sample_user_service, sample_user, casing):
        """Test that updating the email to that of existing user throws"""
        other_user = sample_user_service.create_user(
            UserCreate(email="new@test.com", username="updated_name", password="a-Fine-pwd123455!")
        )

        # Attempt to update to same email as other_user
        new_username = other_user.username
        if casing == "lower":
            new_username = new_username.lower()
        if casing == "upper":
            new_username = new_username.upper()
        if casing == "title":
            new_username = new_username.title()

        update_data = UserUpdate(username=new_username)
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.update_user(user_id=sample_user.id, user_data=update_data)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail == "Username already taken"

    def test_update_password(self, sample_user_service, sample_user):
        """Test that updating the password of a user works."""
        update_data = UserUpdate(password="Good-and-new345?")
        sample_user_dict = sample_user.__dict__.copy()
        updated_user = sample_user_service.update_user(
            user_id=sample_user.id, user_data=update_data
        )
        assert updated_user.email == sample_user_dict.get("email")
        assert updated_user.id == sample_user_dict.get("id")
        assert updated_user.username == sample_user_dict.get("username")
        assert updated_user.password_hash != sample_user_dict.get("password_hash")


class TestUserServiceDelete:
    """Unit tests for delete endpoints of UserService."""

    def test_delete_valid_user(self, sample_user_service, sample_user):
        """Test that user deletion works."""
        assert sample_user_service.get_user_by_email(sample_user.email) is not None

        sample_user_service.delete_user(sample_user.id)
        assert sample_user_service.get_user_by_email(sample_user.email) is None

    def test_delete_invalid_user(self, sample_user_service):
        """Test that user deletion works."""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.delete_user(10)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "User not found"


class TestUserServiceAuthentication:
    """Unit tests for authentication endpoints of UserService"""

    def test_authenticate_user_success(self, sample_user_service, hashed_user):
        """Test user auth with valid credentials"""
        user = sample_user_service.authenticate_user("a-Fine-Password123!", email=hashed_user.email)
        assert user is not None
        assert user == hashed_user

    def test_authenticate_user_fail(self, sample_user_service, hashed_user):
        """Test user auth with wrong password returns None"""
        user = sample_user_service.authenticate_user(
            "wrong-password_WOMP123", email=hashed_user.email
        )
        assert user is None

    def test_authenticate_user_invalid_user_email(self, sample_user_service):
        """Test user auth with invalid user email."""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.authenticate_user("somePassword_12313!", email="invalid@test.com")
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Incorrect username or email"

    def test_authenticate_user_invalid_username(self, sample_user_service):
        """Test user auth with invalid username."""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.authenticate_user("somePassword_12313!", username="invalid_user")
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Incorrect username or email"

    def test_authenticate_user_no_user_spec(self, sample_user_service):
        """Test user auth with neither email nor username"""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.authenticate_user("somePassword_12313!")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert exc_info.value.detail == "email or username not provided."

    def test_login_successful(self, sample_user_service, hashed_user, test_password):
        request = LoginRequest(
            email=hashed_user.email, username=hashed_user.username, password=test_password
        )
        response = sample_user_service.login(request)

        assert response.access_token is not None
        assert response.refresh_token is not None
        assert response.token_type == "bearer"
        assert response.user.id == hashed_user.id
        assert response.user.email == hashed_user.email
        assert response.user.username == hashed_user.username
        assert response.user.created_at == hashed_user.created_at

    def test_login_invalid_user(self, sample_user_service, test_password):
        request = LoginRequest(email="bad@test.com", username="bad", password=test_password)
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.login(request)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "Incorrect username or email"

    def test_login_bad_password(self, sample_user_service, hashed_user, test_password):
        request = LoginRequest(
            email=hashed_user.email,
            username=hashed_user.username,
            password=test_password + "bad",
        )
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.login(request)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Incorrect password"
