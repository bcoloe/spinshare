"""Nomination guess table — stores each member's guess for who nominated a selected album."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class NominationGuess(Base):
    __tablename__ = "nomination_guesses"

    id = Column(Integer, primary_key=True, index=True)
    group_album_id = Column(Integer, ForeignKey("group_albums.id", ondelete="CASCADE"), nullable=False)
    guessing_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    guessed_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    correct = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group_album = relationship("GroupAlbum", back_populates="guesses")
    guessing_user = relationship("User", foreign_keys=[guessing_user_id])
    guessed_user = relationship("User", foreign_keys=[guessed_user_id])

    __table_args__ = (
        UniqueConstraint(
            "group_album_id", "guessing_user_id", name="unique_guess_per_user_album"
        ),
    )
