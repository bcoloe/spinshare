"""Router tests for weekly recap endpoints — HTTP behaviour with the service mocked."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_recap_service
from app.main import app
from app.routers.conftest import _auth_headers_for, make_mock_user
from app.schemas.recap import (
    GuessAccuracy,
    LeaderboardEntry,
    RecapData,
    RecapResponse,
    RecapSummary,
)


def _sample_response(recap_id=1, group_id=1, seen=False) -> RecapResponse:
    return RecapResponse(
        id=recap_id,
        group_id=group_id,
        week_start=date(2026, 7, 27),
        week_end=date(2026, 8, 3),
        generated_at=datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc),
        data=RecapData(
            albums_added=[LeaderboardEntry(username="alice", count=2)],
            albums_reviewed=[LeaderboardEntry(username="bob", count=1)],
            favorite_album=None,
            least_favorite_album=None,
            guess_accuracy=GuessAccuracy(total_guesses=0, correct_guesses=0, pct=0.0, per_member=[]),
        ),
        seen=seen,
    )


@pytest.fixture
def mock_recap_service():
    return MagicMock()


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def client(mock_user, mock_recap_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_recap_service] = lambda: mock_recap_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(mock_user):
    return _auth_headers_for(mock_user)


class TestListRecaps:
    def test_returns_list(self, client, mock_recap_service, auth_headers):
        mock_recap_service.list_for_group.return_value = [_sample_response()]
        resp = client.get("/groups/1/recaps", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["data"]["albums_added"][0]["username"] == "alice"
        mock_recap_service.list_for_group.assert_called_once()

    def test_requires_auth(self):
        # No auth override → real get_current_user rejects the missing token.
        with TestClient(app) as c:
            assert c.get("/groups/1/recaps").status_code == 401


class TestLatestRecap:
    def test_returns_recap(self, client, mock_recap_service, auth_headers):
        mock_recap_service.latest_for_group.return_value = _sample_response()
        resp = client.get("/groups/1/recaps/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == 1

    def test_returns_null_when_none(self, client, mock_recap_service, auth_headers):
        mock_recap_service.latest_for_group.return_value = None
        resp = client.get("/groups/1/recaps/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() is None


class TestGetRecap:
    def test_returns_recap(self, client, mock_recap_service, auth_headers):
        mock_recap_service.get_recap.return_value = _sample_response(recap_id=7)
        resp = client.get("/groups/1/recaps/7", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == 7


class TestMarkSeen:
    def test_returns_204(self, client, mock_recap_service, auth_headers):
        resp = client.post("/groups/1/recaps/7/seen", headers=auth_headers)
        assert resp.status_code == 204
        mock_recap_service.mark_seen.assert_called_once()


class TestPending:
    def test_returns_summaries(self, client, mock_recap_service, auth_headers):
        mock_recap_service.pending_for_user.return_value = [
            RecapSummary(id=1, group_id=1, group_name="Recap Group", week_start=date(2026, 7, 27), week_end=date(2026, 8, 3))
        ]
        resp = client.get("/users/me/recaps/pending", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()[0]["group_name"] == "Recap Group"


class TestGenerate:
    def test_404_in_production(self, client, mock_recap_service, auth_headers):
        with patch("app.routers.recaps.get_settings") as gs:
            gs.return_value = MagicMock(ENVIRONMENT="production")
            resp = client.post("/groups/1/recaps/generate?week_start=2026-07-27", headers=auth_headers)
        assert resp.status_code == 404
        mock_recap_service.generate_for_group.assert_not_called()

    def test_allowed_in_test_env(self, client, mock_recap_service, auth_headers):
        mock_recap_service.generate_for_group.return_value = MagicMock(id=3)
        mock_recap_service.get_recap.return_value = _sample_response(recap_id=3)
        with patch("app.routers.recaps.get_settings") as gs:
            gs.return_value = MagicMock(ENVIRONMENT="test")
            resp = client.post("/groups/1/recaps/generate?week_start=2026-07-27", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == 3
        mock_recap_service.generate_for_group.assert_called_once()
