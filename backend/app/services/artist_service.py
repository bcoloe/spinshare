"""Artist overview service — aggregates an artist's nominated albums."""

import statistics

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import Album, GroupAlbum
from app.models.review import Review
from app.schemas.album import AlbumResponse
from app.schemas.artist import ArtistAlbumItem, ArtistOverviewResponse


class ArtistService:
    """Service layer for artist-level aggregates across nominated albums."""

    def __init__(self, db: Session):
        self.db = db

    def get_artist_overview(self, artist_name: str) -> ArtistOverviewResponse:
        """Return aggregate stats for an artist across all of their nominated albums.

        Only albums with at least one nomination in some group are included. For each
        album the nomination count is the number of distinct users who nominated it.
        The artist-level average is the mean of each album's own average (equal weight),
        counting only albums that have at least one published rating.

        Raises:
            HTTPException 404: If the artist has no nominated albums.
        """
        name = artist_name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artist not found",
            )

        # Distinct albums by this artist that have been nominated at least once.
        albums = (
            self.db.query(Album)
            .join(GroupAlbum, GroupAlbum.album_id == Album.id)
            .filter(func.lower(Album.artist) == name.lower())
            .options(selectinload(Album.genres))
            .distinct()
            .all()
        )
        if not albums:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No nominated albums found for artist '{artist_name}'",
            )

        album_ids = [a.id for a in albums]

        # Distinct nominators per album (any group), ignoring null nominators.
        nom_rows = (
            self.db.query(
                GroupAlbum.album_id,
                func.count(func.distinct(GroupAlbum.added_by)).label("cnt"),
            )
            .filter(
                GroupAlbum.album_id.in_(album_ids),
                GroupAlbum.added_by.isnot(None),
            )
            .group_by(GroupAlbum.album_id)
            .all()
        )
        nominators_by_album = {album_id: cnt for album_id, cnt in nom_rows}

        # Raw published ratings per album — collected so we can compute both the mean
        # and a population standard deviation (a spread/contentiousness measure) in
        # Python, since the test DB (SQLite) has no native STDDEV aggregate.
        rating_rows = (
            self.db.query(Review.album_id, Review.rating)
            .filter(
                Review.album_id.in_(album_ids),
                Review.is_draft == False,  # noqa: E712
                Review.rating.isnot(None),
            )
            .all()
        )
        ratings_by_album: dict[int, list[float]] = {}
        for album_id, rating in rating_rows:
            ratings_by_album.setdefault(album_id, []).append(rating)

        items: list[ArtistAlbumItem] = []
        album_averages: list[float] = []
        total_nominations = 0
        total_reviews = 0
        for album in albums:
            nomination_count = int(nominators_by_album.get(album.id, 0))
            ratings = ratings_by_album.get(album.id, [])
            avg_value = round(sum(ratings) / len(ratings), 2) if ratings else None
            # Population std dev — 0.0 for a single rating, None when unrated.
            stddev_value = round(statistics.pstdev(ratings), 2) if ratings else None
            items.append(
                ArtistAlbumItem(
                    album=AlbumResponse.from_orm_with_genres(album),
                    nomination_count=nomination_count,
                    review_count=len(ratings),
                    average_rating=avg_value,
                    rating_stddev=stddev_value,
                )
            )
            total_nominations += nomination_count
            total_reviews += len(ratings)
            if avg_value is not None:
                album_averages.append(avg_value)

        # Highest mean score first; unrated albums fall to the bottom, then ordered
        # by nomination count so the list stays stable and useful.
        items.sort(
            key=lambda i: (
                i.average_rating is not None,
                i.average_rating if i.average_rating is not None else 0,
                i.nomination_count,
            ),
            reverse=True,
        )

        artist_average = (
            round(sum(album_averages) / len(album_averages), 2) if album_averages else None
        )
        # Spread across the catalog: population std dev of the per-album averages.
        artist_stddev = round(statistics.pstdev(album_averages), 2) if album_averages else None

        return ArtistOverviewResponse(
            artist=albums[0].artist,
            album_count=len(albums),
            total_nominations=total_nominations,
            total_reviews=total_reviews,
            average_rating=artist_average,
            rating_stddev=artist_stddev,
            albums=items,
        )
