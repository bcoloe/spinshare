"""Schemas for the Explore feature (platform-wide album/group/stats browsing)."""

from datetime import datetime

from pydantic import BaseModel


# ==================== ALBUMS ====================


class ExploreAlbumItem(BaseModel):
    id: int
    spotify_album_id: str | None
    title: str
    artist: str
    artist_url: str | None
    cover_url: str | None
    release_date: str | None
    avg_rating: float | None
    review_count: int
    nomination_count: int
    weighted_score: float | None


class ExploreAlbumsPage(BaseModel):
    items: list[ExploreAlbumItem]
    next_offset: int | None = None


# ==================== GROUPS ====================


class ExploreGroupItem(BaseModel):
    id: int
    name: str
    is_public: bool
    is_global: bool
    member_count: int
    created_at: datetime


class ExploreGroupsPage(BaseModel):
    items: list[ExploreGroupItem]
    next_offset: int | None = None


# ==================== STATS ====================


class ArtistNominationItem(BaseModel):
    artist: str
    artist_url: str | None
    nomination_count: int
    unique_albums: int


class SiteStatsResponse(BaseModel):
    total_albums_nominated: int
    total_reviews: int
    total_active_groups: int
    total_active_members: int
    top_rated_albums: list[ExploreAlbumItem]
    bottom_rated_albums: list[ExploreAlbumItem]
    most_nominated_artists: list[ArtistNominationItem]
    most_nominated_albums: list[ExploreAlbumItem]
