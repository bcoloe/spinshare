"""Unit tests of the UserService interactions."""

from datetime import UTC, datetime
from unittest.mock import patch

import pydantic
import pytest
from app.models import GroupAlbum, NominationGuess, User
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
            # test multiple violations
            (
                "a-FINE password",
                [
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


    def test_create_user_joins_global_group(
        self, sample_user_service, global_group, test_password
    ):
        """New users are automatically added to the global group when it exists."""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        user = sample_user_service.create_user(user_data=user_data)

        assert any(g.id == global_group.id for g in user.groups)

    def test_create_user_succeeds_without_global_group(
        self, sample_user_service, test_password
    ):
        """User creation succeeds normally when the global group has not been seeded."""
        user_data = UserCreate(email="user@test.com", username="test_user", password=test_password)
        user = sample_user_service.create_user(user_data=user_data)
        assert user.id is not None


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
        email = sample_user.email
        assert sample_user_service.get_user_by_email(email) is not None

        sample_user_service.delete_user(sample_user.id)
        assert sample_user_service.get_user_by_email(email) is None

    def test_delete_invalid_user(self, sample_user_service):
        """Test that user deletion works."""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.delete_user(10)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail == "User not found"

    def test_delete_user_removes_pending_nominations(
        self, sample_user_service, sample_user, sample_group_album, db_session
    ):
        """Pending nominations (no selected_date) are deleted with the user."""
        assert sample_group_album.selected_date is None
        ga_id = sample_group_album.id

        sample_user_service.delete_user(sample_user.id)

        assert db_session.query(GroupAlbum).filter(GroupAlbum.id == ga_id).first() is None

    def test_delete_user_preserves_selected_nominations(
        self, sample_user_service, sample_user, sample_group_album, db_session
    ):
        """Selected nominations (selected_date set) are kept but anonymized."""
        sample_group_album.selected_date = datetime.now(UTC)
        db_session.commit()
        ga_id = sample_group_album.id

        sample_user_service.delete_user(sample_user.id)

        remaining = db_session.query(GroupAlbum).filter(GroupAlbum.id == ga_id).first()
        assert remaining is not None
        assert remaining.added_by is None

    def test_delete_user_with_nomination_guesses(
        self, sample_user_service, sample_user, sample_group_album, db_session, user_factory
    ):
        """Nomination guesses referencing the deleted user are removed."""
        other_user = user_factory(email="other@test.com", username="other_user")
        sample_group_album.selected_date = datetime.now(UTC)
        db_session.commit()

        guess = NominationGuess(
            group_album_id=sample_group_album.id,
            guessing_user_id=other_user.id,
            guessed_user_id=sample_user.id,
            correct=True,
        )
        db_session.add(guess)
        db_session.commit()
        guess_id = guess.id

        sample_user_service.delete_user(sample_user.id)

        assert db_session.query(NominationGuess).filter(NominationGuess.id == guess_id).first() is None


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


class TestUserServiceAdmin:
    """Tests for admin status management in UserService."""

    def _make_admin(self, db_session, user: User) -> User:
        user.is_admin = True
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_grant_admin_success(self, db_session, sample_user_service, user_factory):
        admin = self._make_admin(db_session, user_factory(email="admin@test.com", username="admin"))
        target = user_factory(email="target@test.com", username="target")

        result = sample_user_service.set_admin_status(admin.id, target.id, True)

        assert result.is_admin is True

    def test_revoke_admin_success(self, db_session, sample_user_service, user_factory):
        admin = self._make_admin(db_session, user_factory(email="admin@test.com", username="admin"))
        target = self._make_admin(
            db_session, user_factory(email="target@test.com", username="target")
        )

        result = sample_user_service.set_admin_status(admin.id, target.id, False)

        assert result.is_admin is False

    def test_non_admin_cannot_grant(self, sample_user_service, user_factory):
        non_admin = user_factory(email="nonadmin@test.com", username="nonadmin")
        target = user_factory(email="target@test.com", username="target")

        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.set_admin_status(non_admin.id, target.id, True)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_modify_own_admin_status(self, db_session, sample_user_service, user_factory):
        admin = self._make_admin(db_session, user_factory(email="admin@test.com", username="admin"))

        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.set_admin_status(admin.id, admin.id, False)
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_grant_admin_target_not_found(self, db_session, sample_user_service, user_factory):
        admin = self._make_admin(db_session, user_factory(email="admin@test.com", username="admin"))

        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.set_admin_status(admin.id, 99999, True)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestUserServicePasswordReset:
    """Tests for the password reset request/confirm flow."""

    def test_request_sends_email_for_known_user(self, sample_user_service, user_factory):
        """request_password_reset calls send_password_reset_email for a real address.

        The service imports get_settings and send_password_reset_email locally
        inside the method, so we patch them at their definition site.
        """
        user = user_factory(email="reset@test.com", username="resetuser")
        with (
            patch("app.config.get_settings") as mock_settings,
            patch("app.utils.email.send_password_reset_email") as mock_email,
        ):
            mock_settings.return_value.FRONTEND_URL = "http://localhost:5173"
            sample_user_service.request_password_reset(user.email)

        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args.kwargs
        assert call_kwargs["to_email"] == user.email
        assert "token=" in call_kwargs["reset_url"]

    def test_request_silent_for_unknown_email(self, sample_user_service):
        """request_password_reset returns silently for an unknown address (no leak)."""
        with patch("app.utils.email.send_password_reset_email") as mock_email:
            sample_user_service.request_password_reset("nobody@nowhere.com")

        mock_email.assert_not_called()

    def test_confirm_updates_password(self, sample_user_service, user_factory):
        """confirm_password_reset hashes and stores the new password."""
        from app.utils.security import create_password_reset_token, verify_password

        user = user_factory(email="reset@test.com", username="resetuser")
        token = create_password_reset_token(user.email)
        new_password = "NewValidPass1"

        sample_user_service.confirm_password_reset(token, new_password)

        # Re-fetch from DB to verify the hash was written
        updated = sample_user_service.db.query(User).filter_by(id=user.id).first()
        assert verify_password(new_password, updated.password_hash)

    def test_confirm_invalid_token_raises_400(self, sample_user_service):
        """confirm_password_reset raises 400 for a bogus token."""
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.confirm_password_reset("not.a.token", "ValidPass1")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_expired_token_raises_400(self, sample_user_service, user_factory):
        """confirm_password_reset raises 400 for an expired token."""
        from datetime import timedelta
        from app.config import get_settings
        from jose import jwt as jose_jwt

        user = user_factory(email="reset@test.com", username="resetuser")
        settings = get_settings()
        expired_token = jose_jwt.encode(
            {
                "sub": user.email,
                "type": "password_reset",
                "exp": datetime.now(UTC) - timedelta(seconds=1),
                "iat": datetime.now(UTC) - timedelta(minutes=31),
                "jti": "test",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.confirm_password_reset(expired_token, "ValidPass1")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_weak_password_raises_400(self, sample_user_service, user_factory):
        """confirm_password_reset raises 400 when the new password is too weak."""
        from app.utils.security import create_password_reset_token

        user = user_factory(email="reset@test.com", username="resetuser")
        token = create_password_reset_token(user.email)
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.confirm_password_reset(token, "weak")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
