"""Odesli client for resolving Apple Music album URLs from Spotify IDs."""

import httpx

_ODESLI_URL = "https://api.song.link/v1-alpha.1/links"


def get_apple_music_url(spotify_album_id: str) -> str | None:
    """Resolve an Apple Music URL for a Spotify album via Odesli.

    Returns None if no match is found or if the API call fails for any reason.
    """
    spotify_url = f"https://open.spotify.com/album/{spotify_album_id}"
    resp = httpx.get(
        _ODESLI_URL,
        params={"url": spotify_url, "userCountry": "US"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json().get("linksByPlatform", {}).get("appleMusic", {}).get("url")
