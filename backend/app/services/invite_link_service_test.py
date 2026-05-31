"""Tests for InviteLinkService."""

import pytest
from fastapi import HTTPException, status

from app.models.group import GroupRole
from app.services.invite_link_service import InviteLinkService


@pytest.fixture
def invite_link_service(db_session):
    return InviteLinkService(db_session)


# ==================== GET LINK ====================

class TestGetLink:
    def test_get_link_returns_none_when_none_exists(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        result = invite_link_service.get_link(sample_group.id, sample_user, sample_group_service)
        assert result is None

    def test_get_link_admin_forbidden_by_default_for_member(
        self, db_session, invite_link_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members cannot get the link when the group uses the default admin-only setting."""
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.get_link(sample_group.id, member, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_get_link_member_succeeds_when_setting_allows_members(
        self, db_session, invite_link_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members can get the link when min_role_to_add_members is set to 'member'."""
        sample_group.settings.min_role_to_add_members = "member"
        db_session.commit()

        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        result = invite_link_service.get_link(sample_group.id, member, sample_group_service)
        assert result is None  # no link yet — but no 403 raised

    def test_get_link_group_not_found_raises_404(
        self, invite_link_service, sample_group_service, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.get_link(9999, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ==================== CREATE / ROTATE ====================

class TestCreateOrRotateLink:
    def test_create_link_success(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        link = invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        assert link.group_id == sample_group.id
        assert link.token is not None
        assert link.created_by == sample_user.id

    def test_rotate_link_changes_token(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        link = invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        original_token = link.token

        rotated = invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        assert rotated.token != original_token

    def test_create_link_admin_forbidden_by_default_for_member(
        self, db_session, invite_link_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members cannot create/rotate a link when the group uses the default admin-only setting."""
        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.create_or_rotate_link(
                sample_group.id, member, sample_group_service
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_create_link_member_succeeds_when_setting_allows_members(
        self, db_session, invite_link_service, sample_group_service, sample_group, user_factory
    ):
        """Regular members can create a link when min_role_to_add_members is set to 'member'."""
        sample_group.settings.min_role_to_add_members = "member"
        db_session.commit()

        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        link = invite_link_service.create_or_rotate_link(
            sample_group.id, member, sample_group_service
        )
        assert link.group_id == sample_group.id
        assert link.token is not None

    def test_create_link_group_not_found_raises_404(
        self, invite_link_service, sample_group_service, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.create_or_rotate_link(9999, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ==================== REVOKE LINK ====================

class TestRevokeLink:
    def test_revoke_link_success(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        # Should not raise
        invite_link_service.revoke_link(sample_group.id, sample_user, sample_group_service)

    def test_revoke_link_not_found_raises_404(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.revoke_link(sample_group.id, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_revoke_link_member_forbidden_even_when_setting_allows_members(
        self, db_session, invite_link_service, sample_group_service, sample_group, user_factory
    ):
        """Revoking a link is an admin-only action regardless of min_role_to_add_members."""
        sample_group.settings.min_role_to_add_members = "member"
        db_session.commit()

        member = user_factory(email="member@test.com", username="member")
        sample_group_service.add_user(sample_group.id, member.id)

        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.revoke_link(sample_group.id, member, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ==================== ACCEPT LINK ====================

class TestAcceptLink:
    def test_accept_link_adds_user(
        self, db_session, invite_link_service, sample_group_service, sample_group, sample_user, user_factory
    ):
        link = invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        joiner = user_factory(email="joiner@test.com", username="joiner")

        invite_link_service.accept_link(link.token, joiner, sample_group_service)
        assert sample_group_service.is_user_in_group(joiner.id, sample_group.id)

    def test_accept_link_already_member_raises_409(
        self, invite_link_service, sample_group_service, sample_group, sample_user
    ):
        link = invite_link_service.create_or_rotate_link(
            sample_group.id, sample_user, sample_group_service
        )
        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.accept_link(link.token, sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_accept_link_invalid_token_raises_404(
        self, invite_link_service, sample_group_service, sample_user
    ):
        with pytest.raises(HTTPException) as exc_info:
            invite_link_service.accept_link("bad-token", sample_user, sample_group_service)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
