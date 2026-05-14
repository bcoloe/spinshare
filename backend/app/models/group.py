"""Group table definition."""

from enum import StrEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupRole(StrEnum):
    """Enum for group roles"""

    Owner = "owner"
    Admin = "admin"
    Member = "member"

    def __lt__(self, other):
        members = list(GroupRole.__members__.values())
        return members.index(self) < members.index(other)

    def __gt__(self, other):
        members = list(GroupRole.__members__.values())
        return members.index(self) > members.index(other)

    def __ge__(self, other):
        members = list(GroupRole.__members__.values())
        return members.index(self) >= members.index(other)

    def __le__(self, other):
        members = list(GroupRole.__members__.values())
        return members.index(self) <= members.index(other)


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
    name = Column(String, nullable=False)
    is_public = Column(Boolean, nullable=False)
    is_global = Column(Boolean, nullable=False, default=False, server_default="false")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    @hybrid_property
    def name_uniform(self):
        return self.name.lower()

    @name_uniform.expression
    def name_uniform(cls):
        return func.lower(cls.name)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_groups")
    members = relationship("User", secondary=group_members, back_populates="groups")
    albums = relationship("GroupAlbum", back_populates="group", cascade="all, delete-orphan")
    settings = relationship("GroupSettings", back_populates="group", uselist=False, cascade="all, delete-orphan")
    bot_sources = relationship("BotSource", back_populates="group", cascade="all, delete-orphan")
