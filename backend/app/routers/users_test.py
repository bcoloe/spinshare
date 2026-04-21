# backend/app/routers/users_test.py
#
# Router tests: verify HTTP status codes, request/response shapes, and auth
# enforcement for Spotify OAuth endpoints. UserService is fully mocked.

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from jose import jwt

from app.config import get_settings
from app.dependencies import get_current_user, get_user_service
from app.main import app
from app.routers.conftest import make_mock_user
from app.services.user_service import UserService

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _make_state(user_id: int, secret: str, exp_offset: int = 300) -> str:
    return jwt.encode(
        {"user_id": user_id, "exp": datetime.now(UTC) + timedelta(seconds=exp_offset)},
        secret,
        algorithm="HS256",
    )


@pytest.fixture
def mock_user():
    return make_mock_user()


@pytest.fixture
def mock_user_service():
    return MagicMock(spec=UserService)


@pytest.fixture
def client(mock_user, mock_user_service):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(mock_user_service):
    app.dependency_overrides[get_user_service] = lambda: mock_user_service
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


# ==================== SPOTIFY CONNECT ====================

class TestSpotifyToken:
    def test_returns_access_token(self, client, mock_user_service):
        mock_user_service.get_valid_spotify_token.return_value = "valid_access_token"
        resp = client.get("/users/spotify/token")
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "valid_access_token"

    def test_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/users/spotify/token")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_404_when_not_connected(self, client, mock_user_service):
        mock_user_service.get_valid_spotify_token.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No Spotify account connected"
        )
        resp = client.get("/users/spotify/token")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_401_when_token_expired(self, client, mock_user_service):
        mock_user_service.get_valid_spotify_token.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify connection expired — please reconnect",
        )
        resp = client.get("/users/spotify/token")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


class TestSpotifyConnectUrl:
    def test_returns_spotify_url(self, client):
        with patch("app.routers.users.spotify_client.get_auth_url", return_value="https://accounts.spotify.com/authorize?foo=bar") as mock_get:
            resp = client.get("/users/spotify/connect-url")

        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert data["url"].startswith("https://accounts.spotify.com/authorize")
        mock_get.assert_called_once_with(1)

    def test_requires_auth(self, unauthed_client):
        resp = unauthed_client.get("/users/spotify/connect-url")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_propagates_503_when_not_configured(self, client):
        with patch(
            "app.routers.users.spotify_client.get_auth_url",
            side_effect=HTTPException(status_code=503, detail="Spotify integration not configured"),
        ):
            resp = client.get("/users/spotify/connect-url")
        assert resp.status_code == 503


class TestSpotifyDisconnect:
    def test_disconnect_returns_204(self, client, mock_user_service):
        resp = client.delete("/users/spotify")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        mock_user_service.disconnect_spotify.assert_called_once_with(1)

    def test_requires_auth(self, unauthed_client):
        resp = unauthed_client.delete("/users/spotify")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_404_when_no_connection(self, client, mock_user_service):
        mock_user_service.disconnect_spotify.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No Spotify account connected"
        )
        resp = client.delete("/users/spotify")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ==================== SPOTIFY CALLBACK ====================

class TestSpotifyCallback:
    def _valid_state(self) -> str:
        settings = get_settings()
        return _make_state(user_id=1, secret=settings.SECRET_KEY)

    def test_success_redirects_to_frontend_with_connected(self, unauthed_client, mock_user_service):
        tokens = {
            "spotify_user_id": "spotify_abc",
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": _NOW + timedelta(hours=1),
        }
        with patch("app.routers.users.spotify_client.exchange_code_for_tokens", return_value=tokens):
            resp = unauthed_client.get(
                "/users/spotify/callback",
                params={"code": "authcode", "state": self._valid_state()},
            )

        assert resp.status_code in (302, 307)
        assert "spotify=connected" in resp.headers["location"]
        mock_user_service.connect_spotify.assert_called_once()

    def test_error_param_redirects_with_error(self, unauthed_client):
        resp = unauthed_client.get(
            "/users/spotify/callback",
            params={"error": "access_denied", "state": "whatever"},
        )
        assert resp.status_code in (302, 307)
        assert "spotify=error" in resp.headers["location"]

    def test_missing_code_redirects_with_error(self, unauthed_client):
        resp = unauthed_client.get(
            "/users/spotify/callback",
            params={"state": self._valid_state()},
        )
        assert resp.status_code in (302, 307)
        assert "spotify=error" in resp.headers["location"]

    def test_invalid_state_redirects_with_error(self, unauthed_client):
        resp = unauthed_client.get(
            "/users/spotify/callback",
            params={"code": "authcode", "state": "tampered.jwt.value"},
        )
        assert resp.status_code in (302, 307)
        assert "spotify=error" in resp.headers["location"]

    def test_expired_state_redirects_with_error(self, unauthed_client):
        settings = get_settings()
        expired_state = _make_state(user_id=1, secret=settings.SECRET_KEY, exp_offset=-60)
        resp = unauthed_client.get(
            "/users/spotify/callback",
            params={"code": "authcode", "state": expired_state},
        )
        assert resp.status_code in (302, 307)
        assert "spotify=error" in resp.headers["location"]

    def test_token_exchange_failure_redirects_with_error(self, unauthed_client):
        with patch(
            "app.routers.users.spotify_client.exchange_code_for_tokens",
            side_effect=HTTPException(status_code=502, detail="Spotify token exchange failed"),
        ):
            resp = unauthed_client.get(
                "/users/spotify/callback",
                params={"code": "authcode", "state": self._valid_state()},
            )
        assert resp.status_code in (302, 307)
        assert "spotify=error" in resp.headers["location"]
