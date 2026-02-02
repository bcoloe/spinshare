"""Genres table definition."""

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from app.database import Base

# Association table for many-to-many
album_genres = Table(
    "album_genres",
    Base.metadata,
    Column("album_id", Integer, ForeignKey("albums.id")),
    Column("genre_id", Integer, ForeignKey("genres.id")),
)


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    # Relationships
    albums = relationship("Album", secondary=album_genres, back_populates="genres")
