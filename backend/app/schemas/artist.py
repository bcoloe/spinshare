"""Artist overview schema definitions."""

from pydantic import BaseModel

from app.schemas.album import AlbumResponse


class ArtistAlbumItem(BaseModel):
    """A single nominated album on an artist's overview page."""

    album: AlbumResponse
    nomination_count: int  # distinct users who nominated this album (any group)
    review_count: int
    average_rating: float | None = None
    rating_stddev: float | None = None  # population std dev of this album's ratings


class ArtistOverviewResponse(BaseModel):
    """Aggregate stats for one artist across all of their nominated albums."""

    artist: str
    album_count: int
    total_nominations: int  # sum of per-album distinct-nominator counts
    total_reviews: int
    average_rating: float | None = None  # mean of each album's average (equal weight)
    rating_stddev: float | None = None  # population std dev of the per-album averages (spread across catalog)
    albums: list[ArtistAlbumItem]
