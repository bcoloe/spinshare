"""YouTube Music client for resolving album browse IDs."""

import logging

from ytmusicapi import YTMusic

log = logging.getLogger(__name__)


def search_album_browse_id(title: str, artist: str) -> str | None:
    """Search YouTube Music for an album and return its browseId.

    Uses unauthenticated mode — sufficient for search. Returns None if no
    match is found or if the search call fails for any reason.
    """
    yt = YTMusic()
    results = yt.search(f"{artist} {title}", filter="albums", limit=1)
    if results:
        return results[0].get("browseId")
    return None


def get_album_details(ytm_id: str) -> dict | None:
    """Fetch album metadata from YouTube Music by browse ID or playlist ID.

    Accepts:
      - MPREb_... style browseId (direct album lookup)
      - OLAK5uy_... style playlist ID (converted to browseId first)

    Returns a dict with keys: title, artist, release_date, cover_url, browse_id.
    Returns None on any failure.
    """
    try:
        yt = YTMusic()
        browse_id = ytm_id
        if ytm_id.startswith("OLAK5uy_"):
            browse_id = yt.get_album_browse_id(ytm_id)
            if not browse_id:
                log.warning("Could not convert YouTube Music playlist ID %r to browse ID", ytm_id)
                return None

        data = yt.get_album(browse_id)
        if not data:
            return None

        artists_list = data.get("artists") or []
        if artists_list:
            artist = ", ".join(a["name"] for a in artists_list if a.get("name"))
        else:
            artist = data.get("artist", "")

        thumbnails = data.get("thumbnails") or []
        cover_url = thumbnails[-1]["url"] if thumbnails else None

        return {
            "title": data.get("title", ""),
            "artist": artist,
            "release_date": str(data["year"]) if data.get("year") else None,
            "cover_url": cover_url,
            "browse_id": browse_id,
        }
    except Exception:
        log.warning("YouTube Music album fetch failed for ID %r", ytm_id)
        return None
