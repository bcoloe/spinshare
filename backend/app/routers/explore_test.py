"""Router tests for /explore endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_explore_service
from app.main import app
from app.schemas.explore import (
    ArtistNominationItem,
    ExploreAlbumItem,
    ExploreAlbumsPage,
    ExploreGroupItem,
    ExploreGroupsPage,
    SiteStatsResponse,
)
from app.services.explore_service import ExploreService

from app.routers.conftest import make_mock_user


# ==================== HELPERS ====================

def _album_item(**overrides) -> ExploreAlbumItem:
    defaults = dict(
        id=1,
        spotify_album_id="sp_abc",
        title="OK Computer",
        artist="Radiohead",
        artist_url=None,
        cover_url="https://example.com/cover.jpg",
        release_date="1997-05",
        avg_rating=8.5,
        review_count=42,
        nomination_count=7,
        weighted_score=8.3,
    )
    return ExploreAlbumItem(**{**defaults, **overrides})


def _group_item(**overrides) -> ExploreGroupItem:
    defaults = dict(
        id=1,
        name="Bees",
        is_public=True,
        is_global=False,
        member_count=5,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    return ExploreGroupItem(**{**defaults, **overrides})


# ==================== FIXTURES ====================

@pytest.fixture
def mock_explore_service():
    return MagicMock(spec=ExploreService)


@pytest.fixture
def client(mock_explore_service):
    mock_user = make_mock_user()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_explore_service] = lambda: mock_explore_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_explore_service):
    app.dependency_overrides[get_explore_service] = lambda: mock_explore_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== GET /explore/albums ====================

class TestExploreAlbums:
    def test_returns_200_with_items(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(
            items=[_album_item()], next_offset=20
        )
        resp = client.get("/explore/albums")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "OK Computer"
        assert data["next_offset"] == 20

    def test_passes_query_params_to_service(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(items=[], next_offset=None)
        client.get("/explore/albums?offset=40&limit=10&min_reviews=5&sort_by=most_reviewed&q=radiohead")
        mock_explore_service.get_explore_albums.assert_called_once_with(
            offset=40, limit=10, min_reviews=5, sort_by="most_reviewed", q="radiohead"
        )

    def test_q_param_forwarded(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(items=[], next_offset=None)
        client.get("/explore/albums?q=ok+computer")
        mock_explore_service.get_explore_albums.assert_called_once_with(
            offset=0, limit=20, min_reviews=None, sort_by="top_rated", q="ok computer"
        )

    def test_empty_q_treated_as_none(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(items=[], next_offset=None)
        client.get("/explore/albums?q=")
        mock_explore_service.get_explore_albums.assert_called_once_with(
            offset=0, limit=20, min_reviews=None, sort_by="top_rated", q=None
        )

    def test_invalid_sort_by_falls_back_to_top_rated(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(items=[], next_offset=None)
        client.get("/explore/albums?sort_by=garbage")
        mock_explore_service.get_explore_albums.assert_called_once_with(
            offset=0, limit=20, min_reviews=None, sort_by="top_rated", q=None
        )

    def test_requires_authentication(self, unauthed_client):
        resp = unauthed_client.get("/explore/albums")
        assert resp.status_code == 401

    def test_empty_page(self, client, mock_explore_service):
        mock_explore_service.get_explore_albums.return_value = ExploreAlbumsPage(items=[], next_offset=None)
        resp = client.get("/explore/albums")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "next_offset": None}


# ==================== GET /explore/groups ====================

class TestExploreGroups:
    def test_returns_200_with_groups(self, client, mock_explore_service):
        mock_explore_service.get_explore_groups.return_value = ExploreGroupsPage(
            items=[_group_item()], next_offset=None
        )
        resp = client.get("/explore/groups")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Bees"

    def test_passes_offset_and_limit(self, client, mock_explore_service):
        mock_explore_service.get_explore_groups.return_value = ExploreGroupsPage(items=[], next_offset=None)
        client.get("/explore/groups?offset=20&limit=5")
        mock_explore_service.get_explore_groups.assert_called_once_with(
            offset=20, limit=5, q=None, group_type="all", include_private=False
        )

    def test_q_and_group_type_forwarded(self, client, mock_explore_service):
        mock_explore_service.get_explore_groups.return_value = ExploreGroupsPage(items=[], next_offset=None)
        client.get("/explore/groups?q=jazz&group_type=human")
        mock_explore_service.get_explore_groups.assert_called_once_with(
            offset=0, limit=20, q="jazz", group_type="human", include_private=False
        )

    def test_invalid_group_type_falls_back_to_all(self, client, mock_explore_service):
        mock_explore_service.get_explore_groups.return_value = ExploreGroupsPage(items=[], next_offset=None)
        client.get("/explore/groups?group_type=nonsense")
        mock_explore_service.get_explore_groups.assert_called_once_with(
            offset=0, limit=20, q=None, group_type="all", include_private=False
        )

    def test_requires_authentication(self, unauthed_client):
        resp = unauthed_client.get("/explore/groups")
        assert resp.status_code == 401

    def test_bot_group_flag_preserved(self, client, mock_explore_service):
        mock_explore_service.get_explore_groups.return_value = ExploreGroupsPage(
            items=[_group_item(is_global=True)], next_offset=None
        )
        resp = client.get("/explore/groups")
        assert resp.json()["items"][0]["is_global"] is True


# ==================== GET /explore/stats ====================

class TestExploreStats:
    def _stats_response(self) -> SiteStatsResponse:
        return SiteStatsResponse(
            total_albums_nominated=500,
            total_reviews=3200,
            total_active_groups=12,
            total_active_members=88,
            top_rated_albums=[_album_item(id=1, title="Top")],
            bottom_rated_albums=[_album_item(id=2, title="Bottom")],
            most_nominated_artists=[
                ArtistNominationItem(artist="The Beatles", artist_url=None, nomination_count=34, unique_albums=12)
            ],
            most_nominated_albums=[_album_item(id=3, title="Popular")],
        )

    def test_returns_200_with_stats(self, client, mock_explore_service):
        mock_explore_service.get_site_stats.return_value = self._stats_response()
        resp = client.get("/explore/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_albums_nominated"] == 500
        assert data["total_reviews"] == 3200
        assert data["total_active_groups"] == 12
        assert data["total_active_members"] == 88
        assert data["top_rated_albums"][0]["title"] == "Top"
        assert data["most_nominated_artists"][0]["artist"] == "The Beatles"

    def test_requires_authentication(self, unauthed_client):
        resp = unauthed_client.get("/explore/stats")
        assert resp.status_code == 401

    def test_calls_get_site_stats(self, client, mock_explore_service):
        mock_explore_service.get_site_stats.return_value = self._stats_response()
        client.get("/explore/stats")
        mock_explore_service.get_site_stats.assert_called_once()
