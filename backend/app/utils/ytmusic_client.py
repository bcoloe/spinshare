"""YouTube Music client for resolving album browse IDs."""

from ytmusicapi import YTMusic


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
