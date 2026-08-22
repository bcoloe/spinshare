"""Tests for the admin panel router.

Every endpoint here is site-admin gated, so each class carries the standard
triple: success, 403 for a signed-in non-admin, 401 for anonymous.
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.dependencies import (
    get_admin_service,
    get_current_user,
    get_link_report_service,
)
from app.main import app
from app.routers.conftest import make_mock_user
from app.schemas.admin import AdminMetricsResponse, MetricPair, TimeSeriesPoint
from app.schemas.link_report import AdminLinkReportItem, AlbumLinksSnapshot
from app.services.admin_service import AdminService
from app.services.link_report_service import LinkReportService


def make_report_item(**overrides) -> AdminLinkReportItem:
    data = {
        "id": 1,
        "album_id": 7,
        "reporter_id": 2,
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
        "album": AlbumLinksSnapshot(
            id=7, title="OK Computer", artist="Radiohead", spotify_album_id="old_id"
        ),
        "reporter_username": "alice",
        "current_value": "old_id",
    }
    data.update(overrides)
    return AdminLinkReportItem(**data)


def make_mock_report(**overrides):
    data = {
        "id": 1,
        "album_id": 7,
        "reporter_id": 2,
        "link_field": "spotify",
        "reason_code": "bad",
        "reason_detail": None,
        "suggested_url": None,
        "suggested_value": None,
        "status": "resolved",
        "resolved_by": 1,
        "resolved_at": datetime.now(timezone.utc),
        "resolution_note": None,
        "created_at": datetime.now(timezone.utc),
    }
    data.update(overrides)
    return MagicMock(**data)


@pytest.fixture
def mock_link_report_service():
    return MagicMock(spec=LinkReportService)


@pytest.fixture
def mock_admin_service():
    return MagicMock(spec=AdminService)


@pytest.fixture
def client(admin_client, mock_link_report_service):
    """Admin-authenticated client with the link report service mocked."""
    app.dependency_overrides[get_link_report_service] = lambda: mock_link_report_service
    return admin_client


def non_admin_client(mock_service):
    """A signed-in but non-admin client, for asserting the 403 path."""
    app.dependency_overrides[get_current_user] = lambda: make_mock_user(is_admin=False)
    app.dependency_overrides[get_link_report_service] = lambda: mock_service
    return TestClient(app)


class TestListLinkReports:
    def test_list_success(self, client, mock_link_report_service):
        mock_link_report_service.list_reports.return_value = [make_report_item()]

        resp = client.get("/admin/link-reports")

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body) == 1
        assert body[0]["reporter_username"] == "alice"
        assert body[0]["album"]["title"] == "OK Computer"
        assert body[0]["current_value"] == "old_id"

    def test_list_defaults_to_open(self, client, mock_link_report_service):
        mock_link_report_service.list_reports.return_value = []

        client.get("/admin/link-reports")

        assert mock_link_report_service.list_reports.call_args.kwargs["status_filter"] == "open"

    def test_list_filters_by_status_query(self, client, mock_link_report_service):
        mock_link_report_service.list_reports.return_value = []

        client.get("/admin/link-reports?status=dismissed")

        assert (
            mock_link_report_service.list_reports.call_args.kwargs["status_filter"] == "dismissed"
        )

    def test_list_rejects_unknown_status_422(self, client, mock_link_report_service):
        resp = client.get("/admin/link-reports?status=banana")

        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        mock_link_report_service.list_reports.assert_not_called()

    def test_list_rejects_out_of_range_limit_422(self, client, mock_link_report_service):
        assert client.get("/admin/link-reports?limit=0").status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        assert client.get("/admin/link-reports?limit=500").status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    def test_list_requires_admin(self, mock_link_report_service):
        with non_admin_client(mock_link_report_service) as c:
            resp = c.get("/admin/link-reports")
        app.dependency_overrides.clear()
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_list_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/admin/link-reports")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestOpenReportCount:
    def test_count_success(self, client, mock_link_report_service):
        mock_link_report_service.count_open.return_value = 4

        resp = client.get("/admin/link-reports/count")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"open_count": 4}

    def test_count_is_not_captured_as_a_report_id(self, client, mock_link_report_service):
        """/count must be routed before /{report_id}, or it 422s on int parsing."""
        mock_link_report_service.count_open.return_value = 0

        resp = client.get("/admin/link-reports/count")

        assert resp.status_code == status.HTTP_200_OK
        mock_link_report_service.count_open.assert_called_once()

    def test_count_requires_admin(self, mock_link_report_service):
        with non_admin_client(mock_link_report_service) as c:
            resp = c.get("/admin/link-reports/count")
        app.dependency_overrides.clear()
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_count_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/admin/link-reports/count")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestResolveLinkReport:
    def test_resolve_success(self, client, mock_link_report_service):
        mock_link_report_service.resolve.return_value = make_mock_report()

        resp = client.post("/admin/link-reports/1/resolve")

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "resolved"
        mock_link_report_service.resolve.assert_called_once()

    def test_resolve_404(self, client, mock_link_report_service):
        mock_link_report_service.resolve.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link report not found"
        )

        resp = client.post("/admin/link-reports/999/resolve")

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_resolve_already_closed_409(self, client, mock_link_report_service):
        mock_link_report_service.resolve.side_effect = HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Report has already been resolved"
        )

        resp = client.post("/admin/link-reports/1/resolve")

        assert resp.status_code == status.HTTP_409_CONFLICT

    def test_resolve_requires_admin(self, mock_link_report_service):
        with non_admin_client(mock_link_report_service) as c:
            resp = c.post("/admin/link-reports/1/resolve")
        app.dependency_overrides.clear()
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        mock_link_report_service.resolve.assert_not_called()

    def test_resolve_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/admin/link-reports/1/resolve")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestDismissLinkReport:
    def test_dismiss_success_with_note(self, client, mock_link_report_service):
        mock_link_report_service.dismiss.return_value = make_mock_report(
            status="dismissed", resolution_note="Link works for me"
        )

        resp = client.post(
            "/admin/link-reports/1/dismiss", json={"note": "Link works for me"}
        )

        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "dismissed"
        assert resp.json()["resolution_note"] == "Link works for me"
        assert mock_link_report_service.dismiss.call_args.args[2] == "Link works for me"

    def test_dismiss_without_note(self, client, mock_link_report_service):
        mock_link_report_service.dismiss.return_value = make_mock_report(status="dismissed")

        resp = client.post("/admin/link-reports/1/dismiss", json={})

        assert resp.status_code == status.HTTP_200_OK
        assert mock_link_report_service.dismiss.call_args.args[2] is None

    def test_dismiss_404(self, client, mock_link_report_service):
        mock_link_report_service.dismiss.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Link report not found"
        )

        resp = client.post("/admin/link-reports/999/dismiss", json={})

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_dismiss_requires_admin(self, mock_link_report_service):
        with non_admin_client(mock_link_report_service) as c:
            resp = c.post("/admin/link-reports/1/dismiss", json={})
        app.dependency_overrides.clear()
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        mock_link_report_service.dismiss.assert_not_called()

    def test_dismiss_unauthenticated(self, unauthed_client):
        resp = unauthed_client.post("/admin/link-reports/1/dismiss", json={})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def make_metrics(**overrides) -> AdminMetricsResponse:
    data = {
        "users": MetricPair(total=10, recent=2),
        "groups": MetricPair(total=3, recent=1),
        "albums": MetricPair(total=42, recent=5),
        "reviews": MetricPair(total=100, recent=9),
        "signups_by_day": [TimeSeriesPoint(day=date(2026, 8, 20), count=2)],
        "reviews_by_day": [],
        "open_link_reports": 4,
        "window_days": 30,
    }
    data.update(overrides)
    return AdminMetricsResponse(**data)


class TestAdminMetrics:
    @pytest.fixture
    def metrics_client(self, admin_client, mock_admin_service):
        app.dependency_overrides[get_admin_service] = lambda: mock_admin_service
        return admin_client

    def test_metrics_success(self, metrics_client, mock_admin_service):
        mock_admin_service.get_admin_metrics.return_value = make_metrics()

        resp = metrics_client.get("/admin/metrics")

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["users"] == {"total": 10, "recent": 2}
        assert body["open_link_reports"] == 4
        assert body["signups_by_day"][0] == {"day": "2026-08-20", "count": 2}

    def test_metrics_defaults_to_30_days(self, metrics_client, mock_admin_service):
        mock_admin_service.get_admin_metrics.return_value = make_metrics()

        metrics_client.get("/admin/metrics")

        mock_admin_service.get_admin_metrics.assert_called_once_with(30)

    def test_metrics_passes_days_through(self, metrics_client, mock_admin_service):
        mock_admin_service.get_admin_metrics.return_value = make_metrics(window_days=7)

        metrics_client.get("/admin/metrics?days=7")

        mock_admin_service.get_admin_metrics.assert_called_once_with(7)

    def test_days_out_of_range_422(self, metrics_client, mock_admin_service):
        assert metrics_client.get("/admin/metrics?days=0").status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        assert metrics_client.get("/admin/metrics?days=366").status_code == (
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        mock_admin_service.get_admin_metrics.assert_not_called()

    def test_metrics_requires_admin(self, mock_admin_service):
        app.dependency_overrides[get_current_user] = lambda: make_mock_user(is_admin=False)
        app.dependency_overrides[get_admin_service] = lambda: mock_admin_service
        with TestClient(app) as c:
            resp = c.get("/admin/metrics")
        app.dependency_overrides.clear()

        assert resp.status_code == status.HTTP_403_FORBIDDEN
        mock_admin_service.get_admin_metrics.assert_not_called()

    def test_metrics_unauthenticated(self, unauthed_client):
        resp = unauthed_client.get("/admin/metrics")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
