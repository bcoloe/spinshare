# backend/app/models/invitation.py

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupInvitation(Base):
    __tablename__ = "group_invitations"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_email = Column(String, nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    group = relationship("Group")
    inviter = relationship("User", foreign_keys=[invited_by])

    @property
    def status(self) -> str:
        if self.accepted_at is not None:
            return "accepted"
        if self.expires_at < datetime.now(timezone.utc):
            return "expired"
        return "pending"

    @property
    def group_name(self) -> str:
        return self.group.name

    @property
    def inviter_username(self) -> str:
        return self.inviter.username
