"""Album table definition."""

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models import genre


class Album(Base):
    __tablename__ = "albums"

    id = Column(Integer, primary_key=True, index=True)
    spotify_album_id = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    release_date = Column(String)
    cover_url = Column(String)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    genres = relationship("Genre", secondary=genre.album_genres, back_populates="albums")
    reviews = relationship("Review", back_populates="albums")
    group_albums = relationship("GroupAlbum", back_populates="albums")
