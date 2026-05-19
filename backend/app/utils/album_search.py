"""Utilities for merging and deduplicating album search results across services."""

import re
import unicodedata
from dataclasses import dataclass, field

from app.utils.apple_music_client import AppleMusicAlbumResult
from app.utils.spotify_client import SpotifyAlbumResult

# Strips common edition/remaster suffixes (from Spotify's normalization).
_EDITION_RE = re.compile(
    r"[\s\-]*[\(\[]?\s*("
    r"deluxe(\s+edition)?|remastered(\s+\d{4})?|remaster(\s+\d{4})?|"
    r"\d{4}\s+remaster(ed)?|bonus\s+tracks?|anniversary\s+edition|"
    r"expanded\s+edition|special\s+edition|super\s+deluxe(\s+edition)?"
    r")\s*[\)\]]?\s*$",
    re.IGNORECASE,
)

# Strips any trailing parenthetical/bracketed group (from Apple's normalization).
_TRAILING_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]+[\)\]]\s*$")

# Strips trailing dash-separated release qualifiers (from Apple's normalization).
_TRAILING_DASH_QUALIFIER_RE = re.compile(
    r"\s*-\s*(?:EP|Single|Live|Acoustic|Demo|Instrumental|Soundtrack|OST|Radio\s+Edit|Extended)\s*$",
    re.IGNORECASE,
)


def normalize_title_for_dedup(title: str) -> str:
    """Normalize a title for cross-service deduplication.

    Combines Spotify's edition-suffix stripping with Apple's iterative parenthetical
    and dash-qualifier stripping, then lowercases and collapses whitespace.
    """
    title = _EDITION_RE.sub("", title).strip()
    changed = True
    while changed:
        changed = False
        stripped = _TRAILING_PAREN_RE.sub("", title).strip()
        if stripped != title:
            title = stripped
            changed = True
        stripped = _TRAILING_DASH_QUALIFIER_RE.sub("", title).strip()
        if stripped != title:
            title = stripped
            changed = True
    decomposed = unicodedata.normalize("NFKD", title)
    without_combining = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    without_combining = re.sub(r"[*!]", "", without_combining)
    return re.sub(r"\s+", " ", without_combining.lower()).strip()


@dataclass
class UnifiedAlbumResult:
    spotify_album_id: str | None
    apple_music_album_id: str | None
    title: str
    artist: str
    release_date: str | None
    cover_url: str | None
    genres: list[str] = field(default_factory=list)


def merge_search_results(
    spotify: list[SpotifyAlbumResult],
    apple: list[AppleMusicAlbumResult],
) -> list[UnifiedAlbumResult]:
    """Merge Spotify and Apple Music search results, deduplicating by normalized title + artist.

    Matched pairs use Spotify metadata as the primary source (cover, title, artist) while
    including the Apple Music ID.  Ordering: matched pairs first, then Spotify-only, then
    Apple-only.
    """
    # Index Apple results by (normalized_title, normalized_artist)
    apple_by_key: dict[tuple[str, str], AppleMusicAlbumResult] = {}
    for a in apple:
        key = (normalize_title_for_dedup(a.title), a.artist.lower())
        if key not in apple_by_key:
            apple_by_key[key] = a

    matched: list[UnifiedAlbumResult] = []
    spotify_only: list[UnifiedAlbumResult] = []
    matched_apple_ids: set[str] = set()

    for s in spotify:
        key = (normalize_title_for_dedup(s.title), s.artist.lower())
        apple_match = apple_by_key.get(key)
        if apple_match:
            matched_apple_ids.add(apple_match.id)
            matched.append(
                UnifiedAlbumResult(
                    spotify_album_id=s.spotify_album_id,
                    apple_music_album_id=apple_match.id,
                    title=s.title,
                    artist=s.artist,
                    release_date=s.release_date,
                    cover_url=s.cover_url,
                    genres=apple_match.genres,
                )
            )
        else:
            spotify_only.append(
                UnifiedAlbumResult(
                    spotify_album_id=s.spotify_album_id,
                    apple_music_album_id=None,
                    title=s.title,
                    artist=s.artist,
                    release_date=s.release_date,
                    cover_url=s.cover_url,
                    genres=[],
                )
            )

    apple_only: list[UnifiedAlbumResult] = []
    for a in apple:
        if a.id not in matched_apple_ids:
            apple_only.append(
                UnifiedAlbumResult(
                    spotify_album_id=None,
                    apple_music_album_id=a.id,
                    title=a.title,
                    artist=a.artist,
                    release_date=a.release_date,
                    cover_url=a.cover_url,
                    genres=a.genres,
                )
            )

    return matched + spotify_only + apple_only
