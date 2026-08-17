"""Router tests for chat messages, presence, and the socket ticket.

Per the house testing split these assert HTTP behaviour only — status codes,
payload shapes, and auth enforcement — with MessageService mocked out. Mention
resolution and permission rules are covered in the service tests.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from app.dependencies import get_current_user, get_message_service
from app.main import app
from app.schemas.message import MAX_MESSAGE_LENGTH
from app.services.message_service import MessageService
from app.utils.security import decode_access_token, decode_chat_ticket
from fastapi import HTTPException, status

CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def make_mock_message(
    id=1, group_id=1, user_id=1, username="test_user", body="hello", deleted_at=None
) -> MagicMock:
    message = MagicMock()
    message.id = id
    message.group_id = group_id
    message.user_id = user_id
    message.user = MagicMock(username=username) if user_id is not None else None
    message.body = body
    message.created_at = CREATED_AT
    message.edited_at = None
    message.deleted_at = deleted_at
    message.mentions = []
    return message


@pytest.fixture
def mock_message_service():
    return MagicMock(spec=MessageService)


@pytest.fixture
def chat_client(mock_user, mock_message_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_message_service] = lambda: mock_message_service
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_chat_client(mock_message_service):
    app.dependency_overrides[get_message_service] = lambda: mock_message_service
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetMessages:
    def test_returns_history(self, chat_client, mock_message_service):
        mock_message_service.get_history.return_value = [
            make_mock_message(id=1, body="one"),
            make_mock_message(id=2, body="two"),
        ]

        resp = chat_client.get("/groups/1/messages")

        assert resp.status_code == 200
        assert [m["body"] for m in resp.json()] == ["one", "two"]

    def test_passes_paging_params_through(self, chat_client, mock_message_service):
        mock_message_service.get_history.return_value = []

        chat_client.get("/groups/1/messages?before=50&after=10&limit=25")

        _, kwargs = mock_message_service.get_history.call_args
        assert kwargs["before"] == 50
        assert kwargs["after"] == 10
        assert kwargs["limit"] == 25

    def test_limit_above_maximum_is_rejected(self, chat_client, mock_message_service):
        resp = chat_client.get("/groups/1/messages?limit=1000")
        assert resp.status_code == 422

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.get("/groups/1/messages")
        assert resp.status_code == 401

    def test_forwards_service_403(self, chat_client, mock_message_service):
        mock_message_service.get_history.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member of this group"
        )

        resp = chat_client.get("/groups/1/messages")

        assert resp.status_code == 403


class TestPostMessage:
    def test_creates_message(self, chat_client, mock_message_service):
        mock_message_service.create_message.return_value = make_mock_message(body="hi")

        resp = chat_client.post("/groups/1/messages", json={"body": "hi"})

        assert resp.status_code == 201
        assert resp.json()["body"] == "hi"
        assert resp.json()["username"] == "test_user"

    def test_empty_body_is_rejected(self, chat_client):
        resp = chat_client.post("/groups/1/messages", json={"body": "   "})
        assert resp.status_code == 422

    def test_oversized_body_is_rejected(self, chat_client):
        resp = chat_client.post(
            "/groups/1/messages", json={"body": "x" * (MAX_MESSAGE_LENGTH + 1)}
        )
        assert resp.status_code == 422

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.post("/groups/1/messages", json={"body": "hi"})
        assert resp.status_code == 401

    def test_broadcasts_after_commit(self, chat_client, mock_message_service):
        mock_message_service.create_message.return_value = make_mock_message(
            id=7, group_id=3, body="hi"
        )

        with patch("app.routers.messages.manager") as mock_manager:
            chat_client.post("/groups/3/messages", json={"body": "hi"})

        group_id, payload = mock_manager.broadcast_from_thread.call_args[0]
        assert group_id == 3
        assert payload["type"] == "message.new"
        assert payload["message"]["id"] == 7

    def test_does_not_broadcast_when_the_write_fails(
        self, chat_client, mock_message_service
    ):
        mock_message_service.create_message.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member of this group"
        )

        with patch("app.routers.messages.manager") as mock_manager:
            resp = chat_client.post("/groups/1/messages", json={"body": "hi"})

        assert resp.status_code == 403
        mock_manager.broadcast_from_thread.assert_not_called()


class TestDeleteMessage:
    def test_deletes_message(self, chat_client, mock_message_service):
        mock_message_service.delete_message.return_value = make_mock_message(
            id=5, deleted_at=CREATED_AT
        )

        resp = chat_client.delete("/messages/5")

        assert resp.status_code == 200
        assert resp.json()["is_deleted"] is True
        assert resp.json()["body"] == ""

    def test_broadcasts_the_tombstone(self, chat_client, mock_message_service):
        mock_message_service.delete_message.return_value = make_mock_message(
            id=5, group_id=2, deleted_at=CREATED_AT
        )

        with patch("app.routers.messages.manager") as mock_manager:
            chat_client.delete("/messages/5")

        group_id, payload = mock_manager.broadcast_from_thread.call_args[0]
        assert group_id == 2
        assert payload["type"] == "message.deleted"
        assert payload["message"]["id"] == 5

    def test_forwards_service_403(self, chat_client, mock_message_service):
        mock_message_service.delete_message.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires at least admin role"
        )

        resp = chat_client.delete("/messages/5")

        assert resp.status_code == 403

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.delete("/messages/5")
        assert resp.status_code == 401


class TestMarkChatSeen:
    def test_clears_mentions_for_the_group(self, chat_client, mock_message_service, mock_user):
        mock_message_service.mark_chat_seen.return_value = 2

        resp = chat_client.post("/groups/7/chat/seen")

        assert resp.status_code == 204
        mock_message_service.mark_chat_seen.assert_called_once_with(7, mock_user, None)

    def test_advances_the_read_marker(self, chat_client, mock_message_service, mock_user):
        mock_message_service.mark_chat_seen.return_value = 0

        resp = chat_client.post("/groups/7/chat/seen", json={"last_message_id": 42})

        assert resp.status_code == 204
        mock_message_service.mark_chat_seen.assert_called_once_with(7, mock_user, 42)

    def test_null_marker_is_accepted(self, chat_client, mock_message_service, mock_user):
        # An empty room has no message to mark, but its mentions can still clear.
        resp = chat_client.post("/groups/7/chat/seen", json={"last_message_id": None})

        assert resp.status_code == 204
        mock_message_service.mark_chat_seen.assert_called_once_with(7, mock_user, None)

    def test_nonsense_marker_is_rejected(self, chat_client, mock_message_service):
        resp = chat_client.post("/groups/7/chat/seen", json={"last_message_id": 0})

        assert resp.status_code == 422
        mock_message_service.mark_chat_seen.assert_not_called()

    def test_clearing_nothing_still_succeeds(self, chat_client, mock_message_service):
        # The client fires this on every chat open, so "no unread mentions" is
        # the common case and must not read as an error.
        mock_message_service.mark_chat_seen.return_value = 0

        resp = chat_client.post("/groups/7/chat/seen")

        assert resp.status_code == 204

    def test_enforces_membership(self, chat_client, mock_message_service):
        mock_message_service.mark_chat_seen.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member of this group"
        )

        resp = chat_client.post("/groups/7/chat/seen")

        assert resp.status_code == 403

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.post("/groups/7/chat/seen")
        assert resp.status_code == 401


class TestUnreadCounts:
    def test_returns_a_count_per_group(self, chat_client, mock_message_service, mock_user):
        mock_message_service.unread_counts.return_value = {3: 5, 7: 1}

        resp = chat_client.get("/chat/unread")

        assert resp.status_code == 200
        assert {r["group_id"]: r["count"] for r in resp.json()} == {3: 5, 7: 1}
        mock_message_service.unread_counts.assert_called_once_with(mock_user)

    def test_nothing_unread_is_an_empty_list(self, chat_client, mock_message_service):
        mock_message_service.unread_counts.return_value = {}

        resp = chat_client.get("/chat/unread")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.get("/chat/unread")
        assert resp.status_code == 401


class TestPresence:
    def test_returns_online_members(self, chat_client, mock_message_service):
        with patch("app.routers.messages.manager") as mock_manager:
            mock_manager.presence.return_value = [
                {"user_id": 1, "username": "alice"},
                {"user_id": 2, "username": "bob"},
            ]
            resp = chat_client.get("/groups/1/presence")

        assert resp.status_code == 200
        assert [m["username"] for m in resp.json()] == ["alice", "bob"]

    def test_enforces_membership(self, chat_client, mock_message_service):
        mock_message_service.require_membership.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You must be a member of this group"
        )

        resp = chat_client.get("/groups/1/presence")

        assert resp.status_code == 403

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.get("/groups/1/presence")
        assert resp.status_code == 401


class TestChatTicket:
    def test_mints_a_ticket_for_the_caller(self, chat_client, mock_user):
        resp = chat_client.post("/chat/ticket")

        assert resp.status_code == 200
        payload = decode_chat_ticket(resp.json()["ticket"])
        assert payload is not None
        assert payload["sub"] == str(mock_user.id)

    def test_ticket_is_short_lived(self, chat_client):
        resp = chat_client.post("/chat/ticket")
        assert resp.json()["expires_in"] == 30

    def test_ticket_is_not_usable_as_an_access_token(self, chat_client):
        """The type check is what stops a ticket being replayed against the API."""
        ticket = chat_client.post("/chat/ticket").json()["ticket"]

        assert decode_access_token(ticket) is None

    def test_requires_auth(self, unauthed_chat_client):
        resp = unauthed_chat_client.post("/chat/ticket")
        assert resp.status_code == 401
