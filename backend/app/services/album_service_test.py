import pytest
from app.models import Album, GroupAlbum
from app.models.group import GroupRole
from app.schemas.album import AlbumCreate, GroupAlbumStatus, GroupAlbumStatusUpdate
from fastapi import HTTPException, status


class TestAlbumServiceCreate:
    def test_create_album_success(self, album_service):
        data = AlbumCreate(
            spotify_album_id="spotify_xyz",
            title="Kid A",
            artist="Radiohead",
            genres=["electronic", "art rock"],
        )
        album = album_service.create_album(data)

        assert album.id is not None
        assert album.spotify_album_id == "spotify_xyz"
        assert album.title == "Kid A"
        assert album.artist == "Radiohead"
        assert len(album.genres) == 2
        assert {g.name for g in album.genres} == {"electronic", "art rock"}

    def test_create_album_no_genres(self, album_service):
        data = AlbumCreate(spotify_album_id="spotify_ng", title="Hail to the Thief", artist="Radiohead")
        album = album_service.create_album(data)
        assert album.genres == []

    def test_create_album_duplicate_spotify_id(self, album_service, sample_album):
        data = AlbumCreate(
            spotify_album_id=sample_album.spotify_album_id,
            title="Duplicate",
            artist="Someone",
        )
        with pytest.raises(HTTPException) as exc_info:
            album_service.create_album(data)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_get_or_create_returns_existing(self, album_service, sample_album):
        data = AlbumCreate(
            spotify_album_id=sample_album.spotify_album_id,
            title="Different Title",
            artist="Different Artist",
        )
        result = album_service.get_or_create_album(data)
        assert result.id == sample_album.id
        assert result.title == sample_album.title

    def test_get_or_create_creates_new(self, album_service):
        data = AlbumCreate(spotify_album_id="new_spotify_id", title="New Album", artist="Artist")
        album = album_service.get_or_create_album(data)
        assert album.id is not None
        assert album.spotify_album_id == "new_spotify_id"


class TestAlbumServiceGet:
    def test_get_album_by_id_success(self, album_service, sample_album):
        result = album_service.get_album_by_id(sample_album.id)
        assert result.id == sample_album.id

    def test_get_album_by_id_not_found(self, album_service):
        with pytest.raises(HTTPException) as exc_info:
            album_service.get_album_by_id(99999)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_album_by_spotify_id_success(self, album_service, sample_album):
        result = album_service.get_album_by_spotify_id(sample_album.spotify_album_id)
        assert result.id == sample_album.id

    def test_get_album_by_spotify_id_not_found_raises(self, album_service):
        with pytest.raises(HTTPException) as exc_info:
            album_service.get_album_by_spotify_id("nope_123")
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_get_album_by_spotify_id_not_found_silent(self, album_service):
        result = album_service.get_album_by_spotify_id("nope_123", raise_on_missing=False)
        assert result is None


class TestAlbumServiceNominate:
    def test_nominate_album_success(self, album_service, sample_group, sample_album, sample_user):
        ga = album_service.nominate_album(sample_group.id, sample_album.id, sample_user)

        assert ga.id is not None
        assert ga.group_id == sample_group.id
        assert ga.album_id == sample_album.id
        assert ga.added_by == sample_user.id
        assert ga.status == GroupAlbumStatus.Pending

    def test_nominate_album_non_member_forbidden(
        self, album_service, sample_group, sample_album, user_factory
    ):
        outsider = user_factory(email="outsider@test.com", username="outsider")
        with pytest.raises(HTTPException) as exc_info:
            album_service.nominate_album(sample_group.id, sample_album.id, outsider)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_nominate_album_duplicate_conflict(
        self, album_service, sample_group, sample_album, sample_user, sample_group_album
    ):
        with pytest.raises(HTTPException) as exc_info:
            album_service.nominate_album(sample_group.id, sample_album.id, sample_user)
        assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    def test_nominate_album_not_found(self, album_service, sample_group, sample_user):
        with pytest.raises(HTTPException) as exc_info:
            album_service.nominate_album(sample_group.id, 99999, sample_user)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestAlbumServiceGroupAlbumGet:
    def test_get_group_albums_all(self, album_service, sample_group, sample_group_album):
        results = album_service.get_group_albums(sample_group.id)
        assert len(results) == 1
        assert results[0].id == sample_group_album.id

    def test_get_group_albums_status_filter(self, album_service, sample_group, sample_group_album):
        results = album_service.get_group_albums(sample_group.id, status_filter="pending")
        assert len(results) == 1

        results = album_service.get_group_albums(sample_group.id, status_filter="selected")
        assert len(results) == 0

    def test_get_group_album_success(self, album_service, sample_group, sample_group_album):
        result = album_service.get_group_album(sample_group.id, sample_group_album.id)
        assert result.id == sample_group_album.id

    def test_get_group_album_not_found(self, album_service, sample_group):
        with pytest.raises(HTTPException) as exc_info:
            album_service.get_group_album(sample_group.id, 99999)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


class TestAlbumServiceRemoveGroupAlbum:
    def test_remove_group_album_by_nominator(
        self, album_service, sample_group, sample_group_album, sample_user
    ):
        album_service.remove_group_album(sample_group.id, sample_group_album.id, sample_user)
        with pytest.raises(HTTPException):
            album_service.get_group_album(sample_group.id, sample_group_album.id)

    def test_remove_group_album_by_admin(
        self, album_service, sample_group_service, sample_group, sample_group_album, user_factory
    ):
        admin = user_factory(email="admin@test.com", username="admin_user")
        sample_group_service.add_user(sample_group.id, admin.id)
        sample_group_service.set_user_role(
            admin.id, admin.id, sample_group.id, GroupRole.Admin, force=True
        )
        album_service.remove_group_album(sample_group.id, sample_group_album.id, admin)
        with pytest.raises(HTTPException):
            album_service.get_group_album(sample_group.id, sample_group_album.id)

    def test_remove_group_album_by_non_admin_non_nominator_forbidden(
        self, album_service, sample_group, sample_group_album, sample_group_service, user_factory
    ):
        other = user_factory(email="other@test.com", username="other_user")
        sample_group_service.add_user(sample_group.id, other.id)
        with pytest.raises(HTTPException) as exc_info:
            album_service.remove_group_album(sample_group.id, sample_group_album.id, other)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestAlbumServiceUpdateStatus:
    def test_update_status_success(
        self, album_service, sample_group_service, sample_group, sample_group_album, user_factory
    ):
        admin = user_factory(email="admin@test.com", username="admin_user")
        sample_group_service.add_user(sample_group.id, admin.id)
        sample_group_service.set_user_role(
            admin.id, admin.id, sample_group.id, GroupRole.Admin, force=True
        )
        update_data = GroupAlbumStatusUpdate(status=GroupAlbumStatus.Selected)
        result = album_service.update_group_album_status(
            sample_group.id, sample_group_album.id, update_data, admin
        )
        assert result.status == GroupAlbumStatus.Selected

    def test_update_status_non_admin_forbidden(
        self, album_service, sample_group, sample_group_album, sample_group_service, user_factory
    ):
        member = user_factory(email="member@test.com", username="member_user")
        sample_group_service.add_user(sample_group.id, member.id)
        update_data = GroupAlbumStatusUpdate(status=GroupAlbumStatus.Selected)
        with pytest.raises(HTTPException) as exc_info:
            album_service.update_group_album_status(
                sample_group.id, sample_group_album.id, update_data, member
            )
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
