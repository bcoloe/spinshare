"""Pitchfork Best New Albums bot.

Scrapes pitchfork.com/reviews/best/albums/, matches each album on Spotify,
and nominates it to the bot-owned group. Already-nominated albums are
silently skipped (duplicate constraint).

Run setup_bot.py once before the first execution.

Usage:
    python scripts/pitchfork_bot.py
    python scripts/pitchfork_bot.py --max-pages 5    # limit pages (useful for testing)
    python scripts/pitchfork_bot.py --dry-run         # scrape + match, no DB writes

Cron example (weekly, Mondays 3am UTC):
    0 3 * * 1 cd /path/to/spinshare/backend && .venv/bin/python scripts/pitchfork_bot.py
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import BotSource, Group, GroupAlbum, GroupSettings, User  # noqa: F401
from app.schemas.album import AlbumCreate
from app.services.album_service import AlbumService
from app.utils import pitchfork_scraper
from app.utils.pitchfork_scraper import PitchforkAlbum
from app.utils.spotify_client import search_albums

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BOT_SOURCE_NAME = "pitchfork_best_new"
MAX_CONSECUTIVE_SKIPPED_PAGES = 3


def run(db, *, max_pages: int, dry_run: bool) -> None:
    bot_source = db.query(BotSource).filter(BotSource.name == BOT_SOURCE_NAME).first()
    if not bot_source:
        log.error("BotSource %r not found. Run scripts/setup_bot.py first.", BOT_SOURCE_NAME)
        sys.exit(1)

    bot_user = db.query(User).filter(User.id == bot_source.bot_user_id).first()
    group_id = bot_source.bot_group_id
    album_svc = AlbumService(db)

    counts = {"nominated": 0, "skipped": 0, "no_match": 0, "error": 0}
    consecutive_all_skipped = 0

    for page in range(1, max_pages + 1):
        log.info("Scraping page %d...", page)
        albums = pitchfork_scraper.scrape_page(page)
        if not albums:
            log.warning("Page %d returned no albums — stopping", page)
            break

        skipped_this_page = 0
        for pitchfork_album in albums:
            result = _process_album(pitchfork_album, bot_user, group_id, album_svc, dry_run=dry_run)
            counts[result] = counts.get(result, 0) + 1
            if result in ("skipped", "no_match"):
                skipped_this_page += 1

        if skipped_this_page == len(albums):
            consecutive_all_skipped += 1
            log.debug("Page %d fully skipped (%d/%d)", page, consecutive_all_skipped, MAX_CONSECUTIVE_SKIPPED_PAGES)
        else:
            consecutive_all_skipped = 0

        if not dry_run:
            bot_source.processing_state = {"last_processed_page": page}
            bot_source.last_run_at = datetime.now(timezone.utc)
            db.commit()

        if consecutive_all_skipped >= MAX_CONSECUTIVE_SKIPPED_PAGES:
            log.info("Reached already-processed content after page %d — stopping early", page)
            break

    log.info(
        "Done. Nominated: %d | Skipped (existing): %d | No Spotify match: %d | Errors: %d",
        counts["nominated"],
        counts["skipped"],
        counts["no_match"],
        counts["error"],
    )


def _process_album(
    pitchfork_album: PitchforkAlbum,
    bot_user: User,
    group_id: int,
    album_svc: AlbumService,
    *,
    dry_run: bool,
) -> str:
    try:
        results = search_albums(artist=pitchfork_album.artist, album=pitchfork_album.title, limit=1)
    except HTTPException as exc:
        log.warning(
            "Spotify unavailable for %r by %r: %s",
            pitchfork_album.title,
            pitchfork_album.artist,
            exc.detail,
        )
        return "error"

    if not results:
        log.info("No Spotify match: %r by %r", pitchfork_album.title, pitchfork_album.artist)
        return "no_match"

    spotify = results[0]

    if dry_run:
        log.info(
            "[dry-run] Would nominate: %r by %r (%s)",
            spotify.title,
            spotify.artist,
            spotify.spotify_album_id,
        )
        return "skipped"

    album = album_svc.get_or_create_album(
        AlbumCreate(
            spotify_album_id=spotify.spotify_album_id,
            title=spotify.title,
            artist=spotify.artist,
            release_date=spotify.release_date,
            cover_url=spotify.cover_url,
            genres=spotify.genres,
        )
    )

    try:
        album_svc.nominate_album(group_id=group_id, album_id=album.id, user=bot_user)
        log.info("Nominated: %r by %r", album.title, album.artist)
        return "nominated"
    except HTTPException as exc:
        if exc.status_code == 409:
            log.debug("Already nominated: %r by %r", album.title, album.artist)
            return "skipped"
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Pitchfork Best New Albums bot")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to scrape per run (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and match on Spotify but make no DB writes",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        run(db, max_pages=args.max_pages, dry_run=args.dry_run)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
