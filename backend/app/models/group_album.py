"""Group album table definition."""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, UniqueConstraint, case, exists
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupAlbum(Base):
    __tablename__ = "group_albums"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    selected_date = Column(DateTime(timezone=True), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    is_chaos_selection = Column(Boolean, nullable=False, default=False, server_default="false")
    avg_rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    group = relationship("Group", back_populates="albums")
    albums = relationship("Album", back_populates="group_albums")
    added_by_user = relationship("User", foreign_keys=[added_by], back_populates="added_albums")
    guesses = relationship("NominationGuess", back_populates="group_album", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("group_id", "album_id", "added_by", name="unique_user_album_per_group"),
    )

    @hybrid_property
    def status(self) -> str:
        if self.selected_date is None:
            return "pending"
        if self.albums and self.albums.reviews:
            return "reviewed"
        return "selected"

    @status.expression
    def status(cls):
        from app.models.review import Review  # local import avoids circular dependency
        has_review = exists().where(Review.album_id == cls.album_id)
        return case(
            (cls.selected_date.is_(None), "pending"),
            (has_review, "reviewed"),
            else_="selected",
        )
