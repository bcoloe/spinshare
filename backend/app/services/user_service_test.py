"""Unit tests of the UserService interactions."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pydantic
import pytest
from app.models import (
    Album,
    Genre,
    Group,
    GroupAlbum,
    GroupInvitation,
    GroupInviteLink,
    GroupParticipation,
    NominationGuess,
    PriorityReviewCredit,
    Review,
    User,
)
from app.schemas.user import LoginRequest, UserCreate, UserUpdate
from app.utils import security
from fastapi import HTTPException, status
from sqlalchemy import event


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

    def test_delete_user_with_participation_credits_and_invites(
        self, sample_user_service, sample_user, sample_group, sample_album, db_session
    ):
        """A user with participation, credits, a sent invitation and an invite link deletes.

        Each of those four tables FKs to ``users.id`` with no ON DELETE clause, and
        nothing else clears them — so before this fix a single earned credit or sent
        invite made the account permanently undeletable (409 forever).
        """
        db_session.add_all(
            [
                GroupParticipation(group_id=sample_group.id, user_id=sample_user.id, credits=2),
                PriorityReviewCredit(
                    group_id=sample_group.id, user_id=sample_user.id, album_id=sample_album.id
                ),
                GroupInvitation(
                    group_id=sample_group.id,
                    invited_email="invitee@test.com",
                    invited_by=sample_user.id,
                    token="invite-token-1",
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                ),
                GroupInviteLink(
                    group_id=sample_group.id, created_by=sample_user.id, token="link-token-1"
                ),
            ]
        )
        db_session.commit()
        user_id = sample_user.id

        sample_user_service.delete_user(user_id)

        assert db_session.query(User).filter(User.id == user_id).first() is None
        assert (
            db_session.query(GroupParticipation)
            .filter(GroupParticipation.user_id == user_id)
            .count()
            == 0
        )
        assert (
            db_session.query(PriorityReviewCredit)
            .filter(PriorityReviewCredit.user_id == user_id)
            .count()
            == 0
        )
        assert (
            db_session.query(GroupInvitation).filter(GroupInvitation.invited_by == user_id).count()
            == 0
        )
        assert (
            db_session.query(GroupInviteLink).filter(GroupInviteLink.created_by == user_id).count()
            == 0
        )

    def test_delete_user_removes_invitations_addressed_to_them(
        self, sample_user_service, sample_user, sample_group, db_session, user_factory
    ):
        """A pending invitation sent *to* the deleted user's email is cleaned up too.

        It carries the address of an account that no longer exists; honouring it
        later would hand group access to whoever next registers that address.
        """
        inviter = user_factory(email="inviter@test.com", username="inviter_user")
        db_session.add(
            GroupInvitation(
                group_id=sample_group.id,
                invited_email=sample_user.email,
                invited_by=inviter.id,
                token="invite-token-2",
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
        )
        db_session.commit()
        email = sample_user.email

        sample_user_service.delete_user(sample_user.id)

        assert (
            db_session.query(GroupInvitation)
            .filter(GroupInvitation.invited_email == email)
            .count()
            == 0
        )


class TestUserServicePublicProfile:
    """The public profile must not leak private fields to other authenticated users."""

    def test_public_profile_omits_email(self, sample_user_service, sample_user):
        profile = sample_user_service.get_public_profile(sample_user.username)

        assert "email" not in profile
        assert sample_user.email not in str(profile)

    def test_public_profile_keeps_expected_fields(self, sample_user_service, sample_user):
        profile = sample_user_service.get_public_profile(sample_user.username)

        assert profile["id"] == sample_user.id
        assert profile["username"] == sample_user.username
        assert profile["is_admin"] is False


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


class TestUserServiceRefresh:
    """Tests for the token refresh flow."""

    def test_refresh_reloads_the_user_to_recompute_group_claims(
        self, sample_user_service, hashed_user
    ):
        """Refresh reads the user row, and that read is the point of it.

        The access token carries a ``groups`` claim so that opening a chat socket
        needs no query. Refresh is the only moment in a long session when that
        claim can be corrected, so it must come from the database rather than be
        copied forward from the refresh token, which may be a week old.
        """
        from app.utils.security import create_refresh_token, decode_access_token

        token = create_refresh_token({"sub": str(hashed_user.id), "email": hashed_user.email})

        result = sample_user_service.refresh(token)

        claims = decode_access_token(result.access_token)
        assert claims["username"] == hashed_user.username
        assert claims["groups"] == sorted(group.id for group in hashed_user.groups)
        assert result.token_type == "bearer"

    def test_refresh_for_a_deleted_user_is_rejected(self, sample_user_service):
        """A valid refresh token for a row that no longer exists cannot mint one."""
        from app.utils.security import create_refresh_token

        token = create_refresh_token({"sub": "999999", "email": "gone@test.com"})

        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.refresh(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_legacy_token_falls_back_to_db(self, sample_user_service, hashed_user):
        """Legacy tokens without email embedded still work via DB fallback."""
        from app.utils.security import create_refresh_token

        token = create_refresh_token({"sub": str(hashed_user.id)})
        result = sample_user_service.refresh(token)

        assert result.access_token is not None
        assert result.refresh_token is not None

    def test_refresh_invalid_token_raises_401(self, sample_user_service):
        with pytest.raises(HTTPException) as exc_info:
            sample_user_service.refresh("not.a.valid.token")
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_new_token_embeds_email(self, sample_user_service, hashed_user):
        """Tokens issued by refresh should carry email so future refreshes skip the DB."""
        from app.utils.security import create_refresh_token, decode_refresh_token

        token = create_refresh_token({"sub": str(hashed_user.id), "email": hashed_user.email})
        result = sample_user_service.refresh(token)

        new_payload = decode_refresh_token(result.refresh_token)
        assert new_payload is not None
        assert new_payload.get("email") == hashed_user.email


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


# ==================== QUERY-COUNT GUARDS ====================
#
# These pin the *shape* of a few profile reads rather than their results.
#
# app.database uses a NullPool against a serverless Postgres, so every statement
# is a fresh network round trip and the statement count — not the row count — is
# what the endpoint costs. No model declares ``lazy=``, so any relationship walk
# added to a loop silently reintroduces an N+1 that no correctness test notices.
#
# Each test therefore runs the same call over a small dataset and a much larger
# one and asserts the statement count did not move: the assertion that fails on
# regression is "grew with N", not a magic number.


@contextmanager
def count_statements(db_session):
    """Collect the SQL the session emits inside the block.

    Savepoint bookkeeping from the test fixture is filtered out — it is an
    artefact of how tests are isolated, not work the service asked for.
    """
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        head = statement.lstrip().upper()
        if head.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO SAVEPOINT")):
            return
        statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


class TestUserServiceQueryCounts:
    """Profile reads must cost a fixed number of round trips, not one per row."""

    @staticmethod
    def _albums(db_session, count: int, *, offset: int = 0) -> list[Album]:
        genre = Genre(name=f"genre-{offset}")
        db_session.add(genre)
        db_session.flush()
        albums = [
            Album(
                spotify_album_id=f"album-{offset + i}",
                title=f"Album {offset + i}",
                artist=f"Artist {offset + i}",
                release_date=f"{1960 + (offset + i) % 60}-01-01",
                genres=[genre],
            )
            for i in range(count)
        ]
        db_session.add_all(albums)
        db_session.commit()
        return albums

    def _reviews(self, db_session, user: User, count: int, *, offset: int = 0) -> None:
        for i, album in enumerate(self._albums(db_session, count, offset=offset)):
            db_session.add(
                Review(user_id=user.id, album_id=album.id, rating=float(i % 11), is_draft=False)
            )
        db_session.commit()

    def _nominations(self, db_session, user: User, group, count: int, *, offset: int = 0) -> None:
        for album in self._albums(db_session, count, offset=offset):
            db_session.add(
                GroupAlbum(group_id=group.id, album_id=album.id, added_by=user.id)
            )
        db_session.commit()

    def test_reviews_for_profile_does_not_scale_with_review_count(
        self, sample_user_service, sample_user, db_session
    ):
        """One statement per review's album, and another per album's genres, is 1+2N."""
        self._reviews(db_session, sample_user, 3)
        username = sample_user.username  # outside the block: not the call's cost
        with count_statements(db_session) as small:
            assert len(sample_user_service.get_user_reviews_for_profile(username)) == 3

        self._reviews(db_session, sample_user, 27, offset=100)
        with count_statements(db_session) as large:
            assert len(sample_user_service.get_user_reviews_for_profile(username)) == 30

        assert len(large) == len(small), (small, large)
        assert len(small) <= 4

    def test_review_stats_does_not_scale_with_review_count(
        self, sample_user_service, sample_user, db_session
    ):
        """The decade breakdown must not walk ``r.albums`` one review at a time."""
        self._reviews(db_session, sample_user, 3)
        username = sample_user.username
        with count_statements(db_session) as small:
            sample_user_service.get_review_stats(username)

        self._reviews(db_session, sample_user, 27, offset=100)
        with count_statements(db_session) as large:
            sample_user_service.get_review_stats(username)

        assert len(large) == len(small), (small, large)
        assert len(small) <= 4

    def test_nomination_breakdown_does_not_scale_with_nomination_count(
        self, sample_user_service, sample_user, sample_group, db_session
    ):
        """Only ``albums.release_date`` is needed, so it must cost one statement."""
        self._nominations(db_session, sample_user, sample_group, 3)
        username = sample_user.username
        with count_statements(db_session) as small:
            small_result = sample_user_service.get_nomination_decade_breakdown(username)

        self._nominations(db_session, sample_user, sample_group, 27, offset=100)
        with count_statements(db_session) as large:
            large_result = sample_user_service.get_nomination_decade_breakdown(username)

        assert small_result["total_nominations"] == 3
        assert large_result["total_nominations"] == 30
        assert len(large) == len(small), (small, large)
        assert len(small) <= 3

    def test_public_profile_groups_do_not_scale_with_group_count(
        self, sample_user_service, sample_user, db_session, user_factory
    ):
        """Per-group role lookups and ``len(group.members)`` were 2 queries each."""
        viewer = user_factory(email="viewer@test.com", username="viewer")

        def join(n: int, offset: int) -> None:
            for i in range(n):
                group = Group(name=f"grp-{offset + i}", is_public=True, created_by=sample_user.id)
                group.members = [sample_user, viewer]
                db_session.add(group)
            db_session.commit()

        join(2, 0)
        username, viewer_id = sample_user.username, viewer.id
        with count_statements(db_session) as small:
            small_result = sample_user_service.get_groups_for_public_profile(username, viewer_id)

        join(10, 100)
        with count_statements(db_session) as large:
            large_result = sample_user_service.get_groups_for_public_profile(username, viewer_id)

        assert len(small_result) == 2
        assert len(large_result) == 12
        assert all(g["member_count"] == 2 for g in large_result)
        assert all(g["current_user_role"] == "member" for g in large_result)
        assert len(large) == len(small), (small, large)
        assert len(small) <= 5

    def test_user_stats_counts_in_the_database(
        self, sample_user_service, sample_user, sample_group, db_session
    ):
        """Five integers should not mean five relationship loads."""
        self._reviews(db_session, sample_user, 4)
        self._nominations(db_session, sample_user, sample_group, 4, offset=200)

        user_id = sample_user.id
        with count_statements(db_session) as statements:
            stats = sample_user_service.get_user_stats(user_id)

        assert stats["total_reviews"] == 4
        assert stats["albums_added"] == 4
        assert stats["has_spotify"] is False
        # One read of the user row, one of every count.
        assert len(statements) == 2, statements

    def test_public_profile_counts_in_the_database(
        self, sample_user_service, sample_user, sample_group, db_session
    ):
        """Same for the public profile's three totals."""
        self._reviews(db_session, sample_user, 4)
        self._nominations(db_session, sample_user, sample_group, 4, offset=300)

        username = sample_user.username
        with count_statements(db_session) as statements:
            profile = sample_user_service.get_public_profile(username)

        assert profile["total_reviews"] == 4
        assert profile["albums_nominated"] == 4
        assert len(statements) == 2, statements

    def test_access_token_claims_read_only_group_ids(
        self, sample_user_service, sample_user, db_session
    ):
        """Every login and refresh builds this claim; it must not load Group rows."""
        group = Group(name="claims-grp", is_public=True, created_by=sample_user.id)
        group.members = [sample_user]
        db_session.add(group)
        db_session.commit()

        db_session.refresh(sample_user)  # the user row is already in hand at call time
        group_id = group.id
        with count_statements(db_session) as statements:
            claims = sample_user_service._access_token_data(sample_user)

        assert claims["groups"] == [group_id]
        assert len(statements) == 1, statements
        # Ids only — no column of ``groups`` other than the key is selected.
        assert "groups.name" not in statements[0]
