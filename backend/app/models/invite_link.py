from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupInviteLink(Base):
    __tablename__ = "group_invite_links"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    group = relationship("Group")
    creator = relationship("User", foreign_keys=[created_by])

    @property
    def group_name(self) -> str:
        return self.group.name

    @property
    def creator_username(self) -> str:
        return self.creator.username
