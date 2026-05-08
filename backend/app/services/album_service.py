"""Album and group album service."""

from datetime import datetime, timezone

from app.models import Album, Group, GroupAlbum, User
from app.models.genre import Genre
from app.schemas.album import AlbumCreate, GroupAlbumStatus, GroupAlbumStatusUpdate
from app.services import group_service as gs
from fastapi import HTTPException, status
from sqlalchemy import func
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
        """Return existing album by Spotify ID or create a new one.

        If the album already exists but has no genres and the caller provides some,
        the genres are backfilled so albums registered before the artist-genre fix
        are healed on their next nomination.
        """
        existing = self.get_album_by_spotify_id(data.spotify_album_id, raise_on_missing=False)
        if existing:
            if not existing.genres and data.genres:
                existing.genres = self._get_or_create_genres(data.genres)
                self.db.commit()
                self.db.refresh(existing)
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

        settings = group_service.get_group_settings(group_id)
        group_service.require_permission(
            user.id, group_id, gs.GroupRole(settings.min_role_to_nominate)
        )

        self.get_album_by_id(album_id)

        group_album = GroupAlbum(
            group_id=group_id,
            album_id=album_id,
            added_by=user.id,
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
        """Remove a nomination from a group catalog.

        Admins/owners remove ALL nominations for the album.
        Regular members remove only their own nomination.

        Raises:
            HTTPException 403: If user is not a nominator and not an admin/owner.
            HTTPException 404: If group album not found.
        """
        canonical_ga = self.get_group_album(group_id, group_album_id)
        group_service = gs.GroupService(self.db)

        try:
            group_service.require_permission(user.id, group_id, gs.GroupRole.Admin)
            is_admin = True
        except HTTPException:
            is_admin = False

        if is_admin:
            to_delete = (
                self.db.query(GroupAlbum)
                .filter(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.album_id == canonical_ga.album_id,
                )
                .all()
            )
        else:
            user_ga = (
                self.db.query(GroupAlbum)
                .filter(
                    GroupAlbum.group_id == group_id,
                    GroupAlbum.album_id == canonical_ga.album_id,
                    GroupAlbum.added_by == user.id,
                )
                .first()
            )
            if not user_ga:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not a nominator for this album",
                )
            to_delete = [user_ga]

        try:
            for ga in to_delete:
                self.db.delete(ga)
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
        """Select or deselect an album for all its nominations. Requires Admin or Owner.

        Sets selected_date to now when marking selected; clears it when marking pending.
        The "reviewed" state is derived automatically and cannot be set here.

        Raises:
            HTTPException 403: If user is not an admin/owner.
            HTTPException 404: If group album not found.
        """
        group_service = gs.GroupService(self.db)
        group_service.require_permission(user.id, group_id, gs.GroupRole.Admin)

        canonical_ga = self.get_group_album(group_id, group_album_id)
        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id == canonical_ga.album_id,
            )
            .all()
        )
        new_date = datetime.now(timezone.utc) if update.status == GroupAlbumStatus.Selected else None
        for ga in all_nominations:
            ga.selected_date = new_date
        self.db.commit()
        self.db.refresh(canonical_ga)
        return canonical_ga

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

    def get_todays_albums(self, group_id: int) -> list[GroupAlbum]:
        """Return albums selected for today in this group."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return (
            self.db.query(GroupAlbum)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.status == GroupAlbumStatus.Selected,
                GroupAlbum.selected_date >= today_start,
            )
            .all()
        )

    def get_group_albums(
        self, group_id: int, status_filter: str | None = None
    ) -> list[GroupAlbum]:
        """List group albums unified per album (one entry per unique album with nomination count).

        Multiple nominations for the same album are collapsed into the earliest
        GroupAlbum row (canonical), with nomination_count and nominator_user_ids attached.
        """
        subq = (
            self.db.query(
                GroupAlbum.album_id,
                func.min(GroupAlbum.id).label("canonical_id"),
                func.count(GroupAlbum.id).label("nomination_count"),
            )
            .filter(GroupAlbum.group_id == group_id)
            .group_by(GroupAlbum.album_id)
            .subquery()
        )

        q = (
            self.db.query(GroupAlbum, subq.c.nomination_count)
            .join(subq, GroupAlbum.id == subq.c.canonical_id)
        )
        if status_filter:
            q = q.filter(GroupAlbum.status == status_filter)

        rows = q.all()
        if not rows:
            return []

        # Fetch all nominator IDs grouped by album for this group
        album_ids = [ga.album_id for ga, _ in rows]
        raw = (
            self.db.query(GroupAlbum.album_id, GroupAlbum.added_by)
            .filter(
                GroupAlbum.group_id == group_id,
                GroupAlbum.album_id.in_(album_ids),
            )
            .all()
        )
        nominators_by_album: dict[int, list[int]] = {}
        for album_id, added_by in raw:
            if added_by is not None:
                nominators_by_album.setdefault(album_id, []).append(added_by)

        result = []
        for ga, count in rows:
            ga.nomination_count = count
            ga.nominator_user_ids = nominators_by_album.get(
                ga.album_id, [ga.added_by] if ga.added_by is not None else []
            )
            result.append(ga)
        return result

    def get_my_nominations(self, user_id: int) -> list[tuple]:
        """Return distinct albums the user has nominated, with all nominated group IDs per album.

        Returns a list of (Album, [group_id, ...]) tuples, one entry per unique album.
        """
        all_nominations = (
            self.db.query(GroupAlbum)
            .filter(GroupAlbum.added_by == user_id)
            .all()
        )

        group_ids_by_album: dict[int, list[int]] = {}
        canonical_by_album: dict[int, GroupAlbum] = {}
        for ga in all_nominations:
            group_ids_by_album.setdefault(ga.album_id, []).append(ga.group_id)
            if ga.album_id not in canonical_by_album:
                canonical_by_album[ga.album_id] = ga

        return [
            (canonical_by_album[album_id].albums, group_ids)
            for album_id, group_ids in group_ids_by_album.items()
        ]

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
