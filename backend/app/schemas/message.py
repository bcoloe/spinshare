"""Chat message schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_LIMIT = 100
# One screen's worth of scrollback. Chat opens on the most recent conversation
# and pages backwards on demand rather than loading a room's whole history —
# which for an old group would be a large query nobody asked for. Clients send
# `limit` explicitly, so this is the floor for a caller that omits it.
DEFAULT_HISTORY_LIMIT = 30


class MessageCreate(BaseModel):
    """Inbound chat message."""

    body: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        # Reject whitespace-only bodies, and normalise trailing whitespace so
        # "  hi  " and "hi" are stored identically.
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty")
        return stripped


class MessageMentionResponse(BaseModel):
    """A resolved mention span within a message body.

    The client renders links from this list and never re-parses the body text
    itself — that keeps mention rendering off arbitrary user input.
    """

    user_id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """A chat message as returned by the API and pushed over the socket."""

    id: int
    group_id: int
    user_id: int | None
    # None once the author deletes their account; the client renders
    # "[deleted user]" rather than dropping the message.
    username: str | None
    body: str
    created_at: datetime
    edited_at: datetime | None
    is_deleted: bool
    mentions: list[MessageMentionResponse]

    model_config = ConfigDict(from_attributes=True)


class PresenceMember(BaseModel):
    """A user currently holding an open socket."""

    user_id: int
    username: str


class ChatTicketResponse(BaseModel):
    """Short-lived credential redeemed when opening the WebSocket.

    The browser WebSocket API cannot set an Authorization header, and putting
    the real access token in the query string would leak it into nginx access
    logs. This ticket is single-use-ish (30 s TTL) and carries no other rights.
    """

    ticket: str
    expires_in: int
