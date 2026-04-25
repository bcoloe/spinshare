"""GroupSettings table definition."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class GroupSettings(Base):
    __tablename__ = "group_settings"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    min_role_to_add_members = Column(String, nullable=False, default="admin", server_default="admin")
    daily_album_count = Column(Integer, nullable=False, default=1, server_default="1")

    group = relationship("Group", back_populates="settings")
