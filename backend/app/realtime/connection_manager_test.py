"""Tests for the WebSocket connection registry.

These exercise presence and fanout logic directly against fake sockets — there
is no HTTP or database involved, which is the point: presence is derived purely
from the in-memory registry.
"""

import asyncio

import pytest

from app.realtime.connection_manager import Connection, ConnectionManager


class FakeSocket:
    """Records what was sent, and can be told to fail like a dead peer."""

    def __init__(self, *, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail

    async def send_json(self, payload: dict) -> None:
        if self.fail:
            raise RuntimeError("socket is closed")
        self.sent.append(payload)

    def events(self, event_type: str) -> list[dict]:
        return [p for p in self.sent if p["type"] == event_type]


def make_connection(user_id: int, group_ids, *, fail: bool = False) -> Connection:
    socket = FakeSocket(fail=fail)
    return Connection(
        websocket=socket,  # type: ignore[arg-type]
        user_id=user_id,
        username=f"user{user_id}",
        group_ids=set(group_ids),
    )


@pytest.fixture
def manager() -> ConnectionManager:
    return ConnectionManager()


class TestPresence:
    @pytest.mark.asyncio
    async def test_connect_marks_user_online(self, manager):
        conn = make_connection(1, [10])

        await manager.connect(conn)

        assert manager.is_online(10, 1) is True
        assert manager.presence(10) == [{"user_id": 1, "username": "user1"}]

    @pytest.mark.asyncio
    async def test_connect_returns_snapshot_of_each_room(self, manager):
        await manager.connect(make_connection(1, [10, 20]))

        snapshot = await manager.connect(make_connection(2, [10]))

        assert snapshot == {
            10: [{"user_id": 1, "username": "user1"}, {"user_id": 2, "username": "user2"}]
        }

    @pytest.mark.asyncio
    async def test_disconnect_marks_user_offline(self, manager):
        conn = make_connection(1, [10])
        await manager.connect(conn)

        await manager.disconnect(conn)

        assert manager.is_online(10, 1) is False
        assert manager.presence(10) == []

    @pytest.mark.asyncio
    async def test_presence_is_scoped_per_group(self, manager):
        await manager.connect(make_connection(1, [10]))
        await manager.connect(make_connection(2, [20]))

        assert manager.presence(10) == [{"user_id": 1, "username": "user1"}]
        assert manager.presence(20) == [{"user_id": 2, "username": "user2"}]

    @pytest.mark.asyncio
    async def test_join_is_announced_to_others_but_not_self(self, manager):
        first = make_connection(1, [10])
        await manager.connect(first)

        second = make_connection(2, [10])
        await manager.connect(second)

        assert [e["user_id"] for e in first.websocket.events("presence.join")] == [2]
        assert second.websocket.events("presence.join") == []

    @pytest.mark.asyncio
    async def test_leave_is_announced(self, manager):
        first = make_connection(1, [10])
        second = make_connection(2, [10])
        await manager.connect(first)
        await manager.connect(second)

        await manager.disconnect(second)

        assert [e["user_id"] for e in first.websocket.events("presence.leave")] == [2]


class TestMultipleTabs:
    @pytest.mark.asyncio
    async def test_second_tab_does_not_re_announce_join(self, manager):
        observer = make_connection(99, [10])
        await manager.connect(observer)
        await manager.connect(make_connection(1, [10]))
        observer.websocket.sent.clear()

        await manager.connect(make_connection(1, [10]))  # same user, second tab

        assert observer.websocket.events("presence.join") == []

    @pytest.mark.asyncio
    async def test_user_stays_online_until_last_tab_closes(self, manager):
        tab_one = make_connection(1, [10])
        tab_two = make_connection(1, [10])
        await manager.connect(tab_one)
        await manager.connect(tab_two)

        await manager.disconnect(tab_one)
        assert manager.is_online(10, 1) is True

        await manager.disconnect(tab_two)
        assert manager.is_online(10, 1) is False

    @pytest.mark.asyncio
    async def test_presence_lists_a_user_once_regardless_of_tabs(self, manager):
        await manager.connect(make_connection(1, [10]))
        await manager.connect(make_connection(1, [10]))

        assert manager.presence(10) == [{"user_id": 1, "username": "user1"}]


class TestFanout:
    @pytest.mark.asyncio
    async def test_broadcast_reaches_every_socket_in_the_room(self, manager):
        first = make_connection(1, [10])
        second = make_connection(2, [10])
        await manager.connect(first)
        await manager.connect(second)

        await manager._broadcast(10, {"type": "message.new", "message": {"id": 1}})

        assert len(first.websocket.events("message.new")) == 1
        assert len(second.websocket.events("message.new")) == 1

    @pytest.mark.asyncio
    async def test_broadcast_does_not_leak_across_groups(self, manager):
        insider = make_connection(1, [10])
        outsider = make_connection(2, [20])
        await manager.connect(insider)
        await manager.connect(outsider)

        await manager._broadcast(10, {"type": "message.new", "message": {"id": 1}})

        assert outsider.websocket.events("message.new") == []

    @pytest.mark.asyncio
    async def test_broadcast_to_empty_room_is_a_noop(self, manager):
        await manager._broadcast(999, {"type": "message.new", "message": {}})

    @pytest.mark.asyncio
    async def test_failed_send_drops_only_that_socket(self, manager):
        healthy = make_connection(1, [10])
        broken = make_connection(2, [10], fail=True)
        await manager.connect(healthy)
        await manager.connect(broken)

        await manager._broadcast(10, {"type": "message.new", "message": {"id": 1}})

        assert len(healthy.websocket.events("message.new")) == 1
        # The dead peer is reaped, and its departure announced to the survivor.
        assert manager.is_online(10, 2) is False
        assert [e["user_id"] for e in healthy.websocket.events("presence.leave")] == [2]


class TestBroadcastFromThread:
    @pytest.mark.asyncio
    async def test_schedules_broadcast_onto_the_loop(self, manager):
        """A sync route handler runs in a threadpool and cannot await fanout."""
        conn = make_connection(1, [10])
        await manager.connect(conn)

        # Mimic the threadpool: call the sync entry point off the event loop.
        await asyncio.to_thread(
            manager.broadcast_from_thread, 10, {"type": "message.new", "message": {"id": 7}}
        )
        await asyncio.sleep(0)  # let the scheduled coroutine run

        assert conn.websocket.events("message.new") == [
            {"type": "message.new", "message": {"id": 7}}
        ]

    def test_is_a_noop_when_no_socket_has_ever_connected(self, manager):
        # No loop bound yet — nobody to broadcast to, and definitely not an error.
        manager.broadcast_from_thread(10, {"type": "message.new", "message": {}})


class TestConnectionCount:
    @pytest.mark.asyncio
    async def test_counts_sockets_not_users(self, manager):
        await manager.connect(make_connection(1, [10]))
        await manager.connect(make_connection(1, [10]))
        await manager.connect(make_connection(2, [10]))

        assert manager.connection_count() == 3

    @pytest.mark.asyncio
    async def test_disconnect_is_safe_to_call_twice(self, manager):
        conn = make_connection(1, [10])
        await manager.connect(conn)

        await manager.disconnect(conn)
        await manager.disconnect(conn)

        assert manager.connection_count() == 0
