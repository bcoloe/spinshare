"""Group participation tables: per-member priority-pick credits and the credit
ledger that keeps crediting idempotent.

``GroupParticipation`` holds one row per (group, user) with the running credit
balance and the single pending priority pick. ``PriorityReviewCredit`` records
which (group, user, album) triples have already granted a credit, so a review
can earn a credit in every group its album belongs to, but never twice in the
same group.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupParticipation(Base):
    __tablename__ = "group_participation"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credits = Column(Integer, nullable=False, default=0, server_default="0")
    priority_group_album_id = Column(
        Integer, ForeignKey("group_albums.id", ondelete="SET NULL"), nullable=True
    )
    priority_queued_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    priority_group_album = relationship("GroupAlbum", foreign_keys=[priority_group_album_id])

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="unique_participation_per_group"),
    )


class PriorityReviewCredit(Base):
    """Idempotency ledger: one row per (group, user, album) that has granted a credit.

    A member earns a credit for a group either by publishing a review of one of
    the group's albums or by having already reviewed an album at the time it is
    drawn into the group. Both paths insert here first; the unique constraint
    guarantees at most one credit per album per group.
    """

    __tablename__ = "priority_review_credits"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "album_id", name="unique_credit_per_group_album"),
    )
