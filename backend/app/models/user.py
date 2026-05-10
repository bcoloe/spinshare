"""User table definition."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.database import Base
from app.models import group


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String(50), nullable=True)
    password_hash = Column(String, nullable=False)
    is_bot = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    spotify_connection = relationship("SpotifyConnection", back_populates="user", uselist=False)
    groups = relationship("Group", secondary=group.group_members, back_populates="members")
    created_groups = relationship(
        "Group", foreign_keys="Group.created_by", back_populates="creator"
    )
    reviews = relationship("Review", back_populates="user")
    added_albums = relationship(
        "GroupAlbum", foreign_keys="GroupAlbum.added_by", back_populates="added_by_user"
    )

    # Validations
    @validates("email")
    def convert_lower(self, key, value):
        return value.lower() if value else value

    @validates("username")
    def convert_lower_username(self, key, value):
        return value.lower() if value else value
