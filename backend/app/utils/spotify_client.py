"""Thin client for the Spotify Web API using Client Credentials flow."""

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

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
