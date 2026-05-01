"""Group album table definition."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Float, nullable=True)
    comment = Column(String, nullable=True)
    is_draft = Column(Boolean, nullable=False, server_default="false")
    reviewed_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    albums = relationship("Album", back_populates="reviews")
    user = relationship("User", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("user_id", "album_id", name="unique_user_album_review"),
        CheckConstraint("rating >= 0 AND rating <= 10", name="valid_rating_range"),
    )
