# backend/app/routers/ws.py

"""The chat WebSocket endpoint.

The socket is **receive-only from the client's point of view**: everything the
server pushes originates from a REST write elsewhere, and nothing the client
sends over the socket mutates state. That is deliberate — it keeps this the only
async code path in the backend, and it keeps it free of database access after
the handshake, so an idle socket costs nothing.

The read loop exists solely to notice that the peer has gone away. uvicorn's
protocol-level ping/pong (20 s interval, 20 s timeout by default) closes
half-open connections for us, which is what stops a closed laptop lid from
leaving a ghost user online forever — without any heartbeat reaching the
database.
"""

import logging

from app.database import SessionLocal
from app.realtime.connection_manager import Connection, manager
from app.services.user_service import UserService
from app.utils.security import decode_chat_ticket
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter()

# Close codes. 4001 is in the private-use range and tells the client "your
# credential was bad" — distinct from a transient drop, so the frontend knows to
# fetch a fresh ticket rather than blindly retrying with the same one.
WS_UNAUTHORIZED = 4001


def _load_identity(user_id: int) -> tuple[str, set[int]] | None:
    """Resolve a user's username and group ids.

    The only database work the socket ever does, and it happens once per
    connection rather than once per message. Runs in a threadpool because the
    session is synchronous and would otherwise block the event loop for every
    other connected client.
    """
    db = SessionLocal()
    try:
        user = UserService(db).get_user_by_id(user_id)
        return user.username, {group.id for group in user.groups}
    except Exception:
        return None
    finally:
        db.close()


@router.websocket("/ws/chat")
async def chat_socket(websocket: WebSocket, ticket: str = ""):
    """Open the chat socket for one user across all of their groups.

    A single connection serves every group the user belongs to, so presence dots
    light up across the whole app from one socket rather than one per room.
    """
    payload = decode_chat_ticket(ticket)
    if payload is None or payload.get("sub") is None:
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    identity = await run_in_threadpool(_load_identity, user_id)
    if identity is None:
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    username, group_ids = identity

    await websocket.accept()
    connection = Connection(
        websocket=websocket, user_id=user_id, username=username, group_ids=group_ids
    )

    snapshot = await manager.connect(connection)
    await websocket.send_json(
        {
            "type": "presence.snapshot",
            "user_id": user_id,
            "groups": {str(gid): members for gid, members in snapshot.items()},
        }
    )

    try:
        while True:
            # Anything the client sends is discarded. We read only so that a
            # disconnect raises promptly instead of the socket lingering.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # pragma: no cover - defensive
        logger.exception("Chat socket for user %s failed", user_id)
    finally:
        await manager.disconnect(connection)
