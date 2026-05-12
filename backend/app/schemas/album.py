"""Album and review schema definitions for backend APIs."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    youtube_music_id: str | None = None
    apple_music_url: str | None = None
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
            youtube_music_id=album.youtube_music_id,
            apple_music_url=album.apple_music_url,
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
    added_by: int | None
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
            nominator_user_ids=getattr(ga, "nominator_user_ids", [ga.added_by] if ga.added_by is not None else []),
        )


# ==================== USER NOMINATION POOL ====================


class UserNominationResponse(BaseModel):
    album: AlbumResponse
    nominated_group_ids: list[int]


# ==================== REVIEW ====================


class ReviewCreate(BaseModel):
    rating: float | None = Field(None, ge=0, le=10)
    comment: str | None = None
    is_draft: bool = False

    @model_validator(mode="after")
    def rating_required_when_published(self) -> "ReviewCreate":
        if not self.is_draft and self.rating is None:
            raise ValueError("rating is required when submitting a review")
        return self


class ReviewUpdate(BaseModel):
    rating: float | None = Field(None, ge=0, le=10)
    comment: str | None = None
    is_draft: bool | None = None


class ReviewResponse(BaseModel):
    id: int
    album_id: int
    user_id: int
    rating: float | None
    comment: str | None = None
    is_draft: bool
    reviewed_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AlbumReviewItem(BaseModel):
    """Review enriched with reviewer username, returned from the public album reviews endpoint."""

    id: int
    album_id: int
    user_id: int
    username: str
    first_name: str | None = None
    last_name: str | None = None
    rating: float | None
    comment: str | None = None
    is_draft: bool
    reviewed_at: datetime
    updated_at: datetime | None = None


class HistogramBucket(BaseModel):
    bucket_start: int
    bucket_end: int
    count: int


class AlbumStatsResponse(BaseModel):
    average_rating: float | None
    review_count: int
    histogram: list[HistogramBucket]
