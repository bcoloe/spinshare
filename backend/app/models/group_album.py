"""Group album table definition."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class GroupAlbum(Base):
    __tablename__ = "group_albums"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    album_id = Column(Integer, ForeignKey("albums.id"), nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")
    selected_date = Column(DateTime(timezone=True), nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group = relationship("Group", back_populates="group_albums")
    albums = relationship("Album", back_populates="group_albums")
    added_by_user = relationship("User", foreign_keys=[added_by], back_populates="added_albums")

    __table_args__ = (
        UniqueConstraint("group_id", "album_id", "added_by", name="unique_user_album_per_group"),
    )
