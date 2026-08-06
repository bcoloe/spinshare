"""Group weekly recap table — a frozen per-group, per-week activity snapshot.

The recap is computed once when a week completes and stored as an immutable JSON
blob so subsequent views never change even as albums/reviews keep accumulating.
"""

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupRecap(Base):
    __tablename__ = "group_recaps"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    # Inclusive Monday (group-tz) that starts the recapped week.
    week_start = Column(Date, nullable=False)
    # Exclusive Monday (group-tz) that ends the recapped week (week_start + 7 days).
    week_end = Column(Date, nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Frozen computed payload — see app/schemas/recap.py::RecapData for the shape.
    data = Column(JSON, nullable=False)

    # Relationships
    group = relationship("Group")
    views = relationship("RecapView", back_populates="recap", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("group_id", "week_start", name="unique_group_week_recap"),
    )
