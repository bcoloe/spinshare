"""Group table definition."""

from enum import StrEnum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupRole(StrEnum):
    """Enum for group roles"""

    Owner = "owner"
    Admin = "admin"
    Member = "member"


# Association table for many-to-many relationship
group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("groups.id")),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("joined_at", DateTime(timezone=True), server_default=func.now()),
    Column("role", String, nullable=False, server_default=GroupRole.Member.value),
)


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name_uniform = Column(String, index=True)
    name = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_groups")
    members = relationship("User", secondary=group_members, back_populates="groups")
    albums = relationship("GroupAlbum", back_populates="group")
