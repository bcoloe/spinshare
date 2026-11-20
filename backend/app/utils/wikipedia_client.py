"""Best-effort client for the MediaWiki Action API to resolve album/artist Wikipedia pages.

Resolves a single Wikipedia URL for an album, preferring the album's own page and falling
back to the artist's page. Used for lazy, self-healing enrichment of the ``albums`` table, so
every function silently returns ``None`` on any failure to avoid breaking background tasks.

Matching on page title alone is not enough: a self-titled album ("Broken Bells" by Broken
Bells) shares its title with the band's page, and a generic title ("Blue") collides with
unrelated articles. Every candidate is therefore *classified* using the page's Wikipedia
short description (e.g. "2010 studio album by Broken Bells") and its categories (e.g.
"Category:Broken Bells albums"):

- an album page must look like an album AND name the expected artist;
- an artist page must look like a musical act and must not itself be an album or song.

Candidates come from two sources, cheapest and most precise first: Wikipedia's own naming
conventions for album articles ("Title (Artist album)", "Title (album)", "Title"), then
full-text search.
"""

import difflib
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)

_API_URL = "https://en.wikipedia.org/w/api.php"
_PAGE_BASE_URL = "https://en.wikipedia.org/wiki/"

# MediaWiki etiquette: identify the client with a descriptive User-Agent.
_USER_AGENT = "spinshare/1.0 (album review app; https://github.com/spinshare)"

_TITLE_THRESHOLD = 0.82
# Artist names are matched near-exactly: "Mavi" must not match "Mavis". The slack absorbs
# stylization only ("A$AP Rocky" vs "ASAP Rocky").
_ARTIST_THRESHOLD = 0.9
_SEARCH_LIMIT = 10

# Strips any trailing parenthetical group from a page title, e.g. the disambiguation
# suffixes Wikipedia adds like "1989 (Taylor Swift album)" or "Thriller (album)".
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")

# Release-variant noise streaming services append to album titles, which never appears in
# the Wikipedia article title: "Abbey Road (Remastered 2019)", "Rumours [Super Deluxe]",
# "Blue - 2005 Remaster".
_VARIANT_WORDS = (
    r"remaster(?:ed)?|deluxe|edition|anniversary|expanded|bonus|reissue|mono|stereo|"
    r"explicit|special|collector'?s|legacy|motion picture|soundtrack|music from"
)
_VARIANT_PAREN_RE = re.compile(
    rf"\s*[(\[](?:(?:with|feat\.?|featuring)\s[^)\]]*|[^)\]]*\b(?:{_VARIANT_WORDS})\b[^)\]]*)"
    rf"[)\]]\s*$",
    re.IGNORECASE,
)
_VARIANT_DASH_RE = re.compile(rf"\s+-\s+[^-]*\b(?:{_VARIANT_WORDS})\b.*$", re.IGNORECASE)

# Characters MediaWiki forbids in page titles; a candidate containing one is skipped.
_INVALID_TITLE_CHARS = set("#<>[]|{}")

_ALBUM_DESC_RE = re.compile(r"\b(?:album|ep|extended play|mixtape|soundtrack)\b")
_SONG_DESC_RE = re.compile(r"\b(?:song|single)\b")
_ALBUM_CATEGORY_RE = re.compile(r"\b(?:albums|eps|mixtapes|soundtracks)$")
_ACT_DESC_RE = re.compile(
    r"\b(?:band|group|duo|trio|quartet|ensemble|orchestra|collective|supergroup|"
    r"musician|singer|rapper|songwriter|vocalist|dj|producer|composer|guitarist|"
    r"pianist|drummer|bassist|multiinstrumentalist|artist)\b"
)
_ACT_CATEGORY_RE = re.compile(
    r"\b(?:musical groups|musicians|singers|rappers|songwriters|record producers|"
    r"composers|guitarists|pianists|drummers|djs)\b"
)


class _LookupError(Exception):
    """A MediaWiki request failed, so absence of a match proves nothing."""


@dataclass(frozen=True)
class _Page:
    """A Wikipedia article plus the metadata used to classify it."""

    title: str
    shortdesc: str  # normalized
    categories: tuple[str, ...]  # normalized, "Category:" prefix dropped
    disambiguation: bool


def _normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, spell out "&", and drop punctuation for fuzzy comparison."""
    decomposed = unicodedata.normalize("NFKD", text.replace("&", " and "))
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


def _page_qualifier(title: str) -> str:
    """Return the normalized trailing parenthetical of a page title, e.g. "radiohead album"."""
    match = _TRAILING_PAREN_RE.search(title)
    return _normalize_text(match.group(0)) if match else ""


def _clean_album_title(title: str) -> str:
    """Drop release-variant suffixes ("(Deluxe Edition)", "- 2011 Remaster") from a title."""
    changed = True
    while changed:
        stripped = _VARIANT_DASH_RE.sub("", _VARIANT_PAREN_RE.sub("", title)).strip()
        changed = stripped != title and bool(stripped)
        if changed:
            title = stripped
    return title


def _artist_names(artist: str) -> list[str]:
    """Return the names to verify against: the full credit, then each comma-split artist.

    Spotify joins multiple artists with ", ", but some single acts contain commas
    ("Crosby, Stills, Nash & Young"), so the full string is always tried first.
    """
    names = [artist.strip()]
    parts = [p.strip() for p in artist.split(",") if p.strip()]
    if len(parts) > 1:
        names.extend(parts)
    return [n for n in names if n]


def _page_url(title: str) -> str:
    """Build the canonical article URL from a MediaWiki page title."""
    return _PAGE_BASE_URL + quote(title.replace(" ", "_"))


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


# ==================== API ====================


def _query_pages(params: dict) -> list[_Page]:
    """Run a page query with classification metadata attached.

    Raises ``_LookupError`` on any request failure (including rate limiting), so callers
    never mistake an outage for "no such page". Pages come back ordered by search rank
    when ``generator=search`` is used, else in the order MediaWiki returns them. Missing pages are dropped; redirects are followed.
    """
    try:
        resp = httpx.get(
            _API_URL,
            params={
                "action": "query",
                "format": "json",
                "formatversion": 2,
                "redirects": 1,
                "prop": "pageprops|categories",
                "ppprop": "wikibase-shortdesc|disambiguation",
                "clshow": "!hidden",
                "cllimit": "max",
                **params,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
    except Exception as exc:
        raise _LookupError(f"request failed for {params!r}") from exc

    if not resp.is_success:
        raise _LookupError(f"HTTP {resp.status_code} for {params!r}")

    raw_pages = resp.json().get("query", {}).get("pages", [])
    raw_pages = sorted(raw_pages, key=lambda p: p.get("index", 0))
    pages = []
    for raw in raw_pages:
        if raw.get("missing") or raw.get("invalid") or not raw.get("title"):
            continue
        props = raw.get("pageprops", {})
        pages.append(
            _Page(
                title=raw["title"],
                shortdesc=_normalize_text(props.get("wikibase-shortdesc", "")),
                categories=tuple(
                    _normalize_text(c["title"].split(":", 1)[-1])
                    for c in raw.get("categories", [])
                    if c.get("title")
                ),
                disambiguation="disambiguation" in props,
            )
        )
    return pages


def _lookup_titles(titles: list[str]) -> list[_Page]:
    """Fetch the given exact page titles (those that exist), preserving the given order."""
    valid = list(dict.fromkeys(t for t in titles if t and not _INVALID_TITLE_CHARS & set(t)))
    if not valid:
        return []
    order = {t: i for i, t in enumerate(valid)}
    pages = _query_pages({"titles": "|".join(valid)})
    # Redirect targets are not in ``order``; keep them after the exact hits.
    return sorted(pages, key=lambda p: order.get(p.title, len(order)))


def _search(query: str) -> list[_Page]:
    """Full-text search, returning the top results in rank order."""
    return _query_pages({"generator": "search", "gsrsearch": query, "gsrlimit": _SEARCH_LIMIT})


# ==================== CLASSIFICATION ====================


def _is_album_page(page: _Page) -> bool:
    """Whether the page is about an album/EP/mixtape/soundtrack (not a song or an act)."""
    if page.disambiguation:
        return False
    if page.shortdesc:
        return bool(_ALBUM_DESC_RE.search(page.shortdesc)) and not _SONG_DESC_RE.search(
            page.shortdesc
        )
    return any(_ALBUM_CATEGORY_RE.search(c) for c in page.categories)


def _is_act_page(page: _Page) -> bool:
    """Whether the page is about a musician or musical group."""
    if page.disambiguation or _is_album_page(page):
        return False
    if page.shortdesc and _SONG_DESC_RE.search(page.shortdesc):
        return False
    return bool(_ACT_DESC_RE.search(page.shortdesc)) or any(
        _ACT_CATEGORY_RE.search(c) for c in page.categories
    )


def _names_match(candidate: str, name: str) -> bool:
    """Near-exact comparison of two normalized artist names, ignoring a leading "the"."""
    a, b = candidate.removeprefix("the "), name.removeprefix("the ")
    return bool(a and b) and _similarity(a, b) >= _ARTIST_THRESHOLD


def _credited_names(page: _Page) -> list[str]:
    """Normalized artist credits a page exposes: description, title qualifier, categories."""
    credits = []
    # "2010 studio album by Broken Bells" / "album by American rapper ASAP Rocky"
    by = re.search(r"\bby (.+)$", page.shortdesc)
    if by:
        credits.append(by.group(1))
        credits.extend(by.group(1).split(" and "))
    # "Blue (Joni Mitchell album)" -> "joni mitchell"
    qualifier = re.sub(
        r"^\d{4} |\b(?:album|ep|mixtape|soundtrack)$", "", _page_qualifier(page.title)
    )
    credits.append(qualifier.strip())
    # "Category:Broken Bells albums" -> "broken bells"
    credits.extend(_ALBUM_CATEGORY_RE.sub("", c).strip() for c in page.categories)
    return [c for c in credits if c]


def _credits_artist(page: _Page, artist: str) -> bool:
    """Whether the page attributes the album to ``artist`` (any of its credited names)."""
    credits = _credited_names(page)
    for name in (_normalize_text(n) for n in _artist_names(artist)):
        for credit in credits:
            # Compare the edges too, tolerating descriptors on either side:
            # "american rapper asap rocky", "john powell film composer".
            words, n = credit.split(), len(name.split())
            edges = (credit, " ".join(words[:n]), " ".join(words[-n:]))
            if any(_names_match(edge, name) for edge in edges):
                return True
    return False


# ==================== RESOLUTION ====================


def _album_score(page: _Page, title: str) -> float:
    """Title similarity, comparing both the raw and the variant-stripped album title.

    The raw comparison keeps distinct releases distinct ("Red (Taylor's Version)" has its
    own article); the stripped ones handle "(Deluxe Edition)" noise and subtitles that only
    the streaming service carries. Stripping a parenthetical the release's own article keeps
    in its title is discounted slightly, so the exact article wins a tie.
    """
    full_page = _normalize_text(page.title)
    base_page = _normalize_page_title(page.title)
    exact = max(
        _similarity(_normalize_text(title), full_page),
        _similarity(_normalize_text(title), base_page),
        _similarity(_normalize_text(_clean_album_title(title)), base_page),
    )
    return max(exact, 0.98 * _similarity(_normalize_page_title(title), base_page))


def _pick_album(pages: list[_Page], title: str, artist: str) -> _Page | None:
    """Return the best verified album page among ``pages`` (earlier wins ties), else None."""
    best: _Page | None = None
    best_score = 0.0
    for page in pages:
        if not (_is_album_page(page) and _credits_artist(page, artist)):
            continue
        score = _album_score(page, title)
        if score >= _TITLE_THRESHOLD and score > best_score:
            best, best_score = page, score
    return best


def _pick_artist(pages: list[_Page], artist: str) -> _Page | None:
    """Return the first verified musical-act page among ``pages`` named ``artist``."""
    expected = _normalize_text(artist)
    for page in pages:
        if _is_act_page(page) and _names_match(_normalize_page_title(page.title), expected):
            return page
    return None


def _find_album_page(title: str, artist: str) -> _Page | None:
    names = _artist_names(artist)
    lead = names[1] if len(names) > 1 else names[0]
    guesses = []
    # Raw title first so a distinct release ("Red (Taylor's Version)") beats the original.
    for t in dict.fromkeys([title.strip(), _clean_album_title(title)]):
        guesses += [
            t,
            f"{t} ({names[0]} album)",
            f"{t} ({lead} album)",
            f"{t} ({names[0]} EP)",
            f"{t} (album)",
            f"{t} (EP)",
        ]
    page = _pick_album(_lookup_titles(guesses), title, artist)
    if page:
        return page
    return _pick_album(_search(f"{_clean_album_title(title)} {artist} album"), title, artist)


def _find_artist_page(artist: str) -> _Page | None:
    # The page for a multi-artist credit is the lead artist's.
    names = _artist_names(artist)
    for name in names[:2]:
        # Titles are case-sensitive past the first letter: "MAVI" is at "Mavi (rapper)".
        spellings = dict.fromkeys([name, name.title()])
        guesses = [
            f"{s} ({q})" if q else s
            for s in spellings
            for q in ("", "band", "musician", "rapper", "singer")
        ]
        page = _pick_artist(_lookup_titles(guesses), name)
        if page:
            return page
    name = names[1] if len(names) > 1 else names[0]
    return _pick_artist(_search(f"{name} musician band"), name)


def find_wikipedia_url(title: str, artist: str) -> str | None:
    """Resolve a Wikipedia URL for an album, preferring its page over the artist's.

    1. Find a page verified to be an album credited to ``artist`` whose title matches.
    2. Fall back to a page verified to be about the musical act.
    3. Return None if neither is found.

    A failed request aborts the whole lookup rather than falling through to the artist
    page, so an outage or rate limit never stores a worse link. Silently returns None on
    any failure to stay safe as a background task.
    """
    try:
        page = _find_album_page(title, artist) or _find_artist_page(artist)
        return _page_url(page.title) if page else None
    except Exception:
        log.warning("Wikipedia lookup failed for %r by %r", title, artist)
        return None
