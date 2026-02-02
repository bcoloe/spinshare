"""Spotify connections table definition."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SpotifyConnection(Base):
    __tablename__ = "spotify_connections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    spotify_user_id = Column(String, unique=True)
    access_token = Column(String, nullable=False)  # Should be encrypted
    refresh_token = Column(String, nullable=False)  # Should be encrypted
    token_expires_at = Column(DateTime(timezone=True))
    last_refreshed_at = Column(DateTime(timezone=True))

    # Relationship
    user = relationship("User", back_populates="spotify_connection")
