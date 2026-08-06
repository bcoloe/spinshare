"""Recap view table — records that a user has seen a given weekly recap.

Presence of a row marks the recap as "seen" for that user, which suppresses the
login pop-up. Server-side so a dismissal on any device applies everywhere.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class RecapView(Base):
    __tablename__ = "recap_views"

    id = Column(Integer, primary_key=True, index=True)
    recap_id = Column(Integer, ForeignKey("group_recaps.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    recap = relationship("GroupRecap", back_populates="views")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("recap_id", "user_id", name="unique_recap_view_per_user"),
    )
