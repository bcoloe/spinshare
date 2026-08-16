"""Tests for the chat WebSocket handshake and lifecycle.

Starlette's TestClient drives a real socket through the ASGI app, so these cover
the handshake, the ticket auth boundary, and that presence is registered and
torn down around the connection.
"""

from unittest.mock import patch

import pytest
from app.main import app
from app.realtime.connection_manager import manager
from app.routers.ws import WS_UNAUTHORIZED
from app.utils.security import (
    create_access_token,
    create_chat_ticket,
    create_refresh_token,
)
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def ws_client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_identity():
    """Stub the one DB read the socket performs: username + group ids."""
    with patch("app.routers.ws._load_identity", return_value=("alice", {10, 20})) as m:
        yield m


@pytest.fixture(autouse=True)
def clean_registry():
    """Keep the module-level singleton from leaking state between tests."""
    manager._rooms.clear()
    yield
    manager._rooms.clear()


class TestHandshakeAuth:
    def test_valid_ticket_connects(self, ws_client, fake_identity):
        ticket = create_chat_ticket(1)

        with ws_client.websocket_connect(f"/ws/chat?ticket={ticket}") as ws:
            message = ws.receive_json()

        assert message["type"] == "presence.snapshot"
        assert message["user_id"] == 1

    def test_missing_ticket_is_rejected(self, ws_client):
        with pytest.raises(WebSocketDisconnect) as exc:
            with ws_client.websocket_connect("/ws/chat") as ws:
                ws.receive_json()

        assert exc.value.code == WS_UNAUTHORIZED

    def test_garbage_ticket_is_rejected(self, ws_client):
        with pytest.raises(WebSocketDisconnect) as exc:
            with ws_client.websocket_connect("/ws/chat?ticket=not-a-jwt") as ws:
                ws.receive_json()

        assert exc.value.code == WS_UNAUTHORIZED

    def test_access_token_is_not_accepted_as_a_ticket(self, ws_client, fake_identity):
        """A leaked access token must not open a socket — types are distinct."""
        token = create_access_token(data={"sub": "1", "email": "a@test.com"})

        with pytest.raises(WebSocketDisconnect) as exc:
            with ws_client.websocket_connect(f"/ws/chat?ticket={token}") as ws:
                ws.receive_json()

        assert exc.value.code == WS_UNAUTHORIZED

    def test_refresh_token_is_not_accepted_as_a_ticket(self, ws_client, fake_identity):
        token = create_refresh_token(data={"sub": "1"})

        with pytest.raises(WebSocketDisconnect) as exc:
            with ws_client.websocket_connect(f"/ws/chat?ticket={token}") as ws:
                ws.receive_json()

        assert exc.value.code == WS_UNAUTHORIZED

    def test_unknown_user_is_rejected(self, ws_client):
        ticket = create_chat_ticket(999)

        with patch("app.routers.ws._load_identity", return_value=None):
            with pytest.raises(WebSocketDisconnect) as exc:
                with ws_client.websocket_connect(f"/ws/chat?ticket={ticket}") as ws:
                    ws.receive_json()

        assert exc.value.code == WS_UNAUTHORIZED

class TestSnapshot:
    def test_snapshot_covers_every_group_the_user_belongs_to(
        self, ws_client, fake_identity
    ):
        ticket = create_chat_ticket(1)

        with ws_client.websocket_connect(f"/ws/chat?ticket={ticket}") as ws:
            snapshot = ws.receive_json()

        assert set(snapshot["groups"].keys()) == {"10", "20"}

    def test_snapshot_lists_users_already_online(self, ws_client, fake_identity):
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as first:
            first.receive_json()

            with patch(
                "app.routers.ws._load_identity", return_value=("bob", {10})
            ):
                with ws_client.websocket_connect(
                    f"/ws/chat?ticket={create_chat_ticket(2)}"
                ) as second:
                    snapshot = second.receive_json()

        assert snapshot["groups"]["10"] == [
            {"user_id": 1, "username": "alice"},
            {"user_id": 2, "username": "bob"},
        ]


class TestLifecycle:
    def test_connection_registers_presence(self, ws_client, fake_identity):
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as ws:
            ws.receive_json()
            assert manager.is_online(10, 1) is True
            assert manager.is_online(20, 1) is True

    def test_presence_is_released_on_disconnect(self, ws_client, fake_identity):
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as ws:
            ws.receive_json()

        assert manager.is_online(10, 1) is False
        assert manager.connection_count() == 0

    def test_join_is_pushed_to_an_already_connected_peer(
        self, ws_client, fake_identity
    ):
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as first:
            first.receive_json()  # own snapshot

            with patch("app.routers.ws._load_identity", return_value=("bob", {10})):
                with ws_client.websocket_connect(
                    f"/ws/chat?ticket={create_chat_ticket(2)}"
                ) as second:
                    second.receive_json()
                    event = first.receive_json()

        assert event["type"] == "presence.join"
        assert event["user_id"] == 2
        assert event["username"] == "bob"

    def test_leave_is_pushed_when_a_peer_disconnects(self, ws_client, fake_identity):
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as first:
            first.receive_json()

            with patch("app.routers.ws._load_identity", return_value=("bob", {10})):
                with ws_client.websocket_connect(
                    f"/ws/chat?ticket={create_chat_ticket(2)}"
                ) as second:
                    second.receive_json()
            first.receive_json()  # the join

            event = first.receive_json()

        assert event["type"] == "presence.leave"
        assert event["user_id"] == 2

    def test_client_sent_frames_are_discarded(self, ws_client, fake_identity):
        """Nothing a client sends over the socket mutates state."""
        with ws_client.websocket_connect(f"/ws/chat?ticket={create_chat_ticket(1)}") as ws:
            ws.receive_json()
            ws.send_text('{"type": "message.new", "body": "nice try"}')
            ws.send_text("garbage")

            # Still connected, and no echo of the injected payload.
            assert manager.is_online(10, 1) is True
