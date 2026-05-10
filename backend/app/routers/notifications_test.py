"""Router tests for notification endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_notification_service
from app.main import app
from app.models.notification import Notification
from app.routers.conftest import make_mock_user
from app.schemas.notification import NotificationType
from app.services.notification_service import NotificationService


def _make_mock_notification(*, id=1, read=False) -> MagicMock:
    n = MagicMock(spec=Notification)
    n.id = id
    n.type = NotificationType.invitation_accepted
    n.message = "alice accepted your invitation to join Bumblebees"
    n.group_id = 1
    n.read_at = datetime.now(timezone.utc) if read else None
    n.created_at = datetime(2026, 4, 22, tzinfo=timezone.utc)
    return n


@pytest.fixture
def mock_notification_service():
    return MagicMock(spec=NotificationService)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_notification_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_notification_service] = lambda: mock_notification_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_notification_service):
    app.dependency_overrides[get_notification_service] = lambda: mock_notification_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetUnreadNotifications:
    def test_returns_list(self, client, mock_notification_service):
        mock_notification_service.get_unread.return_value = [_make_mock_notification()]
        resp = client.get("/notifications")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 1

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/notifications")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetNotificationHistory:
    def test_returns_all_notifications(self, client, mock_notification_service):
        mock_notification_service.get_all.return_value = [
            _make_mock_notification(id=1),
            _make_mock_notification(id=2, read=True),
        ]
        resp = client.get("/notifications/history")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 2

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/notifications/history")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestMarkAllRead:
    def test_success(self, client, mock_notification_service):
        mock_notification_service.mark_all_read.return_value = None
        resp = client.post("/notifications/read-all")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_notification_service.mark_all_read.assert_called_once()

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/notifications/read-all")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestMarkOneRead:
    def test_success(self, client, mock_notification_service):
        mock_notification_service.mark_read.return_value = _make_mock_notification(read=True)
        resp = client.post("/notifications/42/read")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["read_at"] is not None

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/notifications/42/read")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
