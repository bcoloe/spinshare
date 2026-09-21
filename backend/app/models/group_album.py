"""Group album table definition."""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, UniqueConstraint, case, exists
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import query_expression, relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupAlbum(Base):
    __tablename__ = "group_albums"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False, index=True)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    selected_date = Column(DateTime(timezone=True), nullable=True, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    is_chaos_selection = Column(Boolean, nullable=False, default=False, server_default="false")
    avg_rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    group = relationship("Group", back_populates="albums")
    albums = relationship("Album", back_populates="group_albums")
    added_by_user = relationship("User", foreign_keys=[added_by], back_populates="added_albums")
    guesses = relationship("NominationGuess", back_populates="group_album", cascade="all, delete-orphan")

    # unique_user_album_per_group is group_id-leading, so it indexes group_id and
    # nothing else on its own; album_id, added_by and the selected_date IS NULL
    # nomination-pool scan each need their own index (declared on the columns).
    __table_args__ = (
        UniqueConstraint("group_id", "album_id", "added_by", name="unique_user_album_per_group"),
    )

    # Optional loader slot for the "does this album have any review?" boolean that
    # ``status`` needs. List queries populate it with ``with_expression`` (see
    # ``has_reviews_expression``) so serializing a page of rows does not drag every
    # review row along just to derive a string. It is None when a query did not
    # request it, and ``status`` then falls back to the relationship.
    has_reviews = query_expression()

    @hybrid_property
    def status(self) -> str:
        if self.selected_date is None:
            return "pending"
        loaded = self.__dict__.get("has_reviews")
        has_reviews = bool(self.albums and self.albums.reviews) if loaded is None else loaded
        return "reviewed" if has_reviews else "selected"

    @status.expression
    def status(cls):
        return case(
            (cls.selected_date.is_(None), "pending"),
            (has_reviews_expression(cls), "reviewed"),
            else_="selected",
        )


def has_reviews_expression(entity=None):
    """Scalar EXISTS: does this group album's album have any review at all?

    The single source of truth for the review check inside ``GroupAlbum.status`` —
    used both by the SQL-side hybrid expression and by ``with_expression`` loaders
    that pre-compute ``GroupAlbum.has_reviews`` for list queries.

    ``review_count`` on this table is deliberately NOT used here: it counts only
    published, rated reviews by *current members of the group*, is left at 0 for
    rows created before it existed (its migration adds the column with a 0 default
    and no backfill) and for rows created after a review already existed, and is
    only recomputed when a review is written. It answers a different question.
    """
    from app.models.review import Review  # local import avoids circular dependency

    target = entity if entity is not None else GroupAlbum
    return exists().where(Review.album_id == target.album_id)
