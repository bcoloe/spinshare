"""Album and review schema definitions for backend APIs."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AlbumSearchResult(BaseModel):
    spotify_album_id: str
    title: str
    artist: str
    release_date: str | None = None
    cover_url: str | None = None
    genres: list[str] = []


class GroupAlbumStatus(StrEnum):
    Pending = "pending"
    Selected = "selected"


# ==================== ALBUM ====================


class AlbumBase(BaseModel):
    spotify_album_id: str
    title: str
    artist: str
    release_date: str | None = None
    cover_url: str | None = None


class AlbumCreate(AlbumBase):
    genres: list[str] = []


class AlbumResponse(AlbumBase):
    id: int
    added_at: datetime
    genres: list[str] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_genres(cls, album) -> "AlbumResponse":
        return cls(
            id=album.id,
            spotify_album_id=album.spotify_album_id,
            title=album.title,
            artist=album.artist,
            release_date=album.release_date,
            cover_url=album.cover_url,
            added_at=album.added_at,
            genres=[g.name for g in album.genres],
        )


# ==================== GROUP ALBUM ====================


class GroupAlbumCreate(BaseModel):
    album_id: int


class GroupAlbumStatusUpdate(BaseModel):
    status: GroupAlbumStatus


class GroupAlbumResponse(BaseModel):
    id: int
    group_id: int
    album_id: int
    added_by: int
    status: str
    added_at: datetime
    selected_date: datetime | None = None
    album: AlbumResponse
    nomination_count: int = 1
    nominator_user_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm(cls, ga) -> "GroupAlbumResponse":
        return cls(
            id=ga.id,
            group_id=ga.group_id,
            album_id=ga.album_id,
            added_by=ga.added_by,
            status=ga.status,
            added_at=ga.added_at,
            selected_date=ga.selected_date,
            album=AlbumResponse.from_orm_with_genres(ga.albums),
            nomination_count=getattr(ga, "nomination_count", 1),
            nominator_user_ids=getattr(ga, "nominator_user_ids", [ga.added_by]),
        )


# ==================== REVIEW ====================


class ReviewCreate(BaseModel):
    rating: float = Field(..., ge=0, le=10)
    comment: str | None = None


class ReviewUpdate(BaseModel):
    rating: float | None = Field(None, ge=0, le=10)
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: int
    album_id: int
    user_id: int
    rating: float
    comment: str | None = None
    reviewed_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
