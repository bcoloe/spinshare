# backend/app/routers/messages.py

from app.dependencies import get_current_user, get_message_service
from app.models import User
from app.realtime.connection_manager import manager
from app.schemas.message import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    ChatTicketResponse,
    MessageCreate,
    MessageResponse,
    PresenceMember,
)
from app.services.message_service import MessageService, serialize_message
from app.utils.security import CHAT_TICKET_EXPIRE_SECONDS, create_chat_ticket
from fastapi import APIRouter, Depends, Query, status

router = APIRouter(tags=["messages"])


@router.get("/groups/{group_id}/messages", response_model=list[MessageResponse])
def get_messages(
    group_id: int,
    before: int | None = Query(None, description="Return messages older than this id"),
    after: int | None = Query(None, description="Return messages newer than this id"),
    limit: int = Query(DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Chat history for a group, oldest-first.

    Serves three callers: first paint, backwards scrollback (``before``), and
    the delta poll the client falls back to when its socket is unavailable
    (``after``).
    """
    messages = message_service.get_history(
        group_id, current_user, before=before, after=after, limit=limit
    )
    return [serialize_message(m) for m in messages]


@router.post(
    "/groups/{group_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_message(
    group_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Post a chat message.

    Writes go over REST rather than through the socket: this keeps the handler a
    plain sync route with the app's normal auth, validation and testing shape,
    and leaves the socket a receive-only channel that touches no database.
    Fanout happens after the commit and never blocks the response.
    """
    message = message_service.create_message(group_id, current_user, data)
    payload = serialize_message(message)
    manager.broadcast_from_thread(
        group_id, {"type": "message.new", "message": payload.model_dump(mode="json")}
    )
    return payload


@router.delete("/messages/{message_id}", response_model=MessageResponse)
def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Soft-delete a message. Author, group admin, or group owner."""
    message = message_service.delete_message(message_id, current_user)
    payload = serialize_message(message)
    manager.broadcast_from_thread(
        message.group_id,
        {"type": "message.deleted", "message": payload.model_dump(mode="json")},
    )
    return payload


@router.post("/groups/{group_id}/chat/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_chat_seen(
    group_id: int,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Clear unread @mention notifications for a group whose chat is on screen.

    The client calls this when the chat panel is open and visible, so mentions
    the user has demonstrably already read never pile up in the notification
    bell. Idempotent — clearing nothing is a normal, successful outcome.
    """
    message_service.mark_mentions_seen(group_id, current_user)


@router.get("/groups/{group_id}/presence", response_model=list[PresenceMember])
def get_presence(
    group_id: int,
    current_user: User = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Who is online in a group right now.

    Read straight out of the in-process socket registry — no database query. The
    socket pushes join/leave deltas, so clients only need this as a fallback for
    when they could not open a socket at all.
    """
    message_service.require_membership(current_user.id, group_id)
    return manager.presence(group_id)


@router.post("/chat/ticket", response_model=ChatTicketResponse)
def create_ticket(current_user: User = Depends(get_current_user)):
    """Exchange a normal authenticated request for a short-lived socket ticket.

    The browser WebSocket API cannot set an Authorization header, so the
    credential has to ride in the URL where nginx will log it. This one expires
    in 30 seconds and opens nothing but a socket.
    """
    return ChatTicketResponse(
        ticket=create_chat_ticket(current_user.id),
        expires_in=CHAT_TICKET_EXPIRE_SECONDS,
    )
