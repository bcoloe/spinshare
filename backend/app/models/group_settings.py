"""GroupSettings table definition."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
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
    min_role_to_nominate = Column(String, nullable=False, default="member", server_default="member")
    daily_album_count = Column(Integer, nullable=False, default=1, server_default="1")
    allow_guessing = Column(Boolean, nullable=False, default=True, server_default="true")
    guess_user_cap = Column(Integer, nullable=False, default=5, server_default="5")
    chaos_mode = Column(Boolean, nullable=False, default=False, server_default="false")
    daily_nomination_limit = Column(Integer, nullable=True)

    group = relationship("Group", back_populates="settings")
