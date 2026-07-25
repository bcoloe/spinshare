"""PublicSpinDraw table definition."""

from sqlalchemy import Column, Date, DateTime, Integer, JSON
from sqlalchemy.sql import func

from app.database import Base


class PublicSpinDraw(Base):
    """One row per calendar day: the shared 3-album draw shown to every
    anonymous visitor that day (landing page + anonymous global-group view)."""

    __tablename__ = "public_spin_draws"

    id = Column(Integer, primary_key=True, index=True)
    draw_date = Column(Date, nullable=False, unique=True, index=True)
    album_ids = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
