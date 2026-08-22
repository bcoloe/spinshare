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

    Handles:
      - https://open.spotify.com/album/{id}?si=...
      - https://open.spotify.com/intl-de/album/{id}   (localised share links)

    Matched at the end of the path rather than anchored at the start, because
    Spotify prefixes a locale segment for non-English clients.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    m = re.search(r"/album/([A-Za-z0-9]+)/?$", parsed.path)
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


# Shapes a bare (non-URL) identifier must match, per service. Deliberately loose:
# their job is to reject something pasted in wholesale by mistake (a URL for another
# service, a sentence, a file path), not to prove an ID is real. Spotify IDs are
# base62 in practice, but pinning that here would reject the opaque identifiers
# already stored by earlier code paths for no user-visible benefit — and the admin
# editor has always accepted bare IDs. Anything genuinely wrong is a URL, and the
# detect_service branch above catches those with a far better error message.
_BARE_ID_PATTERNS = {
    MusicService.Spotify: re.compile(r"^[A-Za-z0-9_-]+$"),
    MusicService.AppleMusic: re.compile(r"^\d+$"),
    MusicService.YouTubeMusic: re.compile(r"^[A-Za-z0-9_-]+$"),
}

_EXTRACTORS = {
    MusicService.Spotify: extract_spotify_album_id,
    MusicService.AppleMusic: extract_apple_music_album_id,
    MusicService.YouTubeMusic: extract_youtube_music_id,
}

_SERVICE_LABELS = {
    MusicService.Spotify: "Spotify",
    MusicService.AppleMusic: "Apple Music",
    MusicService.YouTubeMusic: "YouTube Music",
    MusicService.Bandcamp: "Bandcamp",
}


def coerce_album_identifier(service: MusicService, value: str) -> str:
    """Accept either a full share URL or a bare ID for `service`; return the bare ID.

    People copy share links, not IDs — ``https://open.spotify.com/album/{id}?si=...``
    rather than ``{id}``. This normalises both into the form the album column stores,
    so callers never have to care which one they were handed.

    Only the three ID-based services are supported. Bandcamp and Wikipedia links are
    stored as full URLs and are validated by their own domain checks instead.

    Raises:
        ValueError: If the value is a URL belonging to a different service, a URL
            no album ID can be extracted from, or a bare value of the wrong shape.
    """
    if service not in _EXTRACTORS:
        raise ValueError(f"{_SERVICE_LABELS.get(service, service)} links are stored as full URLs")

    value = value.strip()
    if not value:
        raise ValueError("Value cannot be empty")

    detected = detect_service(value)
    if detected is not None and detected != service:
        raise ValueError(
            f"That looks like a {_SERVICE_LABELS[detected]} link — "
            f"paste it in the {_SERVICE_LABELS[detected]} field instead"
        )

    if detected == service:
        extracted = _EXTRACTORS[service](value)
        if not extracted:
            raise ValueError(f"Could not find an album ID in that {_SERVICE_LABELS[service]} link")
        return extracted

    # Not a URL we recognise — treat it as a bare ID, which is what the admin
    # editor accepted before share links were supported.
    if not _BARE_ID_PATTERNS[service].match(value):
        raise ValueError(
            f"Not a valid {_SERVICE_LABELS[service]} album link or ID"
        )
    return value
