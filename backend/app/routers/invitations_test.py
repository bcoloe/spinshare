"""Router tests for invitation endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_group_service, get_invitation_service
from app.main import app
from app.models.invitation import GroupInvitation
from app.routers.conftest import make_mock_user
from app.services.invitation_service import InvitationService
from app.utils.security import create_access_token


def _auth_headers(user) -> dict:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return {"Authorization": f"Bearer {token}"}


def _make_mock_invitation(
    *,
    id=1,
    group_id=1,
    group_name="Bumblebees",
    invited_email="guest@example.com",
    invited_by=1,
    inviter_username="test_user",
    token="test-token-abc",
    accepted_at=None,
    days_until_expiry=7,
) -> MagicMock:
    inv = MagicMock(spec=GroupInvitation)
    inv.id = id
    inv.group_id = group_id
    inv.group_name = group_name
    inv.invited_email = invited_email
    inv.invited_by = invited_by
    inv.inviter_username = inviter_username
    inv.token = token
    inv.created_at = datetime(2026, 4, 21, tzinfo=timezone.utc)
    inv.expires_at = datetime.now(timezone.utc) + timedelta(days=days_until_expiry)
    inv.accepted_at = accepted_at
    inv.status = "accepted" if accepted_at else "pending"
    return inv


@pytest.fixture
def mock_invitation_service():
    return MagicMock(spec=InvitationService)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_invitation_service):
    mock_group_service = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_invitation_service] = lambda: mock_invitation_service
    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_invitation_service):
    mock_group_service = MagicMock()
    app.dependency_overrides[get_invitation_service] = lambda: mock_invitation_service
    app.dependency_overrides[get_group_service] = lambda: mock_group_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== POST /groups/{id}/invitations ====================

class TestSendInvitation:
    def test_send_invitation_success(self, client, mock_invitation_service):
        inv = _make_mock_invitation()
        mock_invitation_service.create_invitation.return_value = inv

        resp = client.post("/groups/1/invitations", json={"email": "guest@example.com"})

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["invited_email"] == "guest@example.com"
        mock_invitation_service.create_invitation.assert_called_once()

    def test_send_invitation_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/invitations", json={"email": "guest@example.com"})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_send_invitation_invalid_email(self, client):
        resp = client.post("/groups/1/invitations", json={"email": "not-an-email"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ==================== GET /groups/{id}/invitations ====================

class TestListInvitations:
    def test_list_invitations_success(self, client, mock_invitation_service):
        mock_invitation_service.get_group_invitations.return_value = [
            _make_mock_invitation(invited_email="a@example.com"),
            _make_mock_invitation(id=2, invited_email="b@example.com"),
        ]

        resp = client.get("/groups/1/invitations")

        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 2

    def test_list_invitations_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/invitations")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== DELETE /groups/{id}/invitations/{inv_id} ====================

class TestRevokeInvitation:
    def test_revoke_invitation_success(self, client, mock_invitation_service):
        mock_invitation_service.revoke_invitation.return_value = None

        resp = client.delete("/groups/1/invitations/42")

        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_invitation_service.revoke_invitation.assert_called_once()

    def test_revoke_invitation_unauthenticated(self, unauthed_client):
        resp = unauthed_client.delete("/groups/1/invitations/42")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== GET /invitations/{token} ====================

class TestGetInvitation:
    def test_get_invitation_success(self, client, mock_invitation_service):
        inv = _make_mock_invitation(token="mytoken")
        mock_invitation_service.get_invitation_by_token.return_value = inv

        resp = client.get("/invitations/mytoken")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["token"] == "mytoken"

    def test_get_invitation_unauthenticated_succeeds(self, unauthed_client, mock_invitation_service):
        inv = _make_mock_invitation(token="public-token")
        mock_invitation_service.get_invitation_by_token.return_value = inv

        resp = unauthed_client.get("/invitations/public-token")

        assert resp.status_code == status.HTTP_200_OK


# ==================== GET /invitations/pending ====================

class TestGetMyPendingInvitations:
    def test_returns_list(self, client, mock_invitation_service):
        mock_invitation_service.get_user_pending_invitations.return_value = [
            _make_mock_invitation(invited_email="me@example.com"),
        ]
        resp = client.get("/invitations/pending")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 1

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/invitations/pending")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== POST /invitations/{token}/accept ====================

class TestAcceptInvitation:
    def test_accept_invitation_success(self, client, mock_invitation_service):
        accepted = _make_mock_invitation(
            token="tok",
            accepted_at=datetime.now(timezone.utc),
        )
        mock_invitation_service.accept_invitation.return_value = accepted

        resp = client.post("/invitations/tok/accept")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "accepted"
        mock_invitation_service.accept_invitation.assert_called_once()

    def test_accept_invitation_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/invitations/tok/accept")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== POST /invitations/{token}/decline ====================

class TestDeclineInvitation:
    def test_decline_success(self, client, mock_invitation_service):
        mock_invitation_service.decline_invitation.return_value = None
        resp = client.post("/invitations/tok/decline")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_invitation_service.decline_invitation.assert_called_once()

    def test_decline_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/invitations/tok/decline")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
