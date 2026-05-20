"""Album and review schema definitions for backend APIs."""

from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Domains currently whitelisted for artist_url.
_ALLOWED_ARTIST_URL_DOMAINS = {"bandcamp.com"}


class AlbumSearchResult(BaseModel):
    album_id: int | None = None
    spotify_album_id: str | None = None
    apple_music_album_id: str | None = None
    youtube_music_id: str | None = None
    artist_url: str | None = None
    title: str
    artist: str
    release_date: str | None = None
    cover_url: str | None = None
    genres: list[str] = []


class AlbumSearchPage(BaseModel):
    items: list[AlbumSearchResult]
    next_offset: int | None = None


class GroupAlbumStatus(StrEnum):
    Pending = "pending"
    Selected = "selected"


# ==================== ALBUM ====================


class AlbumBase(BaseModel):
    spotify_album_id: str | None = None
    apple_music_album_id: str | None = None
    artist_url: str | None = None
    title: str
    artist: str
    release_date: str | None = None
    cover_url: str | None = None


class AlbumCreate(AlbumBase):
    genres: list[str] = []
    youtube_music_id: str | None = None

    @field_validator("artist_url")
    @classmethod
    def validate_artist_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parsed = urlparse(v)
        except Exception:
            raise ValueError("artist_url must be a valid URL")
        netloc = parsed.netloc.lower()
        domain_ok = any(netloc.endswith("." + d) for d in _ALLOWED_ARTIST_URL_DOMAINS)
        if not domain_ok:
            allowed = ", ".join(sorted(_ALLOWED_ARTIST_URL_DOMAINS))
            raise ValueError(f"artist_url must be from a supported domain: {allowed}")
        if not parsed.path.lower().startswith("/album/"):
            raise ValueError("artist_url must point to an album page (path must start with /album/)")
        return v

    @model_validator(mode="after")
    def at_least_one_service_id(self) -> "AlbumCreate":
        if not any([
            self.spotify_album_id,
            self.apple_music_album_id,
            self.youtube_music_id,
            self.artist_url,
        ]):
            raise ValueError(
                "At least one of spotify_album_id, apple_music_album_id, "
                "youtube_music_id, or artist_url is required"
            )
        return self


class AlbumLinksUpdate(BaseModel):
    """Schema for admin-only album link corrections."""

    spotify_album_id: str | None = None
    apple_music_album_id: str | None = None
    youtube_music_id: str | None = None
    artist_url: str | None = None

    @field_validator("artist_url")
    @classmethod
    def validate_artist_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parsed = urlparse(v)
        except Exception:
            raise ValueError("artist_url must be a valid URL")
        netloc = parsed.netloc.lower()
        domain_ok = any(netloc.endswith("." + d) for d in _ALLOWED_ARTIST_URL_DOMAINS)
        if not domain_ok:
            allowed = ", ".join(sorted(_ALLOWED_ARTIST_URL_DOMAINS))
            raise ValueError(f"artist_url must be from a supported domain: {allowed}")
        if not parsed.path.lower().startswith("/album/"):
            raise ValueError("artist_url must point to an album page (path must start with /album/)")
        return v


class AlbumResponse(AlbumBase):
    id: int
    youtube_music_id: str | None = None
    added_at: datetime
    genres: list[str] = []

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_genres(cls, album) -> "AlbumResponse":
        return cls(
            id=album.id,
            spotify_album_id=album.spotify_album_id,
            apple_music_album_id=album.apple_music_album_id,
            artist_url=album.artist_url,
            title=album.title,
            artist=album.artist,
            release_date=album.release_date,
            cover_url=album.cover_url,
            youtube_music_id=album.youtube_music_id,
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
    avg_rating: float | None = None
    review_count: int = 0

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
            avg_rating=getattr(ga, "avg_rating", None),
            review_count=getattr(ga, "review_count", 0),
        )


# ==================== URL RESOLVE ====================


class AlbumUrlResolveRequest(BaseModel):
    url: str
    artist: str | None = None
    album: str | None = None


# ==================== USER NOMINATION POOL ====================


class UserNominationResponse(BaseModel):
    album: AlbumResponse
    nominated_group_ids: list[int]


# ==================== REVIEW ====================


class ReviewCreate(BaseModel):
    rating: float | None = Field(None, ge=0, le=10)
    comment: str | None = Field(None, max_length=5000)
    is_draft: bool = False

    @model_validator(mode="after")
    def rating_required_when_published(self) -> "ReviewCreate":
        if not self.is_draft and self.rating is None:
            raise ValueError("rating is required when submitting a review")
        return self


class ReviewUpdate(BaseModel):
    rating: float | None = Field(None, ge=0, le=10)
    comment: str | None = Field(None, max_length=5000)
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
