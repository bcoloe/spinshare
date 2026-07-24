# backend/app/routers/public_test.py
#
# Router tests: verify HTTP status codes and response shape. PublicSpinService
# is fully mocked — business logic is tested in public_spin_service_test.py.

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from app.dependencies import get_public_spin_service
from app.main import app
from app.schemas.album import AlbumResponse, GroupAlbumResponse
from app.schemas.public_spin import PublicSpinResponse
from app.services.public_spin_service import PublicSpinService
from fastapi import status
from fastapi.testclient import TestClient

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_album_response(album_id=1):
    return GroupAlbumResponse(
        id=album_id,
        group_id=1,
        album_id=album_id,
        added_by=1,
        status="pending",
        added_at=_NOW,
        selected_date=None,
        album=AlbumResponse(id=album_id, title="OK Computer", artist="Radiohead", added_at=_NOW),
    )


@pytest.fixture
def mock_svc():
    return MagicMock(spec=PublicSpinService)


@pytest.fixture
def client(mock_svc):
    app.dependency_overrides[get_public_spin_service] = lambda: mock_svc
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestGetPublicSpin:
    def test_returns_todays_draw_no_auth_required(self, client, mock_svc):
        mock_svc.get_or_create_todays_draw.return_value = PublicSpinResponse(
            draw_date=date(2026, 1, 1),
            albums=[make_album_response(1), make_album_response(2), make_album_response(3)],
        )

        resp = client.get("/public/spin")

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["draw_date"] == "2026-01-01"
        assert len(body["albums"]) == 3

    def test_empty_pool_returns_empty_albums(self, client, mock_svc):
        mock_svc.get_or_create_todays_draw.return_value = PublicSpinResponse(
            draw_date=date(2026, 1, 1), albums=[]
        )
        resp = client.get("/public/spin")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["albums"] == []

    def test_global_group_missing_returns_503(self, client, mock_svc):
        from fastapi import HTTPException
        mock_svc.get_or_create_todays_draw.side_effect = HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Global group not configured"
        )
        resp = client.get("/public/spin")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
