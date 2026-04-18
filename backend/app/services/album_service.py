"""Album and group album service."""

from app.models import Album, Group, GroupAlbum, User
from app.models.genre import Genre
from app.schemas.album import AlbumCreate, GroupAlbumStatus, GroupAlbumStatusUpdate
from app.services import group_service as gs
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class AlbumService:
    """Service layer for Album and GroupAlbum operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== CREATE ====================

    def create_album(self, data: AlbumCreate) -> Album:
        """Register a new album. Idempotent on spotify_album_id.

        Raises:
            HTTPException 409: If spotify_album_id already registered.
        """
        existing = self.get_album_by_spotify_id(data.spotify_album_id, raise_on_missing=False)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Album with Spotify ID '{data.spotify_album_id}' already registered",
            )
        return self._persist_album(data)

    def get_or_create_album(self, data: AlbumCreate) -> Album:
        """Return existing album by Spotify ID or create a new one."""
        existing = self.get_album_by_spotify_id(data.spotify_album_id, raise_on_missing=False)
        if existing:
            return existing
        return self._persist_album(data)

    def _persist_album(self, data: AlbumCreate) -> Album:
        genres = self._get_or_create_genres(data.genres)
        album = Album(
            spotify_album_id=data.spotify_album_id,
            title=data.title,
            artist=data.artist,
            release_date=data.release_date,
            cover_url=data.cover_url,
            genres=genres,
        )
        try:
            self.db.add(album)
            self.db.commit()
            self.db.refresh(album)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Album creation failed due to constraint violation",
            ) from None
        return album

    def _get_or_create_genres(self, names: list[str]) -> list[Genre]:
        genres = []
        for name in names:
            genre = self.db.query(Genre).filter(Genre.name == name.lower()).first()
            if not genre:
                genre = Genre(name=name.lower())
                self.db.add(genre)
                self.db.flush()
            genres.append(genre)
        return genres

    # ==================== NOMINATE ====================

    def nominate_album(self, group_id: int, album_id: int, user: User) -> GroupAlbum:
        """Nominate an album to a group catalog.

        Raises:
            HTTPException 403: If user is not a group member.
            HTTPException 404: If album or group not found.
            HTTPException 409: If album already nominated by this user in this group.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_membership(user.id, group_id)

        self.get_album_by_id(album_id)

        group_album = GroupAlbum(
            group_id=group_id,
            album_id=album_id,
            added_by=user.id,
            status=GroupAlbumStatus.Pending,
        )
        try:
            self.db.add(group_album)
            self.db.commit()
            self.db.refresh(group_album)
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already nominated this album to this group",
            ) from None
        return group_album

    def remove_group_album(self, group_id: int, group_album_id: int, user: User):
        """Remove a nominated album from a group catalog.

        Raises:
            HTTPException 403: If user is not the nominator and not an admin/owner.
            HTTPException 404: If group album not found.
        """
        group_album = self.get_group_album(group_id, group_album_id)
        group_service = gs.GroupService(self.db)

        if group_album.added_by != user.id:
            group_service.require_permission(user.id, group_id, gs.GroupRole.Admin)

        try:
            self.db.delete(group_album)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove album due to existing dependencies",
            ) from None

    def update_group_album_status(
        self, group_id: int, group_album_id: int, update: GroupAlbumStatusUpdate, user: User
    ) -> GroupAlbum:
        """Update group album status (pending → selected → reviewed). Requires Admin or Owner.

        Raises:
            HTTPException 403: If user is not an admin/owner.
            HTTPException 404: If group album not found.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_permission(user.id, group_id, gs.GroupRole.Admin)

        group_album = self.get_group_album(group_id, group_album_id)
        group_album.status = update.status.value
        self.db.commit()
        self.db.refresh(group_album)
        return group_album

    # ==================== GET ====================

    def get_album_by_id(self, album_id: int) -> Album:
        """Get album by primary key.

        Raises:
            HTTPException 404: If album not found.
        """
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Album with id {album_id} not found",
            )
        return album

    def get_album_by_spotify_id(
        self, spotify_album_id: str, *, raise_on_missing: bool = True
    ) -> Album | None:
        """Get album by Spotify album ID.

        Raises:
            HTTPException 404: If raise_on_missing=True and album not found.
        """
        album = self.db.query(Album).filter(Album.spotify_album_id == spotify_album_id).first()
        if not album and raise_on_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Album with Spotify ID '{spotify_album_id}' not found",
            )
        return album

    def get_group_albums(
        self, group_id: int, status_filter: str | None = None
    ) -> list[GroupAlbum]:
        """List all group albums, optionally filtered by status."""
        q = self.db.query(GroupAlbum).filter(GroupAlbum.group_id == group_id)
        if status_filter:
            q = q.filter(GroupAlbum.status == status_filter)
        return q.all()

    def get_group_album(self, group_id: int, group_album_id: int) -> GroupAlbum:
        """Get a specific group album entry.

        Raises:
            HTTPException 404: If not found.
        """
        ga = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.id == group_album_id, GroupAlbum.group_id == group_id)
            .first()
        )
        if not ga:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Album {group_album_id} not found in group {group_id}",
            )
        return ga
