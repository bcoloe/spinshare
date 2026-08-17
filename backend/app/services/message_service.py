"""Group chat message service."""

import re
from datetime import UTC, datetime

from app.models import Message, MessageMention, User
from app.models.group import GroupRole, group_members
from app.schemas.message import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    MessageCreate,
    MessageMentionResponse,
    MessageResponse,
)
from app.schemas.notification import NotificationType
from app.services.group_service import GroupService
from app.services.notification_service import NotificationService
from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

# Candidate @mention spans. Usernames are stored lowercase and constrained only
# by length (3–50), so this charset is deliberately permissive but bounded — a
# username containing characters outside it simply isn't mentionable by typing.
# The frontend composer inserts usernames from an autocomplete, so the common
# path never depends on a user hand-typing an exotic handle.
MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.\-]{3,50})")

# A single message can only notify this many people, regardless of how many
# handles it contains. Stops "@a @b @c ..." from becoming a notification cannon.
MAX_MENTIONS_PER_MESSAGE = 10


def serialize_message(message: Message) -> MessageResponse:
    """Build the wire representation of a message.

    Shared by the REST responses and the socket payloads so both carry exactly
    the same shape — the client has one message renderer, not two.

    A soft-deleted message keeps its row and its position in the conversation
    but surrenders its body: the tombstone is what gets sent, never the original
    text.
    """
    is_deleted = message.deleted_at is not None
    return MessageResponse(
        id=message.id,
        group_id=message.group_id,
        user_id=message.user_id,
        username=message.user.username if message.user else None,
        body="" if is_deleted else message.body,
        created_at=message.created_at,
        edited_at=message.edited_at,
        is_deleted=is_deleted,
        mentions=(
            []
            if is_deleted
            else [
                MessageMentionResponse(user_id=m.user_id, username=m.username)
                for m in message.mentions
            ]
        ),
    )


class MessageService:
    """Chat persistence and mention resolution.

    Deliberately knows nothing about WebSockets. The router calls this to commit
    a message and *then* hands the result to the connection manager for fanout,
    which keeps this layer synchronous, DB-only, and testable without an event
    loop — matching every other service in the app.
    """

    def __init__(self, db: Session):
        self.db = db
        self.group_service = GroupService(db)
        self.notification_service = NotificationService(db)

    # ==================== CREATE ====================

    def create_message(self, group_id: int, user: User, data: MessageCreate) -> Message:
        """Post a message to a group's chat room.

        Resolves ``@username`` spans against *members of this group only*, records
        them, and notifies each mentioned user.

        Raises:
            HTTPException 403: If the user is not a member of the group
            HTTPException 404: If the group does not exist
        """
        self.group_service.get_group_by_id(group_id)  # 404s if missing
        self.group_service.require_membership(user.id, group_id)

        message = Message(group_id=group_id, user_id=user.id, body=data.body)
        self.db.add(message)
        self.db.flush()  # assign message.id before building mention rows

        mentioned = self._resolve_mentions(data.body, group_id, exclude_user_id=user.id)
        for target in mentioned:
            self.db.add(
                MessageMention(
                    message_id=message.id,
                    user_id=target.id,
                    username=target.username,
                )
            )

        self.db.commit()
        self.db.refresh(message)

        # Notifications are created after the commit so a failure to notify can
        # never roll back the message itself.
        for target in mentioned:
            self.notification_service.create(
                user_id=target.id,
                type=NotificationType.mentioned_in_chat,
                message=f"{user.username} mentioned you in chat",
                group_id=group_id,
            )

        return message

    def _resolve_mentions(self, body: str, group_id: int, *, exclude_user_id: int) -> list[User]:
        """Resolve ``@handles`` in ``body`` to users who are members of ``group_id``.

        Non-members, unknown handles, and self-mentions resolve to nothing — an
        unresolvable handle stays inert text. This is the whole ping-authorization
        boundary: a user can never be notified by a message in a group they are
        not in, no matter what the client sends.
        """
        handles = {h.lower() for h in MENTION_PATTERN.findall(body)}
        if not handles:
            return []

        stmt = (
            select(User)
            .join(group_members, group_members.c.user_id == User.id)
            .where(
                group_members.c.group_id == group_id,
                User.username.in_(handles),
                User.id != exclude_user_id,
            )
            .order_by(User.id)
            .limit(MAX_MENTIONS_PER_MESSAGE)
        )
        return list(self.db.scalars(stmt).all())

    # ==================== READ ====================

    def require_membership(self, user_id: int, group_id: int) -> None:
        """Assert the user may see this group's chat room.

        Exposed here so callers that need the gate without touching messages —
        the presence endpoint, which reads from memory rather than the DB — do
        not have to reach through this service into GroupService.

        Raises:
            HTTPException 403: If the user is not a member of the group
        """
        self.group_service.require_membership(user_id, group_id)

    def get_history(
        self,
        group_id: int,
        user: User,
        *,
        before: int | None = None,
        after: int | None = None,
        limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> list[Message]:
        """Return messages for a group, oldest-first.

        ``before`` pages backwards for scrollback; ``after`` fetches the delta
        since a known message id, which is what the polling fallback uses when
        the socket is unavailable.

        Raises:
            HTTPException 403: If the user is not a member of the group
            HTTPException 404: If the group does not exist
        """
        self.group_service.get_group_by_id(group_id)
        self.group_service.require_membership(user.id, group_id)

        limit = max(1, min(limit, MAX_HISTORY_LIMIT))

        stmt = (
            select(Message)
            .options(selectinload(Message.mentions), selectinload(Message.user))
            .where(Message.group_id == group_id)
        )
        if before is not None:
            stmt = stmt.where(Message.id < before)
        if after is not None:
            stmt = stmt.where(Message.id > after)

        # Take the newest `limit` rows, then flip to chronological order so the
        # client can append without re-sorting.
        stmt = stmt.order_by(Message.id.desc()).limit(limit)
        rows = list(self.db.scalars(stmt).all())
        rows.reverse()
        return rows

    def get_message(self, message_id: int) -> Message:
        """Fetch a single message.

        Raises:
            HTTPException 404: If the message does not exist
        """
        message = self.db.scalars(
            select(Message)
            .options(selectinload(Message.mentions), selectinload(Message.user))
            .where(Message.id == message_id)
        ).first()
        if message is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        return message

    def unread_counts(self, user: User) -> dict[int, int]:
        """Unread message counts per group for one user.

        Counts messages newer than the reader's marker, from anyone but
        themselves, that still exist. Returned as a mapping so the caller can
        ask about any of the user's groups from a single query rather than one
        request per group.

        Groups with nothing unread are omitted entirely.
        """
        stmt = (
            select(Message.group_id, func.count(Message.id))
            .join(group_members, group_members.c.group_id == Message.group_id)
            .where(
                group_members.c.user_id == user.id,
                # is_distinct_from, not !=: a message whose author deleted their
                # account has a null user_id, and `null != me` is null, which
                # would silently drop it from the count.
                Message.user_id.is_distinct_from(user.id),
                Message.deleted_at.is_(None),
                # A null marker means the member joined an empty room, so
                # everything since counts. Joining a room that already had
                # history starts the marker at its newest message instead —
                # see GroupService._start_chat_read_marker.
                Message.id > func.coalesce(group_members.c.last_read_message_id, 0),
            )
            .group_by(Message.group_id)
        )
        return {group_id: count for group_id, count in self.db.execute(stmt).all()}

    # ==================== UPDATE ====================

    def mark_chat_seen(
        self, group_id: int, user: User, last_message_id: int | None = None
    ) -> int:
        """Record that the user is looking at a group's chat.

        Does two things that always belong together: advances their read marker
        so the unread badge clears, and retires the mention notifications that
        were pointing them here. A mention is a pointer to a message; once they
        are reading the conversation the pointer has served its purpose, and
        leaving it in the bell just makes them dismiss what they have read.

        Only ``mentioned_in_chat`` notifications are touched — sitting in chat
        never clears a review or invitation notification for the same group.

        Raises:
            HTTPException 403: If the user is not a member of the group

        Returns:
            How many notifications were still unread and got cleared.
        """
        self.group_service.require_membership(user.id, group_id)

        if last_message_id is not None:
            self.db.execute(
                update(group_members)
                .where(
                    group_members.c.group_id == group_id,
                    group_members.c.user_id == user.id,
                    # Only ever forwards. Two tabs, or a second device that has
                    # read further, must not be able to rewind the marker and
                    # resurrect messages the user has already seen.
                    func.coalesce(group_members.c.last_read_message_id, 0)
                    < last_message_id,
                )
                .values(last_read_message_id=last_message_id)
            )
            self.db.commit()

        return self.notification_service.mark_read_for_group(
            user, group_id, NotificationType.mentioned_in_chat
        )

    # ==================== DELETE ====================

    def delete_message(self, message_id: int, user: User) -> Message:
        """Soft-delete a message.

        Permitted for the author, and for group owners/admins so public groups
        have a moderation path. The row is retained with ``deleted_at`` set so
        the conversation keeps its shape.

        Raises:
            HTTPException 403: If the user may not delete this message
            HTTPException 404: If the message does not exist
        """
        message = self.get_message(message_id)

        if message.user_id != user.id:
            # Not the author — fall back to group moderator rights.
            self.group_service.require_permission(user.id, message.group_id, GroupRole.Admin)

        if message.deleted_at is None:
            message.deleted_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(message)

        return message
