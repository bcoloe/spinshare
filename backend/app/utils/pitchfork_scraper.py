"""Pitchfork Best New Albums scraper.

Pure data-extraction module — no DB, no FastAPI, no Spotify dependencies.
Returns structured album data from pitchfork.com/reviews/best/albums/.

Selectors are stored as module-level constants so they can be updated in one
place if Pitchfork's markup changes.
"""

import json
import logging
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://pitchfork.com/reviews/best/albums/"
REQUEST_HEADERS = {"User-Agent": "spinshare-bot/1.0 (educational use)"}
REQUEST_TIMEOUT = 15

# Selectors — update here if Pitchfork's markup changes.
RIVER_TESTID = "SummaryRiverWrapper"
CARD_ATTR = "data-item"
HED_TESTID = "SummaryItemHed"


@dataclass
class PitchforkAlbum:
    artist: str
    title: str
    review_url: str


def scrape_page(page: int, *, delay: float = 1.5) -> list[PitchforkAlbum]:
    """Scrape one page of Pitchfork Best New Albums.

    Returns an empty list on HTTP errors or parse failures; never raises.
    The caller controls pagination and stop conditions.
    """
    time.sleep(delay)
    url = f"{BASE_URL}?page={page}"
    try:
        resp = httpx.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True)
    except Exception as exc:
        log.warning("HTTP error fetching %s: %s", url, exc)
        return []

    if not resp.is_success:
        log.warning("Non-2xx response for %s: %d", url, resp.status_code)
        return []

    albums = _parse_albums(resp.text)
    log.debug("Page %d: parsed %d albums", page, len(albums))
    return albums


def _parse_albums(html: str) -> list[PitchforkAlbum]:
    """Extract PitchforkAlbum records from a best-new-albums page HTML string."""
    soup = BeautifulSoup(html, "html.parser")
    river = soup.find(attrs={"data-testid": RIVER_TESTID})
    if not river:
        log.warning("River container (%r) not found — page structure may have changed", RIVER_TESTID)
        return []

    albums = []
    for card in river.find_all(attrs={CARD_ATTR: True}):
        album = _parse_card(card)
        if album:
            albums.append(album)
    return albums


def _parse_card(card) -> PitchforkAlbum | None:
    """Extract a single album from a card element. Returns None on parse failure."""
    try:
        data = json.loads(card[CARD_ATTR])
        title_html = data.get("dangerousHed", "")
        title = BeautifulSoup(title_html, "html.parser").get_text(strip=True)
        review_url = data.get("hotelLink", "")

        # Artist is in the sub-hed SummaryItemHed (a <div>, not the <h3> title)
        heds = card.find_all(attrs={"data-testid": HED_TESTID})
        artist = next((h.get_text(strip=True) for h in heds if h.name == "div"), "")

        if not title or not artist:
            log.debug("Skipping card — missing title or artist: title=%r artist=%r", title, artist)
            return None

        return PitchforkAlbum(artist=artist, title=title, review_url=review_url)
    except Exception as exc:
        log.warning("Failed to parse card: %s", exc)
        return None
