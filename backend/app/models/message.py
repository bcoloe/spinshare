"""Group chat message table definitions."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Message(Base):
    """A chat message posted to a group's room.

    Deletion is soft (``deleted_at``) so a removed message leaves a tombstone
    rather than a hole in the conversation. ``user_id`` is nullable with
    ``ON DELETE SET NULL`` for the same reason: when an author deletes their
    account the message survives and renders as "[deleted user]".
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    # Bumped by every reaction change, inside the same transaction, so clients
    # can tell a newer reaction aggregate from a late-arriving older one.
    reactions_version = Column(Integer, nullable=False, server_default="0")

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    group = relationship("Group")
    mentions = relationship(
        "MessageMention", back_populates="message", cascade="all, delete-orphan"
    )
    # Ordered by id so reaction chips keep a stable, first-reacted-first order.
    reactions = relationship(
        "MessageReaction",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageReaction.id",
    )

    __table_args__ = (
        # Every read is "the newest N messages in this group", optionally paged
        # backwards by id — this index serves both directions of that query.
        Index("ix_messages_group_id_id", "group_id", "id"),
    )


class MessageMention(Base):
    """A resolved ``@username`` inside a message.

    Rows are only ever created for usernames that resolved to a *member of the
    same group* at write time, so this table doubles as the authorization
    record for who was legitimately pinged.
    """

    __tablename__ = "message_mentions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(
        Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Denormalised so the client can render the mention span without a join or
    # a second lookup, and so it still renders after the user is deleted.
    username = Column(String, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="mentions")
    user = relationship("User", foreign_keys=[user_id])


class MessageReaction(Base):
    """One user's emoji reaction to a message.

    A user may react to a message with several different emoji, but with each
    one only once — the unique constraint makes adding a reaction idempotent.
    """

    __tablename__ = "message_reactions"

    id = Column(Integer, primary_key=True, index=True)
    # No separate index: unique_message_user_reaction is message_id-leading, so
    # it already serves "all reactions on these messages".
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emoji = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    message = relationship("Message", back_populates="reactions")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="unique_message_user_reaction"),
    )
