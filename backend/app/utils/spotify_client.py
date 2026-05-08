"""Thin client for the Spotify Web API using Client Credentials and Authorization Code flows."""

import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode


import httpx
from fastapi import HTTPException, status
from jose import jwt

from app.config import get_settings

log = logging.getLogger(__name__)

# Module-level cache for the Client Credentials token (valid ~1 hour).
_cc_token: str | None = None
_cc_token_expires_at: float = 0.0

# Absolute ceiling on any single Retry-After value we will honour.
_MAX_RETRY_AFTER = 60

# Matches common edition/remaster suffixes so variants of the same album collapse to one result.
_EDITION_RE = re.compile(
    r"[\s\-]*[\(\[]?\s*("
    r"deluxe(\s+edition)?|remastered(\s+\d{4})?|remaster(\s+\d{4})?|"
    r"\d{4}\s+remaster(ed)?|bonus\s+tracks?|anniversary\s+edition|"
    r"expanded\s+edition|special\s+edition|super\s+deluxe(\s+edition)?"
    r")\s*[\)\]]?\s*$",
    re.IGNORECASE,
)


def _normalized_title(title: str) -> str:
    return _EDITION_RE.sub("", title).strip().lower()


@dataclass
class SpotifyAlbumResult:
    spotify_album_id: str
    title: str
    artist: str
    release_date: str | None
    cover_url: str | None
    genres: list[str]


def _get_client_token() -> str:
    """Obtain a Spotify access token via Client Credentials flow, reusing a cached token when valid."""
    global _cc_token, _cc_token_expires_at

    if _cc_token and time.time() < _cc_token_expires_at - 60:
        return _cc_token

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
    data = resp.json()
    _cc_token = data["access_token"]
    _cc_token_expires_at = time.time() + data.get("expires_in", 3600)
    return _cc_token


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
            "scope": "streaming user-read-email user-read-private user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-library-modify user-library-read",
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


def refresh_access_token(refresh_token: str) -> dict:
    """Use a refresh token to obtain a new access token.

    Returns a dict with: access_token, expires_at, and optionally a new refresh_token.

    Raises:
        HTTPException 401: If Spotify rejects the refresh token (revoked/expired).
        HTTPException 502: On unexpected Spotify API errors.
    """
    settings = get_settings()
    resp = httpx.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        timeout=10,
    )
    if resp.status_code in (400, 401):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Spotify connection expired — please reconnect",
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Spotify token refresh failed",
        )
    data = resp.json()
    result = {
        "access_token": data["access_token"],
        "expires_at": datetime.now(UTC) + timedelta(seconds=data["expires_in"]),
    }
    # Spotify may rotate the refresh token
    if "refresh_token" in data:
        result["refresh_token"] = data["refresh_token"]
    return result


def search_albums(
    query: str = "",
    limit: int = 10,
    *,
    artist: str | None = None,
    album: str | None = None,
    max_retry_after: int = 10,
) -> list[SpotifyAlbumResult]:
    """Search Spotify for albums, with optional artist/album field filters.

    max_retry_after controls the per-attempt Retry-After ceiling before aborting.
    User-facing callers should use the default (10s) so errors surface quickly.
    Long-running batch callers (e.g. the bot) should pass max_retry_after=60.
    """
    token = _get_client_token()
    parts: list[str] = []
    if artist:
        parts.append(f"artist:{artist}")
    if album:
        parts.append(f"album:{album}")
    if query:
        parts.append(query)
    q = " ".join(parts)
    effective_max = min(max_retry_after, _MAX_RETRY_AFTER)
    params = {"q": q, "type": "album", "limit": limit}
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.get("https://api.spotify.com/v1/search", params=params, headers=headers, timeout=10)
    for attempt in range(3):
        if resp.status_code != 429:
            break
        retry_after = int(resp.headers.get("Retry-After", 10))
        if retry_after > effective_max:
            log.error(
                "Spotify rate limit is severe (Retry-After: %ds > threshold: %ds). "
                "Aborting — credentials may be locked out.",
                retry_after,
                effective_max,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Spotify rate limit exceeded (Retry-After: {retry_after}s)",
            )
        log.warning("Spotify rate limited (attempt %d/3); retrying after %ds", attempt + 1, retry_after)
        time.sleep(retry_after)
        resp = httpx.get("https://api.spotify.com/v1/search", params=params, headers=headers, timeout=10)
    if resp.status_code == 429:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Spotify rate limit exceeded after retries",
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Spotify search failed",
        )

    items = resp.json().get("albums", {}).get("items", [])
    seen: set[tuple[str, str]] = set()
    results = []
    for item in items:
        images = item.get("images", [])
        cover = images[0]["url"] if images else None
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        key = (_normalized_title(item["name"]), artists.lower())
        if key in seen:
            continue
        seen.add(key)
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


def get_albums_batch(ids: list[str]) -> list[SpotifyAlbumResult]:
    """Fetch album details for multiple Spotify album IDs using the batch endpoint.

    Spotify allows up to 20 IDs per request; this function chunks automatically.
    Null entries in the response (invalid IDs) are silently skipped.
    """
    if not ids:
        return []
    token = _get_client_token()
    headers = {"Authorization": f"Bearer {token}"}
    results: list[SpotifyAlbumResult] = []
    chunk_size = 20
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        resp = httpx.get(
            "https://api.spotify.com/v1/albums",
            params={"ids": ",".join(chunk)},
            headers=headers,
            timeout=10,
        )
        for attempt in range(3):
            if resp.status_code != 429:
                break
            retry_after = int(resp.headers.get("Retry-After", 10))
            if retry_after > _MAX_RETRY_AFTER:
                log.error(
                    "Spotify rate limit is severe during batch fetch (Retry-After: %ds). Aborting.",
                    retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Spotify rate limit exceeded (Retry-After: {retry_after}s)",
                )
            log.warning(
                "Spotify rate limited during batch fetch (attempt %d/3); retrying after %ds",
                attempt + 1,
                retry_after,
            )
            time.sleep(retry_after)
            resp = httpx.get(
                "https://api.spotify.com/v1/albums",
                params={"ids": ",".join(chunk)},
                headers=headers,
                timeout=10,
            )
        if resp.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Spotify rate limit exceeded after retries",
            )
        if not resp.is_success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Spotify batch album fetch failed",
            )
        for item in resp.json().get("albums", []):
            if item is None:
                continue
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
