"""Music service URL detection and ID extraction."""

import logging
import re
from enum import StrEnum
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


class MusicService(StrEnum):
    Spotify = "spotify"
    AppleMusic = "apple_music"
    YouTubeMusic = "youtube_music"
    Bandcamp = "bandcamp"


def detect_service(url: str) -> MusicService | None:
    """Detect which music service a URL belongs to. Returns None if unrecognized."""
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    netloc = parsed.netloc.lower()
    if netloc in ("open.spotify.com", "spotify.com") or netloc.endswith(".spotify.com"):
        return MusicService.Spotify
    if netloc in ("music.apple.com",) or netloc.endswith(".music.apple.com"):
        return MusicService.AppleMusic
    if netloc == "music.youtube.com":
        return MusicService.YouTubeMusic
    if netloc == "bandcamp.com" or netloc.endswith(".bandcamp.com"):
        return MusicService.Bandcamp
    return None


def extract_spotify_album_id(url: str) -> str | None:
    """Extract the album ID from a Spotify album URL.

    Handles: https://open.spotify.com/album/{id}?si=...
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    # Path should be /album/{id}
    m = re.match(r"^/album/([A-Za-z0-9]+)/?$", parsed.path)
    return m.group(1) if m else None


def extract_apple_music_album_id(url: str) -> str | None:
    """Extract the numeric album ID from an Apple Music URL.

    Handles:
      - https://music.apple.com/{storefront}/album/{title-slug}/{id}
      - https://music.apple.com/{storefront}/album/{id}
    The album ID is always the last purely-numeric path component.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    # Find the last numeric segment — that's the album ID
    for part in reversed(parts):
        if re.fullmatch(r"\d+", part):
            return part
    return None


def scrape_bandcamp_metadata(url: str) -> dict | None:
    """Fetch a Bandcamp album page and extract title, artist, and cover URL from Open Graph tags.

    Returns a dict with 'title', 'artist', and optional 'cover_url' keys, or None on any failure.
    The og:title on Bandcamp album pages is formatted as: "Album Name, by Artist Name".
    """
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; spinshare/1.0)"},
            follow_redirects=True,
            timeout=10,
        )
    except Exception:
        log.warning("Bandcamp page fetch failed for %r", url)
        return None

    if not resp.is_success:
        log.warning("Bandcamp page returned %d for %r", resp.status_code, url)
        return None

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        og_title = soup.find("meta", property="og:title")
        if not og_title:
            return None
        raw = og_title.get("content", "")
        # Format: "Album Name, by Artist Name"
        m = re.match(r"^(.+),\s+by\s+(.+)$", raw, re.IGNORECASE)
        if not m:
            return None
        result: dict = {"title": m.group(1).strip(), "artist": m.group(2).strip()}
        og_image = soup.find("meta", property="og:image")
        if og_image:
            cover = og_image.get("content", "").strip()
            if cover:
                result["cover_url"] = cover
        return result
    except Exception:
        log.warning("Bandcamp metadata parse failed for %r", url)
        return None


def extract_youtube_music_id(url: str) -> str | None:
    """Extract the YouTube Music album identifier from a URL.

    Handles:
      - https://music.youtube.com/browse/{browseId}  (MPREb_... format)
      - https://music.youtube.com/playlist?list={playlistId}  (OLAK5uy_... format)

    Returns the raw ID (either browseId or playlistId) without conversion.
    The caller (get_album_details) handles OLAK5uy → MPREb conversion.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    # /browse/{id}
    m = re.match(r"^/browse/([^/?]+)", parsed.path)
    if m:
        return m.group(1)
    # /playlist?list={id}
    if "/playlist" in parsed.path:
        params = parse_qs(parsed.query)
        ids = params.get("list", [])
        return ids[0] if ids else None
    return None
