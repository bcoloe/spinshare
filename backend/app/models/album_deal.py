"""Album deal table — per-member album draws in dealer-mode groups.

Deal lifecycle (per user, per group):
  - revealed_at IS NULL     → queued: pre-drawn as part of the day's allotment, not yet shown
  - revealed_at IS NOT NULL → dealt: surfaced to the user; part of their personal history

Deals reference album_id (not group_album_id) so they survive nomination-row churn,
mirroring how reviews are album-keyed.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class AlbumDeal(Base):
    __tablename__ = "album_deals"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    dealt_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revealed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "album_id", name="unique_deal_per_user_album"),
        Index("ix_album_deals_group_user", "group_id", "user_id"),
        Index("ix_album_deals_group_album", "group_id", "album_id"),
    )
