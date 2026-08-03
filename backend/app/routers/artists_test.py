"""Router tests for the artist overview endpoint (service mocked)."""

from unittest.mock import MagicMock

import pytest
from app.dependencies import get_artist_service, get_current_user_optional
from app.main import app
from app.schemas.album import AlbumResponse
from app.schemas.artist import ArtistAlbumItem, ArtistOverviewResponse
from app.services.artist_service import ArtistService
from datetime import datetime, timezone
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


def _album_response(album_id: int, title: str, artist: str) -> AlbumResponse:
    return AlbumResponse(
        id=album_id,
        title=title,
        artist=artist,
        added_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        genres=[],
    )


def _overview() -> ArtistOverviewResponse:
    return ArtistOverviewResponse(
        artist="Muse",
        album_count=2,
        total_nominations=5,
        total_reviews=4,
        average_rating=6.5,
        rating_stddev=1.5,
        albums=[
            ArtistAlbumItem(
                album=_album_response(1, "Absolution", "Muse"),
                nomination_count=3,
                review_count=3,
                average_rating=8.0,
                rating_stddev=1.1,
            ),
            ArtistAlbumItem(
                album=_album_response(2, "Drones", "Muse"),
                nomination_count=2,
                review_count=1,
                average_rating=5.0,
                rating_stddev=0.0,
            ),
        ],
    )


@pytest.fixture
def mock_artist_service():
    return MagicMock(spec=ArtistService)


@pytest.fixture
def client(mock_artist_service):
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_artist_service] = lambda: mock_artist_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestArtistOverviewEndpoint:
    def test_overview_success(self, client, mock_artist_service):
        mock_artist_service.get_artist_overview.return_value = _overview()

        resp = client.get("/artists/overview", params={"name": "Muse"})

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["artist"] == "Muse"
        assert body["album_count"] == 2
        assert body["total_nominations"] == 5
        assert body["total_reviews"] == 4
        assert body["average_rating"] == 6.5
        assert body["rating_stddev"] == 1.5
        assert len(body["albums"]) == 2
        assert body["albums"][0]["album"]["title"] == "Absolution"
        assert body["albums"][0]["nomination_count"] == 3
        assert body["albums"][0]["rating_stddev"] == 1.1
        mock_artist_service.get_artist_overview.assert_called_once_with("Muse")

    def test_overview_works_without_authentication(self, client, mock_artist_service):
        mock_artist_service.get_artist_overview.return_value = _overview()
        resp = client.get("/artists/overview", params={"name": "Muse"})
        assert resp.status_code == status.HTTP_200_OK

    def test_overview_unknown_artist_404(self, client, mock_artist_service):
        mock_artist_service.get_artist_overview.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No nominated albums found"
        )
        resp = client.get("/artists/overview", params={"name": "Nobody"})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_overview_missing_name_422(self, client, mock_artist_service):
        resp = client.get("/artists/overview")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_overview_blank_name_422(self, client, mock_artist_service):
        resp = client.get("/artists/overview", params={"name": ""})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
