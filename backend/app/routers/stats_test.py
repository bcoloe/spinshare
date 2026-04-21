# backend/app/routers/stats_test.py

from unittest.mock import MagicMock

import pytest
from app.dependencies import get_current_user, get_stats_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.schemas.stats import (
    AlbumGuessStatsResponse,
    AlbumReviewStatsResponse,
    UserGuessStatsResponse,
)
from app.services.stats_service import StatsService
from fastapi import HTTPException, status
from fastapi.testclient import TestClient


@pytest.fixture
def mock_svc():
    return MagicMock(spec=StatsService)


@pytest.fixture
def client(mock_svc):
    app.dependency_overrides[get_current_user] = lambda: make_mock_user()
    app.dependency_overrides[get_stats_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_svc):
    app.dependency_overrides[get_stats_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestUserGuessStats:
    def test_success(self, client, mock_svc):
        mock_svc.get_user_guess_stats.return_value = UserGuessStatsResponse(
            user_id=2, group_id=1, total_guesses=5, correct_guesses=3, accuracy=0.6
        )
        resp = client.get("/stats/groups/1/members/2/guesses")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["total_guesses"] == 5
        assert body["correct_guesses"] == 3
        assert body["accuracy"] == 0.6

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/stats/groups/1/members/2/guesses")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestAlbumGuessStats:
    def test_success(self, client, mock_svc):
        mock_svc.get_album_guess_stats.return_value = AlbumGuessStatsResponse(
            group_album_id=1,
            nominator_user_id=1,
            nominator_username="test_user",
            total_guesses=3,
            correct_guesses=2,
            guesses=[],
        )
        resp = client.get("/stats/groups/1/albums/1/guesses")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["total_guesses"] == 3
        assert body["correct_guesses"] == 2
        assert body["nominator_username"] == "test_user"

    def test_not_found(self, client, mock_svc):
        mock_svc.get_album_guess_stats.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        )
        resp = client.get("/stats/groups/1/albums/999/guesses")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/stats/groups/1/albums/1/guesses")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestAlbumReviewStats:
    def test_success(self, client, mock_svc):
        mock_svc.get_album_review_stats.return_value = AlbumReviewStatsResponse(
            album_id=1, review_count=4, avg_rating=7.25, min_rating=5.0, max_rating=9.0
        )
        resp = client.get("/stats/albums/1/reviews")
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["review_count"] == 4
        assert body["avg_rating"] == 7.25
        assert body["min_rating"] == 5.0
        assert body["max_rating"] == 9.0

    def test_no_reviews(self, client, mock_svc):
        mock_svc.get_album_review_stats.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No reviews"
        )
        resp = client.get("/stats/albums/1/reviews")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/stats/albums/1/reviews")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
