"""Chat message schemas."""

import unicodedata
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

MAX_MESSAGE_LENGTH = 2000
MAX_HISTORY_LIMIT = 100
# One screen's worth of scrollback. Chat opens on the most recent conversation
# and pages backwards on demand rather than loading a room's whole history —
# which for an old group would be a large query nobody asked for. Clients send
# `limit` explicitly, so this is the floor for a caller that omits it.
DEFAULT_HISTORY_LIMIT = 30

# Longest emoji the reaction picker can produce is a ZWJ family/flag sequence of
# roughly a dozen code points; anything far beyond that is not a single emoji.
MAX_REACTION_LENGTH = 16
# How many *different* emoji one user may put on one message.
MAX_REACTIONS_PER_USER = 10
# ASCII is allowed only as the base of a keycap sequence (1️⃣, #️⃣, *️⃣).
_KEYCAP_BASES = set("0123456789#*")
_KEYCAP = "\u20e3"
# The non-symbol code points emoji sequences are built from — and nothing else:
# zero-width joiner, variation selectors, the keycap mark, and the tag
# characters of subdivision flags. Other combining marks would stack over
# neighbouring text, and other format characters (bidi overrides) reorder it.
_EMOJI_JOINERS = (
    {"\u200d", _KEYCAP}
    | {chr(c) for c in range(0xFE00, 0xFE10)}
    | {chr(c) for c in range(0xE0020, 0xE0080)}
)


def validate_reaction_emoji(value: str) -> str:
    """Accept a single emoji-like token; reject text and whitespace.

    Not a full emoji grammar — that would need a Unicode data dependency — but
    tight enough that a reaction can only ever render as a glyph or two, never
    as words or as marks spilling onto neighbouring text: bounded length, and
    every code point is a symbol (including skin-tone modifiers), a keycap base,
    or one of the joiners emoji sequences are built from — with at least one
    symbol present.

    Raises:
        ValueError: If the value is not emoji-shaped
    """
    if not 1 <= len(value) <= MAX_REACTION_LENGTH:
        raise ValueError("Reaction must be a single emoji")
    has_symbol = False
    for ch in value:
        category = unicodedata.category(ch)
        if category in ("So", "Sk") or ch == _KEYCAP:
            has_symbol = True
        elif ch not in _KEYCAP_BASES and ch not in _EMOJI_JOINERS:
            raise ValueError("Reaction must be a single emoji")
    if not has_symbol:
        raise ValueError("Reaction must be a single emoji")
    return value


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


class MessageUpdate(MessageCreate):
    """Replacement body for an edited message — validated exactly like a new one."""


class MessageMentionResponse(BaseModel):
    """A resolved mention span within a message body.

    The client renders links from this list and never re-parses the body text
    itself — that keeps mention rendering off arbitrary user input.
    """

    user_id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


# A validated reaction emoji; used for both the request body and the DELETE
# path parameter, so either rejects a non-emoji with the same 422.
ReactionEmoji = Annotated[str, AfterValidator(validate_reaction_emoji)]


class ReactionCreate(BaseModel):
    """Inbound reaction."""

    emoji: ReactionEmoji


class MessageReactionSummary(BaseModel):
    """Everyone who reacted to a message with one emoji."""

    emoji: str
    count: int
    user_ids: list[int]


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
    # In first-reacted order. Empty on a deleted message.
    reactions: list[MessageReactionSummary]

    model_config = ConfigDict(from_attributes=True)


class MessageReactionsResponse(BaseModel):
    """A message's full reaction state after a change.

    Returned by the reaction endpoints and pushed as ``message.reactions``. It is
    the whole aggregate rather than a delta, so applying it twice, or out of
    order with another client's change, still converges.
    """

    message_id: int
    group_id: int
    reactions: list[MessageReactionSummary]


class ChatSeenRequest(BaseModel):
    """How far the client has read in a group's chat.

    Optional: a caller that only wants to clear mention notifications — or that
    is looking at an empty room — can omit it and leave the marker alone.
    """

    last_message_id: int | None = Field(None, ge=1)


class GroupUnread(BaseModel):
    """Unread message count for one group. Only non-zero groups are returned."""

    group_id: int
    count: int


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
