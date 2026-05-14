# backend/app/routers/albums_test.py
#
# Router tests: verify HTTP status codes, request/response shapes, and auth
# enforcement. AlbumService and ReviewService are fully mocked.

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from app.dependencies import get_album_service, get_review_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.services.album_service import AlbumService
from app.services.review_service import ReviewService
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.dependencies import get_current_user

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_mock_album(
    id=1,
    spotify_album_id="spotify_abc",
    title="OK Computer",
    artist="Radiohead",
    release_date="1997-05",
    cover_url="https://example.com/cover.jpg",
    youtube_music_id=None,
    added_at=None,
    genres=None,
):
    album = MagicMock()
    album.id = id
    album.spotify_album_id = spotify_album_id
    album.title = title
    album.artist = artist
    album.release_date = release_date
    album.cover_url = cover_url
    album.youtube_music_id = youtube_music_id
    album.added_at = added_at or _NOW
    album.genres = genres if genres is not None else []
    return album


def make_mock_group_album(
    id=1,
    group_id=1,
    album_id=1,
    added_by=1,
    status="pending",
    added_at=None,
    selected_date=None,
    album=None,
):
    ga = MagicMock()
    ga.id = id
    ga.group_id = group_id
    ga.album_id = album_id
    ga.added_by = added_by
    ga.status = status
    ga.added_at = added_at or _NOW
    ga.selected_date = selected_date
    ga.albums = album or make_mock_album()
    return ga


def make_mock_review(
    id=1,
    album_id=1,
    user_id=1,
    username="testuser",
    first_name=None,
    last_name=None,
    rating=8.5,
    comment="Great album",
    is_draft=False,
    reviewed_at=None,
    updated_at=None,
):
    review = MagicMock()
    review.id = id
    review.album_id = album_id
    review.user_id = user_id
    review.username = username
    review.first_name = first_name
    review.last_name = last_name
    review.rating = rating
    review.comment = comment
    review.is_draft = is_draft
    review.reviewed_at = reviewed_at or _NOW
    review.updated_at = updated_at
    return review


def make_mock_album_stats(
    average_rating=7.5,
    review_count=4,
    histogram=None,
):
    from app.schemas.album import AlbumStatsResponse, HistogramBucket

    if histogram is None:
        histogram = [HistogramBucket(bucket_start=i, bucket_end=i + 1, count=0) for i in range(10)]
        histogram[7] = HistogramBucket(bucket_start=7, bucket_end=8, count=review_count)
    return AlbumStatsResponse(
        average_rating=average_rating, review_count=review_count, histogram=histogram
    )


@pytest.fixture
def mock_album_service():
    return MagicMock(spec=AlbumService)


@pytest.fixture
def mock_review_service():
    return MagicMock(spec=ReviewService)


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_album_service, mock_review_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_album_service] = lambda: mock_album_service
    app.dependency_overrides[get_review_service] = lambda: mock_review_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_album_service, mock_review_service):
    app.dependency_overrides[get_album_service] = lambda: mock_album_service
    app.dependency_overrides[get_review_service] = lambda: mock_review_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== ALBUMS ====================


class TestAlbumCreate:
    def test_create_album_success(self, client, mock_album_service):
        mock_album_service.create_album.return_value = make_mock_album()

        resp = client.post(
            "/albums/",
            json={
                "spotify_album_id": "spotify_abc",
                "title": "OK Computer",
                "artist": "Radiohead",
                "genres": [],
            },
        )

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["title"] == "OK Computer"
        assert body["spotify_album_id"] == "spotify_abc"
        mock_album_service.create_album.assert_called_once()

    def test_create_album_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post(
            "/albums/",
            json={"spotify_album_id": "x", "title": "X", "artist": "Y"},
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_album_conflict(self, client, mock_album_service):
        mock_album_service.create_album.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already registered"
        )
        resp = client.post(
            "/albums/",
            json={"spotify_album_id": "dup", "title": "Dup", "artist": "Art"},
        )
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_get_or_create_album_success(self, client, mock_album_service):
        mock_album_service.get_or_create_album.return_value = make_mock_album()
        resp = client.post(
            "/albums/get-or-create",
            json={"spotify_album_id": "spotify_abc", "title": "OK Computer", "artist": "Radiohead"},
        )
        assert resp.status_code == status.HTTP_200_OK
        mock_album_service.get_or_create_album.assert_called_once()


class TestAlbumGet:
    def test_get_album_by_id_success(self, client, mock_album_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album(id=42)
        resp = client.get("/albums/42")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == 42

    def test_get_album_by_id_not_found(self, client, mock_album_service):
        mock_album_service.get_album_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.get("/albums/999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_album_by_spotify_id_success(self, client, mock_album_service):
        mock_album_service.get_album_by_spotify_id.return_value = make_mock_album(
            spotify_album_id="spotify_test"
        )
        resp = client.get("/albums/spotify/spotify_test")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["spotify_album_id"] == "spotify_test"

    def test_get_album_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/albums/1")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ==================== REVIEWS ====================


class TestReviewCreate:
    def test_create_review_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.create_review.return_value = make_mock_review()

        resp = client.post("/albums/1/reviews", json={"rating": 8.5, "comment": "Great album"})

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["rating"] == 8.5
        assert body["comment"] == "Great album"
        mock_review_service.create_review.assert_called_once()

    def test_create_review_invalid_rating(self, client, mock_album_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        resp = client.post("/albums/1/reviews", json={"rating": 11.0})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_review_album_not_found(self, client, mock_album_service):
        mock_album_service.get_album_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.post("/albums/999/reviews", json={"rating": 7.0})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_create_review_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/albums/1/reviews", json={"rating": 7.0})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_review_duplicate_conflict(
        self, client, mock_album_service, mock_review_service
    ):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.create_review.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already reviewed"
        )
        resp = client.post("/albums/1/reviews", json={"rating": 7.0})
        assert resp.status_code == status.HTTP_409_CONFLICT


class TestReviewGet:
    def test_list_reviews_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.get_reviews_for_album.return_value = [
            make_mock_review(id=1, rating=8.0, username="alice"),
            make_mock_review(id=2, user_id=2, rating=6.0, username="bob"),
        ]
        resp = client.get("/albums/1/reviews")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body) == 2
        assert body[0]["username"] == "alice"
        assert body[1]["username"] == "bob"

    def test_get_my_review_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.get_review_by_user_and_album.return_value = make_mock_review()
        resp = client.get("/albums/1/reviews/me")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["rating"] == 8.5

    def test_get_my_review_not_found(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.get_review_by_user_and_album.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.get("/albums/1/reviews/me")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestReviewUpdate:
    def test_update_review_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.update_review.return_value = make_mock_review(rating=9.5)
        resp = client.patch("/albums/1/reviews/1", json={"rating": 9.5})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["rating"] == 9.5

    def test_update_review_forbidden(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.update_review.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your review"
        )
        resp = client.patch("/albums/1/reviews/1", json={"rating": 1.0})
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestReviewDelete:
    def test_delete_review_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.delete_review.return_value = None
        resp = client.delete("/albums/1/reviews/1")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_review_service.delete_review.assert_called_once()

    def test_delete_review_forbidden(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.delete_review.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your review"
        )
        resp = client.delete("/albums/1/reviews/1")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ==================== GROUP ALBUMS ====================


class TestGroupReviews:
    def test_get_my_group_reviews_success(self, client, mock_review_service):
        mock_review_service.get_my_reviews_for_group.return_value = [
            make_mock_review(id=1, album_id=1, rating=7.0),
            make_mock_review(id=2, album_id=2, rating=8.5),
        ]
        resp = client.get("/groups/1/reviews/me")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body) == 2
        assert body[0]["album_id"] == 1
        assert body[1]["album_id"] == 2
        mock_review_service.get_my_reviews_for_group.assert_called_once()

    def test_get_my_group_reviews_empty(self, client, mock_review_service):
        mock_review_service.get_my_reviews_for_group.return_value = []
        resp = client.get("/groups/1/reviews/me")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_get_my_group_reviews_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/reviews/me")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_group_reviews_success(self, client, mock_review_service):
        mock_review_service.get_all_reviews_for_group.return_value = [
            make_mock_review(id=1, album_id=1, username="alice", rating=7.0),
            make_mock_review(id=2, album_id=1, user_id=2, username="bob", rating=8.0),
        ]
        resp = client.get("/groups/1/reviews")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body) == 2
        assert body[0]["username"] == "alice"
        assert body[1]["username"] == "bob"
        mock_review_service.get_all_reviews_for_group.assert_called_once()

    def test_get_group_reviews_empty(self, client, mock_review_service):
        mock_review_service.get_all_reviews_for_group.return_value = []
        resp = client.get("/groups/1/reviews")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_get_group_reviews_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/groups/1/reviews")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestGroupAlbumNominate:
    def test_nominate_album_success(self, client, mock_album_service):
        mock_album_service.nominate_album.return_value = make_mock_group_album()

        resp = client.post("/groups/1/albums", json={"album_id": 1})

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["group_id"] == 1
        assert body["status"] == "pending"
        mock_album_service.nominate_album.assert_called_once()

    def test_nominate_album_not_member(self, client, mock_album_service):
        mock_album_service.nominate_album.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member"
        )
        resp = client.post("/groups/1/albums", json={"album_id": 1})
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_nominate_album_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/groups/1/albums", json={"album_id": 1})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_nominate_album_conflict(self, client, mock_album_service):
        mock_album_service.nominate_album.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already nominated"
        )
        resp = client.post("/groups/1/albums", json={"album_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_nominate_album_already_selected_conflict(self, client, mock_album_service):
        mock_album_service.nominate_album.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This album has already been selected for this group",
        )
        resp = client.post("/groups/1/albums", json={"album_id": 1})
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "already been selected" in resp.json()["detail"]


class TestGroupAlbumList:
    def test_list_group_albums_success(self, client, mock_album_service):
        mock_album_service.get_group_albums.return_value = [
            make_mock_group_album(id=1),
            make_mock_group_album(id=2, album_id=2),
        ]
        resp = client.get("/groups/1/albums")
        assert resp.status_code == status.HTTP_200_OK
        assert len(resp.json()) == 2

    def test_list_group_albums_status_filter(self, client, mock_album_service):
        mock_album_service.get_group_albums.return_value = []
        resp = client.get("/groups/1/albums?status=selected")
        assert resp.status_code == status.HTTP_200_OK
        mock_album_service.get_group_albums.assert_called_once_with(1, status_filter="selected")

    def test_get_group_album_success(self, client, mock_album_service):
        mock_album_service.get_group_album.return_value = make_mock_group_album(id=5)
        resp = client.get("/groups/1/albums/5")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == 5

    def test_get_group_album_not_found(self, client, mock_album_service):
        mock_album_service.get_group_album.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.get("/groups/1/albums/999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestGroupAlbumRemove:
    def test_remove_group_album_success(self, client, mock_album_service):
        mock_album_service.remove_group_album.return_value = None
        resp = client.delete("/groups/1/albums/1")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_album_service.remove_group_album.assert_called_once()

    def test_remove_group_album_forbidden(self, client, mock_album_service):
        mock_album_service.remove_group_album.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
        resp = client.delete("/groups/1/albums/1")
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestGroupAlbumStatusUpdate:
    def test_update_status_success(self, client, mock_album_service):
        mock_album_service.update_group_album_status.return_value = make_mock_group_album(
            status="selected"
        )
        resp = client.patch("/groups/1/albums/1/status", json={"status": "selected"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "selected"

    def test_update_status_invalid(self, client):
        resp = client.patch("/groups/1/albums/1/status", json={"status": "invalid_status"})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_status_forbidden(self, client, mock_album_service):
        mock_album_service.update_group_album_status.side_effect = HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin"
        )
        resp = client.patch("/groups/1/albums/1/status", json={"status": "selected"})
        assert resp.status_code == status.HTTP_403_FORBIDDEN


class TestAlbumSearch:
    def _make_page(self, items, total=None):
        from app.utils.spotify_client import SpotifySearchPage
        return SpotifySearchPage(items=items, total=total if total is not None else len(items))

    def test_search_returns_results(self, client):
        from app.utils.spotify_client import SpotifyAlbumResult

        mock_result = SpotifyAlbumResult(
            spotify_album_id="abc123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05-21",
            cover_url="https://example.com/cover.jpg",
            genres=["art rock"],
        )
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([mock_result])):
            resp = client.get("/albums/search?q=radiohead")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["spotify_album_id"] == "abc123"
        assert data["items"][0]["title"] == "OK Computer"
        assert data["items"][0]["artist"] == "Radiohead"
        assert data["next_offset"] is None

    def test_search_returns_next_offset_when_more_results(self, client):
        from app.utils.spotify_client import SpotifyAlbumResult

        mock_result = SpotifyAlbumResult(
            spotify_album_id="abc123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05-21",
            cover_url=None,
            genres=[],
        )
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([mock_result], total=25)):
            resp = client.get("/albums/search?q=radiohead")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["next_offset"] == 10

    def test_search_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/albums/search?q=radiohead")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_query_too_short(self, client):
        resp = client.get("/albums/search?q=r")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_spotify_unavailable(self, client):
        with patch(
            "app.routers.albums.spotify_client.search_albums",
            side_effect=HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="not configured"),
        ):
            resp = client.get("/albums/search?q=radiohead")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_search_no_params_returns_400(self, client):
        resp = client.get("/albums/search")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_artist_filter_only(self, client):
        from app.utils.spotify_client import SpotifyAlbumResult

        mock_result = SpotifyAlbumResult(
            spotify_album_id="abc123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05-21",
            cover_url=None,
            genres=[],
        )
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([mock_result])) as mock_search:
            resp = client.get("/albums/search?artist=Radiohead")

        assert resp.status_code == status.HTTP_200_OK
        mock_search.assert_called_once_with("", limit=10, offset=0, artist="Radiohead", album=None)

    def test_search_album_filter_only(self, client):
        from app.utils.spotify_client import SpotifyAlbumResult

        mock_result = SpotifyAlbumResult(
            spotify_album_id="abc123",
            title="OK Computer",
            artist="Radiohead",
            release_date="1997-05-21",
            cover_url=None,
            genres=[],
        )
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([mock_result])) as mock_search:
            resp = client.get("/albums/search?album=OK+Computer")

        assert resp.status_code == status.HTTP_200_OK
        mock_search.assert_called_once_with("", limit=10, offset=0, artist=None, album="OK Computer")

    def test_search_combined_filters(self, client):
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([])) as mock_search:
            resp = client.get("/albums/search?q=rock&artist=Radiohead&album=OK+Computer")

        assert resp.status_code == status.HTTP_200_OK
        mock_search.assert_called_once_with("rock", limit=10, offset=0, artist="Radiohead", album="OK Computer")

    def test_search_offset_passed_through(self, client):
        with patch("app.routers.albums.spotify_client.search_albums", return_value=self._make_page([])) as mock_search:
            resp = client.get("/albums/search?q=radiohead&offset=10")

        assert resp.status_code == status.HTTP_200_OK
        mock_search.assert_called_once_with("radiohead", limit=10, offset=10, artist=None, album=None)


class TestAlbumStats:
    def test_get_stats_success(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.get_album_stats.return_value = make_mock_album_stats()

        resp = client.get("/albums/1/stats")

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["average_rating"] == 7.5
        assert body["review_count"] == 4
        assert len(body["histogram"]) == 10
        mock_review_service.get_album_stats.assert_called_once_with(1)

    def test_get_stats_no_reviews(self, client, mock_album_service, mock_review_service):
        from app.schemas.album import AlbumStatsResponse, HistogramBucket

        mock_album_service.get_album_by_id.return_value = make_mock_album()
        mock_review_service.get_album_stats.return_value = AlbumStatsResponse(
            average_rating=None,
            review_count=0,
            histogram=[HistogramBucket(bucket_start=i, bucket_end=i + 1, count=0) for i in range(10)],
        )

        resp = client.get("/albums/1/stats")

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["average_rating"] is None
        assert body["review_count"] == 0

    def test_get_stats_album_not_found(self, client, mock_album_service, mock_review_service):
        mock_album_service.get_album_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.get("/albums/999/stats")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_stats_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/albums/1/stats")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
