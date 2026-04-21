"""Thin client for the Spotify Web API using Client Credentials and Authorization Code flows."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import jwt

from app.config import get_settings


@dataclass
class SpotifyAlbumResult:
    spotify_album_id: str
    title: str
    artist: str
    release_date: str | None
    cover_url: str | None
    genres: list[str]


def _get_client_token() -> str:
    """Obtain a Spotify access token via Client Credentials flow."""
    settings = get_settings()
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify integration not configured",
        )

    resp = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        timeout=10,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not authenticate with Spotify",
        )
    return resp.json()["access_token"]


def get_auth_url(user_id: int) -> str:
    """Build the Spotify Authorization Code URL for a user.

    The state parameter is a short-lived JWT carrying user_id to identify the user
    in the callback without requiring a server-side session.
    """
    settings = get_settings()
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_REDIRECT_URI:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Spotify integration not configured",
        )
    state = jwt.encode(
        {"user_id": user_id, "exp": datetime.now(UTC) + timedelta(seconds=300)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    params = urlencode(
        {
            "client_id": settings.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            "scope": "user-read-email user-read-private",
            "state": state,
        }
    )
    return f"https://accounts.spotify.com/authorize?{params}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange an authorization code for access/refresh tokens and fetch the Spotify user ID.

    Returns a dict with: spotify_user_id, access_token, refresh_token, expires_at.

    Raises:
        HTTPException 502: If Spotify token exchange or profile fetch fails.
    """
    settings = get_settings()
    token_resp = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        },
        auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        timeout=10,
    )
    if not token_resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Spotify token exchange failed",
        )
    token_data = token_resp.json()
    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]
    expires_at = datetime.now(UTC) + timedelta(seconds=token_data["expires_in"])

    me_resp = httpx.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not me_resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch Spotify profile",
        )
    spotify_user_id = me_resp.json()["id"]

    return {
        "spotify_user_id": spotify_user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }


def search_albums(query: str, limit: int = 10) -> list[SpotifyAlbumResult]:
    """Search Spotify for albums matching the query string."""
    token = _get_client_token()
    resp = httpx.get(
        "https://api.spotify.com/v1/search",
        params={"q": query, "type": "album", "limit": limit},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Spotify search failed",
        )

    items = resp.json().get("albums", {}).get("items", [])
    results = []
    for item in items:
        images = item.get("images", [])
        cover = images[0]["url"] if images else None
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        results.append(
            SpotifyAlbumResult(
                spotify_album_id=item["id"],
                title=item["name"],
                artist=artists,
                release_date=item.get("release_date"),
                cover_url=cover,
                genres=item.get("genres", []),
            )
        )
    return results
