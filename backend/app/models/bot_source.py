"""BotSource table definition."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class BotSource(Base):
    __tablename__ = "bot_sources"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    bot_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    processing_state = Column(JSON, nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="bot_sources")
