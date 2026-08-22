"""Schemas for user-submitted reports of bad album links."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.utils.url_parser import MusicService


class ReportableLink(StrEnum):
    """Which of an album's link columns a report is about.

    The four music values are deliberately identical to ``MusicService`` so a
    detected service compares directly against a report's ``link_field`` with no
    translation table. ``TestLinkFieldMapping`` guards that coupling.
    """

    Spotify = "spotify"
    AppleMusic = "apple_music"
    YouTubeMusic = "youtube_music"
    Bandcamp = "bandcamp"
    Wikipedia = "wikipedia"  # not a MusicService — Wikipedia isn't a music service


class ReportReason(StrEnum):
    """Why a link is being reported. Free text is optional detail on top of this."""

    Missing = "missing"
    Bad = "bad"
    Other = "other"


class LinkReportStatus(StrEnum):
    Open = "open"
    Resolved = "resolved"
    Dismissed = "dismissed"


# Album links are flat columns rather than rows, so a report names its column.
LINK_FIELD_TO_COLUMN: dict[ReportableLink, str] = {
    ReportableLink.Spotify: "spotify_album_id",
    ReportableLink.AppleMusic: "apple_music_album_id",
    ReportableLink.YouTubeMusic: "youtube_music_id",
    ReportableLink.Bandcamp: "artist_url",
    ReportableLink.Wikipedia: "wikipedia_url",
}

# Human-facing names, used in notification text and error messages.
LINK_LABELS: dict[ReportableLink, str] = {
    ReportableLink.Spotify: "Spotify",
    ReportableLink.AppleMusic: "Apple Music",
    ReportableLink.YouTubeMusic: "YouTube Music",
    ReportableLink.Bandcamp: "Bandcamp",
    ReportableLink.Wikipedia: "Wikipedia",
}

# The subset of reportable links that store a bare service ID rather than a URL.
ID_BASED_LINKS: dict[ReportableLink, MusicService] = {
    ReportableLink.Spotify: MusicService.Spotify,
    ReportableLink.AppleMusic: MusicService.AppleMusic,
    ReportableLink.YouTubeMusic: MusicService.YouTubeMusic,
}


# How each reason reads inside a notification sentence.
REASON_PHRASES: dict[ReportReason, str] = {
    ReportReason.Missing: "a missing",
    ReportReason.Bad: "a broken",
    ReportReason.Other: "an issue with the",
}


class LinkReportCreate(BaseModel):
    link_field: ReportableLink
    reason_code: ReportReason
    # Optional elaboration. Accepted for any reason, not just "other" — the form
    # only offers it there, but the API stays permissive per the defensive
    # backend / restrictive frontend split.
    reason_detail: str | None = Field(None, max_length=1000)
    suggested_url: str | None = Field(None, max_length=2048)


class LinkReportResolve(BaseModel):
    note: str | None = Field(None, max_length=500)


class LinkReportResponse(BaseModel):
    id: int
    album_id: int
    reporter_id: int | None
    link_field: ReportableLink
    reason_code: ReportReason
    reason_detail: str | None
    suggested_url: str | None
    suggested_value: str | None
    status: LinkReportStatus
    resolved_by: int | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlbumLinksSnapshot(BaseModel):
    """Just enough album context for the admin queue to render a row.

    Deliberately not AlbumResponse — that requires genres, which would add a
    relationship load per row for data the queue never shows.
    """

    id: int
    title: str
    artist: str
    cover_url: str | None = None
    spotify_album_id: str | None = None
    apple_music_album_id: str | None = None
    youtube_music_id: str | None = None
    artist_url: str | None = None
    wikipedia_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AdminLinkReportItem(LinkReportResponse):
    """A queue row: the report plus the context an admin needs to act on it."""

    album: AlbumLinksSnapshot
    reporter_username: str | None = None
    # The album's current value for the reported link, so an admin can see what
    # is being replaced without cross-referencing the snapshot themselves.
    current_value: str | None = None


class LinkReportCountResponse(BaseModel):
    open_count: int
