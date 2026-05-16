"""Thin client for the Apple Music API using ES256 developer tokens."""

import difflib
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field

import httpx
import jwt
from app.config import get_settings
from fastapi import HTTPException, status

log = logging.getLogger(__name__)

_dev_token: str | None = None
_dev_token_expires_at: float = 0.0

_TOKEN_TTL_SECONDS = 180 * 24 * 3600  # 180 days (Apple's maximum)
_TOKEN_REFRESH_MARGIN = 24 * 3600     # regenerate 1 day before expiry

_TITLE_THRESHOLD = 0.82
_ARTIST_THRESHOLD = 0.72

# Strips any trailing parenthetical/bracketed group from a title (iteratively applied).
_TRAILING_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]+[\)\]]\s*$")

# Strips trailing dash-separated release qualifiers: "Song - EP", "Song - Single", etc.
_TRAILING_DASH_QUALIFIER_RE = re.compile(
    r"\s*-\s*(?:EP|Single|Live|Acoustic|Demo|Instrumental|Soundtrack|OST|Radio\s+Edit|Extended)\s*$",
    re.IGNORECASE,
)

# Splits multi-artist strings on common separators: comma, &, feat., ft., with, and.
_ARTIST_SPLIT_RE = re.compile(r"\s*[,&]\s*|\s+(?:feat\.?|ft\.?|with|and)\s+", re.IGNORECASE)

# Censors a word to Apple Music's pattern: first letter + * fill + last letter.
# Used in search terms so Apple's backend can match censored catalog entries.
_PROFANITY_RE = re.compile(
    r"\b(fuck(?:ing|ed|er|s)?|shit(?:ty)?|ass(?:hole)?|bitch(?:es)?|cunt|dick|cock|piss(?:ed)?|bastard)\b",
    re.IGNORECASE,
)


@dataclass
class AppleMusicAlbumResult:
    id: str
    title: str
    artist: str
    release_date: str | None
    cover_url: str | None
    genres: list[str] = field(default_factory=list)


# ── Text normalization ──────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    """Lowercase, strip diacritics, remove censorship asterisks and punctuation like '!'."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_combining = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    # Remove * (Apple's censorship fill) and ! (common in album titles like "Norman Fucking Rockwell!")
    without_combining = re.sub(r"[*!]", "", without_combining)
    return re.sub(r"\s+", " ", without_combining.lower()).strip()


def _normalized_title(title: str) -> str:
    """Strip trailing dash qualifiers and parenthetical groups, then normalize text.

    Applied iteratively to handle stacked suffixes like "Album - EP (Remastered)".
    """
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
    return _normalize_text(title)


def _censor_for_search(text: str) -> str:
    """Replace known profanity with Apple's censorship pattern (first + last letter, * fill).

    Apple Music censors profanity in their catalog and likely in search as well,
    using the format: first_letter + '*' * (len-2) + last_letter.
    """
    def _censor_word(m: re.Match) -> str:
        w = m.group(0)
        return w[0] + "*" * (len(w) - 2) + w[-1] if len(w) > 2 else w
    return _PROFANITY_RE.sub(_censor_word, text)


def _split_artists(artist_str: str) -> list[str]:
    """Split a multi-artist string into individual names; returns [artist_str] on no split."""
    parts = _ARTIST_SPLIT_RE.split(artist_str)
    return [p.strip() for p in parts if p.strip()] or [artist_str]


# ── Fuzzy matching ──────────────────────────────────────────────────────────────

def _artist_similarity(query_artist: str, candidate_artist: str) -> float:
    """Best SequenceMatcher ratio between any query-artist part and any candidate-artist part.

    Compares each query part against the full candidate string and each candidate
    part individually, so "Vijay Iyer, Wadada Leo Smith" matches "Vijay Iyer".
    """
    q_parts = [_normalize_text(p) for p in _split_artists(query_artist)]
    c_parts = [_normalize_text(p) for p in _split_artists(candidate_artist)]
    c_full = _normalize_text(candidate_artist)
    best = 0.0
    for q in q_parts:
        for target in [c_full, *c_parts]:
            best = max(best, difflib.SequenceMatcher(None, q, target).ratio())
    return best


def _best_match(albums: list[dict], title: str, artist: str) -> AppleMusicAlbumResult | None:
    """Return the highest-scoring candidate that clears both similarity thresholds, or None."""
    q_title = _normalized_title(title)
    best_album: dict | None = None
    best_score = 0.0

    for album in albums:
        attrs = album.get("attributes", {})
        t_sim = difflib.SequenceMatcher(
            None, q_title, _normalized_title(attrs.get("name", ""))
        ).ratio()
        if t_sim < _TITLE_THRESHOLD:
            continue
        a_sim = _artist_similarity(artist, attrs.get("artistName", ""))
        if a_sim < _ARTIST_THRESHOLD:
            continue
        if (t_sim + a_sim) > best_score:
            best_score = t_sim + a_sim
            best_album = album

    if best_album is None:
        return None

    attrs = best_album["attributes"]
    artwork = attrs.get("artwork", {})
    cover_url = None
    if artwork.get("url"):
        cover_url = artwork["url"].replace("{w}", "300").replace("{h}", "300")
    return AppleMusicAlbumResult(
        id=best_album["id"],
        title=attrs.get("name", ""),
        artist=attrs.get("artistName", ""),
        release_date=attrs.get("releaseDate"),
        cover_url=cover_url,
        genres=attrs.get("genreNames", []),
    )


# ── Token management ────────────────────────────────────────────────────────────

def generate_developer_token() -> str:
    """Return a cached ES256 JWT for MusicKit JS and the Apple Music API.

    The token is valid for 180 days and regenerated 1 day before expiry.

    Raises:
        HTTPException 503: If Apple Music credentials are not configured.
    """
    global _dev_token, _dev_token_expires_at

    if _dev_token and time.time() < _dev_token_expires_at - _TOKEN_REFRESH_MARGIN:
        return _dev_token

    settings = get_settings()
    if not all([settings.APPLE_MUSIC_TEAM_ID, settings.APPLE_MUSIC_KEY_ID, settings.APPLE_MUSIC_PRIVATE_KEY]):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apple Music integration not configured",
        )

    now = int(time.time())
    expiry = now + _TOKEN_TTL_SECONDS

    token = jwt.encode(
        {"iss": settings.APPLE_MUSIC_TEAM_ID, "iat": now, "exp": expiry},
        settings.APPLE_MUSIC_PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": settings.APPLE_MUSIC_KEY_ID},
    )

    _dev_token = token
    _dev_token_expires_at = float(expiry)
    return _dev_token


# ── Search ──────────────────────────────────────────────────────────────────────

def find_apple_music_album(
    title: str, artist: str, storefront: str = "us"
) -> AppleMusicAlbumResult | None:
    """Search the Apple Music catalog for the best-matching album.

    Three search stages, each tried only if the previous yields no qualifying candidate:
      1. Normalized title + primary artist (precise)
      2. Normalized title only (broader recall)
      3. Censored title + primary artist — handles Apple's profanity filter, which replaces
         the middle letters of known words with '*' (e.g. "Fucking" → "F*****g")

    Within each stage candidates are ranked by fuzzy title and artist similarity;
    both must clear their respective thresholds to guard against false positives.

    Silently returns None on any failure to avoid breaking background tasks.
    """
    try:
        token = generate_developer_token()
    except HTTPException:
        return None

    first_artist = _split_artists(artist)[0] if artist.strip() else ""
    clean_title = _normalized_title(title)
    censored_title = _censor_for_search(clean_title)

    search_terms = [
        f"{clean_title} {first_artist}".strip(),
        clean_title,
    ]
    if censored_title != clean_title:
        search_terms.append(f"{censored_title} {first_artist}".strip())

    for search_term in search_terms:
        try:
            resp = httpx.get(
                f"https://api.music.apple.com/v1/catalog/{storefront}/search",
                params={"types": "albums", "term": search_term, "limit": 25},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
        except Exception:
            log.warning("Apple Music search request failed for %r by %r", title, artist)
            return None

        if not resp.is_success:
            log.warning("Apple Music search returned %d for %r by %r", resp.status_code, title, artist)
            return None

        albums = resp.json().get("results", {}).get("albums", {}).get("data", [])
        result = _best_match(albums, title, artist)
        if result:
            return result

    return None
