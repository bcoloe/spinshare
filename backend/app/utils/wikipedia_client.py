"""Best-effort client for the MediaWiki Action API to resolve album/artist Wikipedia pages.

Resolves a single Wikipedia URL for an album, preferring the album's own page and falling
back to the artist's page. Used for lazy, self-healing enrichment of the ``albums`` table, so
every function silently returns ``None`` on any failure to avoid breaking background tasks.
"""

import difflib
import logging
import re
import unicodedata
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

_API_URL = "https://en.wikipedia.org/w/api.php"
_PAGE_BASE_URL = "https://en.wikipedia.org/wiki/"

# MediaWiki etiquette: identify the client with a descriptive User-Agent.
_USER_AGENT = "spinshare/1.0 (album review app; https://github.com/spinshare)"

_TITLE_THRESHOLD = 0.82
_ARTIST_THRESHOLD = 0.72

# Strips any trailing parenthetical group from a page title, e.g. the disambiguation
# suffixes Wikipedia adds like "1989 (Taylor Swift album)" or "Thriller (album)".
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, and drop punctuation for fuzzy comparison."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_combining = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    without_punct = re.sub(r"[^\w\s]", "", without_combining)
    return re.sub(r"\s+", " ", without_punct.lower()).strip()


def _normalize_page_title(title: str) -> str:
    """Strip a trailing disambiguation parenthetical, then normalize.

    Applied iteratively to handle stacked qualifiers like "Weezer (Blue Album)".
    """
    changed = True
    while changed:
        stripped = _TRAILING_PAREN_RE.sub("", title).strip()
        changed = stripped != title
        title = stripped
    return _normalize_text(title)


def _page_url(title: str) -> str:
    """Build the canonical article URL from a MediaWiki page title."""
    return _PAGE_BASE_URL + quote(title.replace(" ", "_"))


def _search_titles(srsearch: str) -> list[str]:
    """Return candidate page titles for a search query, or [] on any failure."""
    try:
        resp = httpx.get(
            _API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": srsearch,
                "srlimit": 5,
                "format": "json",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
    except Exception:
        log.warning("Wikipedia search request failed for %r", srsearch)
        return []

    if not resp.is_success:
        log.warning("Wikipedia search returned %d for %r", resp.status_code, srsearch)
        return []

    results = resp.json().get("query", {}).get("search", [])
    return [r["title"] for r in results if r.get("title")]


def _best_match_url(srsearch: str, expected: str, threshold: float) -> str | None:
    """Search Wikipedia and return the URL of the best title clearing ``threshold``, else None."""
    normalized_expected = _normalize_page_title(expected)
    best_title: str | None = None
    best_score = 0.0
    for title in _search_titles(srsearch):
        score = difflib.SequenceMatcher(
            None, normalized_expected, _normalize_page_title(title)
        ).ratio()
        if score >= threshold and score > best_score:
            best_score = score
            best_title = title
    return _page_url(best_title) if best_title else None


def find_wikipedia_url(title: str, artist: str) -> str | None:
    """Resolve a Wikipedia URL for an album, preferring its page over the artist's.

    1. Search for the album page ("<title> <artist> album") and confirm the title match.
    2. Fall back to the artist page and confirm the artist match.
    3. Return None if neither clears its similarity threshold.

    Silently returns None on any failure to stay safe as a background task.
    """
    try:
        album_url = _best_match_url(f"{title} {artist} album", title, _TITLE_THRESHOLD)
        if album_url:
            return album_url
        return _best_match_url(artist, artist, _ARTIST_THRESHOLD)
    except Exception:
        log.warning("Wikipedia lookup failed for %r by %r", title, artist)
        return None
