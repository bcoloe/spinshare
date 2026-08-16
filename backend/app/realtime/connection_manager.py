"""In-process WebSocket registry: message fanout and user presence.

This module holds the only mutable server state in the application. Two things
follow from that, and both are load-bearing:

1. **It is per-process.** Presence and fanout are correct only when the API runs
   with a single uvicorn worker. At >1 workers each process would see just its
   own sockets, so presence would be silently *partial* — worse than absent.
   The deploy pins ``--workers 1``; see ``docs`` in the PR description. If a
   future CPU-bound workload forces multiple workers back, this class is the
   seam where a Redis pub/sub backend would slot in.

2. **The connection registry *is* the presence table.** Presence is derived from
   the same structure used for fanout, so it costs no database queries at all —
   not on connect, not on disconnect, not on read. That matters because the app
   is deliberately built to let Neon's serverless compute auto-suspend between
   requests (see ``app/database.py``), and a polling or heartbeat-backed
   presence design would defeat it.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger(__name__)


# eq=False keeps the default identity-based __eq__/__hash__. Connections are
# stored in sets, and two sockets belonging to the same user in the same rooms
# are still two distinct connections — value equality would silently collapse a
# user's second browser tab into their first.
@dataclass(eq=False)
class Connection:
    """One open socket, and the identity/rooms it was authenticated for."""

    websocket: WebSocket
    user_id: int
    username: str
    # Group ids resolved from membership at connect time. Re-resolved only on
    # reconnect, which is cheap because it happens once per session rather than
    # once per message.
    group_ids: set[int] = field(default_factory=set)


class ConnectionManager:
    """Tracks open sockets and pushes events to them."""

    def __init__(self) -> None:
        # group_id -> user_id -> that user's open sockets. The inner set exists
        # because one user may have several tabs open; presence transitions fire
        # on the first socket in and the last socket out, not on every tab.
        self._rooms: dict[int, dict[int, set[Connection]]] = {}
        # Captured on first use from the running loop so that synchronous
        # request handlers (every route in this app is a sync `def`, executed in
        # a threadpool) can schedule fanout back onto the event loop.
        self._loop: asyncio.AbstractEventLoop | None = None

    # ==================== LIFECYCLE ====================

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Record the event loop that owns these sockets.

        Called from application startup, and again on each connect as a safety
        net for tests that construct a manager directly.
        """
        self._loop = loop or asyncio.get_running_loop()

    async def connect(self, connection: Connection) -> dict[int, list[dict]]:
        """Register an accepted socket and announce the user's arrival.

        Returns the presence snapshot the caller should send to this client:
        ``{group_id: [{user_id, username}, ...]}`` covering every room the user
        joined, so initial state arrives with the connection rather than
        requiring a follow-up request.
        """
        self.bind_loop()

        newly_online: list[int] = []
        for group_id in connection.group_ids:
            room = self._rooms.setdefault(group_id, {})
            was_absent = connection.user_id not in room
            room.setdefault(connection.user_id, set()).add(connection)
            if was_absent:
                newly_online.append(group_id)

        # Announce only where this user was not already present via another tab.
        for group_id in newly_online:
            await self._broadcast(
                group_id,
                {
                    "type": "presence.join",
                    "group_id": group_id,
                    "user_id": connection.user_id,
                    "username": connection.username,
                },
                exclude=connection,
            )

        return {gid: self.presence(gid) for gid in connection.group_ids}

    async def disconnect(self, connection: Connection) -> None:
        """Deregister a socket and announce departure if it was the user's last.

        Safe to call more than once for the same connection — the socket may be
        torn down from both the read loop and an errored send.
        """
        went_offline: list[int] = []
        for group_id in connection.group_ids:
            room = self._rooms.get(group_id)
            if room is None:
                continue
            sockets = room.get(connection.user_id)
            if sockets is None:
                continue

            sockets.discard(connection)
            if not sockets:
                del room[connection.user_id]
                went_offline.append(group_id)
            if not room:
                del self._rooms[group_id]

        for group_id in went_offline:
            await self._broadcast(
                group_id,
                {
                    "type": "presence.leave",
                    "group_id": group_id,
                    "user_id": connection.user_id,
                },
            )

    # ==================== PRESENCE ====================

    def presence(self, group_id: int) -> list[dict]:
        """Who is currently online in a group. Pure in-memory read, no DB."""
        room = self._rooms.get(group_id, {})
        members = [
            {"user_id": user_id, "username": next(iter(sockets)).username}
            for user_id, sockets in room.items()
            if sockets
        ]
        return sorted(members, key=lambda m: m["user_id"])

    def is_online(self, group_id: int, user_id: int) -> bool:
        return bool(self._rooms.get(group_id, {}).get(user_id))

    def connection_count(self) -> int:
        """Total open sockets — used by the health endpoint and tests."""
        return sum(len(sockets) for room in self._rooms.values() for sockets in room.values())

    # ==================== FANOUT ====================

    async def _broadcast(
        self, group_id: int, payload: dict, *, exclude: Connection | None = None
    ) -> None:
        """Send a payload to every socket in a room.

        Sends run concurrently so one slow client cannot serialise the others,
        and a failed send takes only its own socket down. If this ever needs to
        tolerate genuinely slow consumers, the upgrade is a bounded per-socket
        queue with a writer task — unnecessary at the scale this serves.
        """
        room = self._rooms.get(group_id)
        if not room:
            return

        targets = [conn for sockets in room.values() for conn in sockets if conn is not exclude]
        if not targets:
            return

        results = await asyncio.gather(
            *(conn.websocket.send_json(payload) for conn in targets),
            return_exceptions=True,
        )

        # Reap sockets that failed to accept the write. Their read loop will
        # usually also be unwinding; disconnect() tolerates the double call.
        for conn, result in zip(targets, results, strict=True):
            if isinstance(result, Exception):
                logger.info("Dropping chat socket for user %s: %s", conn.user_id, result)
                await self.disconnect(conn)

    def broadcast_from_thread(self, group_id: int, payload: dict) -> None:
        """Schedule a broadcast from a synchronous request handler.

        Route handlers in this app are sync ``def``, so they run in a threadpool
        rather than on the event loop and cannot await ``_broadcast`` directly.
        This hands the coroutine back to the loop and returns immediately: the
        HTTP response is never held up by fanout, and a fanout failure is logged
        rather than surfaced as a failed write to the client whose message was
        already committed.
        """
        if self._loop is None:
            # No socket has ever connected in this process, so there is nobody
            # to broadcast to. Not an error.
            return

        future = asyncio.run_coroutine_threadsafe(self._broadcast(group_id, payload), self._loop)

        def _log_failure(fut: object) -> None:
            try:
                fut.result()  # type: ignore[attr-defined]
            except Exception:  # pragma: no cover - defensive
                logger.exception("Chat broadcast to group %s failed", group_id)

        future.add_done_callback(_log_failure)


# Module-level singleton. One process, one registry.
manager = ConnectionManager()
