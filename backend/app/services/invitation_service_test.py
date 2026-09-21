"""Tests for InvitationService."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import event

from app.models.group import GroupRole
from app.models.invitation import GroupInvitation
from app.schemas.invitation import InvitationCreate
from app.services.invitation_service import InvitationService


@pytest.fixture
def invitation_service(db_session):
    return InvitationService(db_session)


@pytest.fixture
def sample_invitation_service(db_session, sample_group, sample_user):
    """InvitationService seeded with a group and owner user."""
    return InvitationService(db_session)


def _make_invitation(db_session, *, group_id, invited_email, invited_by, days_until_expiry=7, accepted=False):
    now = datetime.now(timezone.utc)
    inv = GroupInvitation(
        group_id=group_id,
        invited_email=invited_email,
        invited_by=invited_by,
        token=f"tok-{invited_email}-{group_id}",
        expires_at=now + timedelta(days=days_until_expiry),
        accepted_at=now if accepted else None,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


# ==================== CREATE ====================

class TestCreateInvitation:
    def test_create_invitation_success(
        self, invitation_service, sample_group_service, sample_group, sample_user
    ):
        data = InvitationCreate(email="newuser@example.com")
        with patch("app.services.invitation_service.send_invitation_email") as mock_send:
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )

        assert inv.invited_email == "newuser@example.com"
        assert inv.group_id == sample_group.id
        assert inv.invited_by == sample_user.id
        assert inv.token is not None
        assert inv.accepted_at is None
        mock_send.assert_called_once()

    def test_create_invitation_lowercases_email(
        self, invitation_service, sample_group_service, sample_group, sample_user
    ):
        data = InvitationCreate(email="NewUser@Example.COM")
        with patch("app.services.invitation_service.send_invitation_email"):
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert inv.invited_email == "newuser@example.com"

    def test_create_invitation_non_admin_raises_403(
        self, db_session, invitation_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members cannot invite when the group uses the default admin-only setting."""
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        data = InvitationCreate(email="other@example.com")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, member, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_create_invitation_member_succeeds_when_setting_allows_members(
        self, db_session, invitation_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members can invite when min_role_to_add_members is set to 'member'."""
        sample_group.settings.min_role_to_add_members = "member"
        db_session.commit()

        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        data = InvitationCreate(email="other@example.com")
        with patch("app.services.invitation_service.send_invitation_email") as mock_send:
            inv = invitation_service.create_invitation(
                sample_group.id, data, member, sample_group_service
            )
        assert inv.invited_email == "other@example.com"
        mock_send.assert_called_once()

    def test_create_invitation_duplicate_pending_raises_409(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="dup@example.com",
            invited_by=sample_user.id,
        )
        data = InvitationCreate(email="dup@example.com")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_create_invitation_already_member_raises_409(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        existing = user_factory(email="existing@example.com", username="existing")
        sample_group_service.add_user(sample_group.id, existing.id)

        data = InvitationCreate(email="existing@example.com")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_create_invitation_expired_allows_reinvite(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        old_inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="reinvite@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        old_id = old_inv.id
        data = InvitationCreate(email="reinvite@example.com")
        with patch("app.services.invitation_service.send_invitation_email"):
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert inv.invited_email == "reinvite@example.com"
        # The old expired record must have been removed.
        assert db_session.get(GroupInvitation, old_id) is None
        # The new invitation is a distinct record.
        assert inv.id != old_id

    def test_create_invitation_group_not_found_raises_404(
        self, invitation_service, sample_group_service, sample_user
    ):
        data = InvitationCreate(email="anyone@example.com")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(9999, data, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestCreateInvitationByUsername:
    """Invites addressed by username — the search UI never learns a user's email."""

    def test_resolves_username_to_email(
        self, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="Invitee@Example.com", username="invitee")

        data = InvitationCreate(username="invitee")
        with patch("app.services.invitation_service.send_invitation_email") as mock_send:
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )

        assert inv.invited_email == invitee.email.lower()
        assert mock_send.call_args.kwargs["to_email"] == invitee.email.lower()

    def test_username_lookup_is_case_insensitive(
        self, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        user_factory(email="mixed@example.com", username="mixedcase")

        data = InvitationCreate(username="MixedCase")
        with patch("app.services.invitation_service.send_invitation_email"):
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert inv.invited_email == "mixed@example.com"

    def test_unknown_username_raises_404(
        self, invitation_service, sample_group_service, sample_group, sample_user
    ):
        data = InvitationCreate(username="ghost")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_permission_is_checked_before_username_lookup(
        self, invitation_service, sample_group_service, sample_group, user_factory
    ):
        """A non-privileged caller gets 403, not a 404 that would leak whether the
        username exists."""
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        data = InvitationCreate(username="ghost")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, member, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_existing_member_raises_409(
        self, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        existing = user_factory(email="existing@example.com", username="existing")
        sample_group_service.add_user(sample_group.id, existing.id)

        data = InvitationCreate(username="existing")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_duplicate_pending_invitation_raises_409(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        user_factory(email="dupe@example.com", username="dupe")
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="dupe@example.com",
            invited_by=sample_user.id,
        )

        data = InvitationCreate(username="dupe")
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_expired_invitation_allows_reinvite(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        user_factory(email="stale@example.com", username="stale")
        old_inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="stale@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        old_id = old_inv.id

        data = InvitationCreate(username="stale")
        with patch("app.services.invitation_service.send_invitation_email"):
            inv = invitation_service.create_invitation(
                sample_group.id, data, sample_user, sample_group_service
            )

        assert db_session.get(GroupInvitation, old_id) is None
        assert inv.id != old_id
        assert inv.invited_email == "stale@example.com"


class TestInvitationCreateValidation:
    """Exactly one of email/username must be supplied."""

    def test_email_only_is_valid(self):
        assert InvitationCreate(email="a@example.com").username is None

    def test_username_only_is_valid(self):
        assert InvitationCreate(username="someone").email is None

    def test_neither_is_rejected(self):
        with pytest.raises(ValidationError):
            InvitationCreate()

    def test_both_is_rejected(self):
        with pytest.raises(ValidationError):
            InvitationCreate(email="a@example.com", username="someone")


# ==================== READ ====================

class TestGetInvitation:
    def test_get_by_token_success(
        self, db_session, invitation_service, sample_group, sample_user
    ):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="find@example.com",
            invited_by=sample_user.id,
        )
        result = invitation_service.get_invitation_by_token(inv.token)
        assert result.id == inv.id

    def test_get_by_token_not_found_raises_404(self, invitation_service):
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.get_invitation_by_token("nonexistent-token")
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_group_invitations_returns_pending_only(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="pending@example.com",
            invited_by=sample_user.id,
        )
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="accepted@example.com",
            invited_by=sample_user.id,
            accepted=True,
        )
        results = invitation_service.get_group_invitations(
            sample_group.id, sample_user, sample_group_service
        )
        assert len(results) == 1
        assert results[0].invited_email == "pending@example.com"

    def test_get_group_invitations_excludes_expired(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="active@example.com",
            invited_by=sample_user.id,
        )
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="expired@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        results = invitation_service.get_group_invitations(
            sample_group.id, sample_user, sample_group_service
        )
        emails = {r.invited_email for r in results}
        assert emails == {"active@example.com"}

    def test_get_group_invitations_non_admin_raises_403(
        self, db_session, invitation_service, sample_group_service, sample_group, user_factory
    ):
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        with pytest.raises(HTTPException) as exc_info:
            invitation_service.get_group_invitations(
                sample_group.id, member, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== ACCEPT ====================

class TestAcceptInvitation:
    def test_accept_success(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
        )
        result = invitation_service.accept_invitation(inv.token, invitee, sample_group_service)

        assert result.accepted_at is not None
        assert sample_group_service.is_user_in_group(invitee.id, sample_group.id)

    def test_accept_wrong_email_raises_403(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        other_user = user_factory(email="other@example.com", username="other")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invited@example.com",
            invited_by=sample_user.id,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.accept_invitation(inv.token, other_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_accept_expired_raises_410(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="late@example.com", username="late")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="late@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.accept_invitation(inv.token, invitee, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_410_GONE

    def test_accept_already_accepted_raises_410(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="done@example.com", username="done")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="done@example.com",
            invited_by=sample_user.id,
            accepted=True,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.accept_invitation(inv.token, invitee, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_410_GONE


# ==================== REVOKE ====================

class TestRevokeInvitation:
    def test_revoke_success(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="revoke@example.com",
            invited_by=sample_user.id,
        )
        invitation_service.revoke_invitation(inv.id, sample_user, sample_group_service)

        result = db_session.get(GroupInvitation, inv.id)
        assert result is None

    def test_revoke_not_found_raises_404(
        self, invitation_service, sample_group_service, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.revoke_invitation(9999, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_non_admin_raises_403(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="target@example.com",
            invited_by=sample_user.id,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.revoke_invitation(inv.id, member, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_revoke_accepted_raises_409(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="accepted@example.com",
            invited_by=sample_user.id,
            accepted=True,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.revoke_invitation(inv.id, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT


# ==================== PENDING FOR USER ====================

class TestGetUserPendingInvitations:
    def test_returns_pending_for_user(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
        )
        results = invitation_service.get_user_pending_invitations(invitee)
        assert len(results) == 1
        assert results[0].invited_email == "invitee@example.com"

    def test_excludes_accepted(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
            accepted=True,
        )
        assert invitation_service.get_user_pending_invitations(invitee) == []

    def test_excludes_expired(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        assert invitation_service.get_user_pending_invitations(invitee) == []

    def test_excludes_other_users_invitations(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="other@example.com",
            invited_by=sample_user.id,
        )
        unrelated = user_factory(email="unrelated@example.com", username="unrelated")
        assert invitation_service.get_user_pending_invitations(unrelated) == []


# ==================== DECLINE ====================

class TestDeclineInvitation:
    def test_decline_success(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
        )
        invitation_service.decline_invitation(inv.token, invitee)
        assert db_session.get(GroupInvitation, inv.id) is None

    def test_decline_wrong_user_raises_403(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        other = user_factory(email="other@example.com", username="other")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="someone@example.com",
            invited_by=sample_user.id,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.decline_invitation(inv.token, other)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_decline_expired_raises_410(
        self, db_session, invitation_service, sample_group, sample_user, user_factory
    ):
        invitee = user_factory(email="invitee@example.com", username="invitee")
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="invitee@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        with pytest.raises(HTTPException) as exc_info:
            invitation_service.decline_invitation(inv.token, invitee)
        assert exc_info.value.status_code == status.HTTP_410_GONE


# ==================== MODEL PROPERTY ====================

class TestInvitationStatus:
    def test_status_pending(self, db_session, sample_group, sample_user):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="pend@example.com",
            invited_by=sample_user.id,
        )
        assert inv.status == "pending"

    def test_status_accepted(self, db_session, sample_group, sample_user):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="acc@example.com",
            invited_by=sample_user.id,
            accepted=True,
        )
        assert inv.status == "accepted"

    def test_status_expired(self, db_session, sample_group, sample_user):
        inv = _make_invitation(
            db_session,
            group_id=sample_group.id,
            invited_email="exp@example.com",
            invited_by=sample_user.id,
            days_until_expiry=-1,
        )
        assert inv.status == "expired"


@contextmanager
def _count_statements(db_session, match: str):
    """Count SQL statements containing ``match`` issued inside the block."""
    statements: list[str] = []

    def record(conn, cursor, statement, params, context, executemany):
        if match in statement:
            statements.append(statement)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", record)


class TestInvitationQueryCounts:
    """InvitationResponse reads two relationship-backed fields per row."""

    def _seed(self, db_session, group_id, inviter_id, n):
        for i in range(n):
            _make_invitation(
                db_session,
                group_id=group_id,
                invited_email=f"pending{i}@example.com",
                invited_by=inviter_id,
            )

    def test_group_listing_eager_loads_the_response_fields(
        self, db_session, invitation_service, sample_group_service, sample_group, sample_user
    ):
        """group_name and inviter_username must not cost a round trip per row."""
        self._seed(db_session, sample_group.id, sample_user.id, 5)
        # Read the fixtures' own attributes first: the commits above expired
        # them, and their refreshes would otherwise be counted below.
        expected = (sample_group.name, sample_user.username)

        with _count_statements(db_session, "FROM users") as user_q:
            with _count_statements(db_session, "FROM groups") as group_q:
                results = invitation_service.get_group_invitations(
                    sample_group.id, sample_user, sample_group_service
                )
                names = [(r.group_name, r.inviter_username) for r in results]

        assert len(names) == 5
        assert all(name == expected for name in names)
        # One selectinload apiece, not one lookup per invitation. The extra
        # groups query is get_group_by_id, which runs once for the 404 check.
        assert len(user_q) == 1, user_q
        assert len(group_q) == 2, group_q

    def test_user_listing_eager_loads_the_response_fields(
        self,
        db_session,
        invitation_service,
        sample_group_service,
        sample_user,
        user_factory,
    ):
        """One invitation per group; the inviter lookup must still be one query."""
        from app.schemas.group import GroupCreate

        invitee = user_factory(email="invitee@example.com", username="invitee")
        for i in range(4):
            group = sample_group_service.create_group(
                GroupCreate(name=f"invite group {i}"), sample_user
            )
            _make_invitation(
                db_session,
                group_id=group.id,
                invited_email="invitee@example.com",
                invited_by=sample_user.id,
            )
        # As above — refresh the fixtures before the statements are counted.
        expected_username = sample_user.username
        invitee.email  # noqa: B018

        with _count_statements(db_session, "FROM users") as user_q:
            results = invitation_service.get_user_pending_invitations(invitee)
            usernames = [r.inviter_username for r in results]

        assert usernames == [expected_username] * 4
        assert len(user_q) <= 1, user_q
