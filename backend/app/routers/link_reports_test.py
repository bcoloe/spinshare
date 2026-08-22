"""Tests for the user-facing link report endpoint."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_link_report_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.services.link_report_service import LinkReportService

VALID_BODY = {
    "link_field": "spotify",
    "reason_code": "bad",
    "suggested_url": "https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR",
}


def make_mock_report(**overrides):
    data = {
        "id": 1,
        "album_id": 7,
        "reporter_id": 1,
        "link_field": "spotify",
        "reason_code": "bad",
        "reason_detail": None,
        "suggested_url": "https://open.spotify.com/album/3v1nspBDZhlcJGDW6fUJQR",
        "suggested_value": "3v1nspBDZhlcJGDW6fUJQR",
        "status": "open",
        "resolved_by": None,
        "resolved_at": None,
        "resolution_note": None,
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return MagicMock(**data)


@pytest.fixture
def mock_link_report_service():
    return MagicMock(spec=LinkReportService)


@pytest.fixture
def report_client(mock_user, mock_link_report_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_link_report_service] = lambda: mock_link_report_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestSubmitLinkReport:
    def test_submit_success_201(self, report_client, mock_link_report_service):
        mock_link_report_service.create.return_value = make_mock_report()

        resp = report_client.post("/albums/7/link-reports", json=VALID_BODY)

        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["suggested_value"] == "3v1nspBDZhlcJGDW6fUJQR"
        mock_link_report_service.create.assert_called_once()

    def test_submit_without_suggestion_succeeds(
        self, report_client, mock_link_report_service
    ):
        """The suggested URL is optional — a reason alone is a valid report."""
        mock_link_report_service.create.return_value = make_mock_report(
            suggested_url=None, suggested_value=None
        )

        resp = report_client.post(
            "/albums/7/link-reports",
            json={"link_field": "wikipedia", "reason_code": "missing"},
        )

        assert resp.status_code == status.HTTP_201_CREATED

    def test_submit_requires_auth_401(self, unauthed_client):
        resp = unauthed_client.post("/albums/7/link-reports", json=VALID_BODY)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_submit_rejects_unknown_reason_code_422(
        self, report_client, mock_link_report_service
    ):
        resp = report_client.post(
            "/albums/7/link-reports", json={"link_field": "spotify", "reason_code": "vibes"}
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_link_report_service.create.assert_not_called()

    def test_submit_rejects_missing_reason_code_422(
        self, report_client, mock_link_report_service
    ):
        resp = report_client.post("/albums/7/link-reports", json={"link_field": "spotify"})

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_link_report_service.create.assert_not_called()

    def test_submit_rejects_overlong_detail_422(
        self, report_client, mock_link_report_service
    ):
        resp = report_client.post(
            "/albums/7/link-reports",
            json={"link_field": "spotify", "reason_code": "other", "reason_detail": "x" * 1001},
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_link_report_service.create.assert_not_called()

    def test_submit_rejects_unknown_link_field_422(
        self, report_client, mock_link_report_service
    ):
        resp = report_client.post(
            "/albums/7/link-reports",
            json={"link_field": "myspace", "reason_code": "bad"},
        )

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_link_report_service.create.assert_not_called()

    def test_submit_propagates_400(self, report_client, mock_link_report_service):
        mock_link_report_service.create.side_effect = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That looks like an Apple Music link",
        )

        resp = report_client.post("/albums/7/link-reports", json=VALID_BODY)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_submit_propagates_404(self, report_client, mock_link_report_service):
        mock_link_report_service.create.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Album not found"
        )

        resp = report_client.post("/albums/999/link-reports", json=VALID_BODY)

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_submit_propagates_409(self, report_client, mock_link_report_service):
        mock_link_report_service.create.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an open report for this link",
        )

        resp = report_client.post("/albums/7/link-reports", json=VALID_BODY)

        assert resp.status_code == status.HTTP_409_CONFLICT
        assert "already have an open report" in resp.json()["detail"]

    def test_non_admin_may_submit(self, mock_link_report_service):
        """The whole point of the feature — reporting is not admin-gated."""
        plain_user = make_mock_user(is_admin=False)
        mock_link_report_service.create.return_value = make_mock_report()
        app.dependency_overrides[get_current_user] = lambda: plain_user
        app.dependency_overrides[get_link_report_service] = lambda: mock_link_report_service

        with TestClient(app) as c:
            resp = c.post("/albums/7/link-reports", json=VALID_BODY)
        app.dependency_overrides.clear()

        assert resp.status_code == status.HTTP_201_CREATED
