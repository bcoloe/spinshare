"""Pitchfork Best New Albums bot.

Scrapes pitchfork.com/reviews/best/albums/, matches each album on Spotify,
and nominates it to the bot-owned group. Already-nominated albums are
silently skipped (duplicate constraint).

Run pitchfork_setup.py once before the first execution.

Usage:
    python bots/pitchfork_bot.py
    python bots/pitchfork_bot.py --start-page 10             # resume from page 10
    python bots/pitchfork_bot.py --start-page 10 --max-pages 5   # pages 10-14
    python bots/pitchfork_bot.py --max-pages 5    # limit pages (useful for testing)
    python bots/pitchfork_bot.py --dry-run         # scrape + match, no DB writes
    python bots/pitchfork_bot.py --force           # ignore cursor and 409 stop signals

Cron example (weekly, Mondays 3am UTC):
    0 3 * * 1 cd /path/to/spinshare/backend && .venv/bin/python bots/pitchfork_bot.py
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timezone

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


def run(db, *, start_page: int, max_pages: int, dry_run: bool, force: bool, delay: float) -> None:
    bot_source = db.query(BotSource).filter(BotSource.name == BOT_SOURCE_NAME).first()
    if not bot_source:
        log.error("BotSource %r not found. Run bots/pitchfork_setup.py first.", BOT_SOURCE_NAME)
        sys.exit(1)

    bot_user = db.query(User).filter(User.id == bot_source.bot_user_id).first()
    group_id = bot_source.bot_group_id
    album_svc = AlbumService(db)

    # URL of the first (newest) album seen last run — stop here next time.
    last_seen_url = (bot_source.processing_state or {}).get("last_seen_review_url")
    # URL of the first album we see this run; becomes the cursor for the next run.
    first_url_this_run = None
    done = False

    counts = {"nominated": 0, "skipped": 0, "no_match": 0, "error": 0, "dry_run": 0}

    for page in range(start_page, start_page + max_pages):
        log.info("Scraping page %d...", page)
        albums = pitchfork_scraper.scrape_page(page)
        if not albums:
            log.warning("Page %d returned no albums — stopping", page)
            break

        for pitchfork_album in albums:
            # Cursor check: stop when we reach the album we started with last run.
            # Everything from here onwards was already processed (newest-first ordering).
            if not force and last_seen_url and pitchfork_album.review_url == last_seen_url:
                log.info("Reached last-processed album (%s) — stopping", pitchfork_album.review_url)
                done = True
                break

            # Capture the newest album URL to use as the cursor for the next run.
            if first_url_this_run is None and pitchfork_album.review_url:
                first_url_this_run = pitchfork_album.review_url

            result = _process_album(pitchfork_album, bot_user, group_id, album_svc, dry_run=dry_run)
            if delay > 0:
                time.sleep(delay)
            counts[result] += 1

            # Newest-first: a 409 means we've crossed into already-processed territory.
            if not force and result == "skipped":
                log.info(
                    "Album %r already nominated — stopping (use --force to continue past this point)",
                    pitchfork_album.title,
                )
                done = True
                break

        if done:
            break

    if not dry_run and first_url_this_run:
        bot_source.processing_state = {"last_seen_review_url": first_url_this_run}
        bot_source.last_run_at = datetime.now(timezone.utc)
        db.commit()

    if dry_run:
        log.info(
            "Dry run complete. Would nominate: %d | No Spotify match: %d | Errors: %d",
            counts["dry_run"],
            counts["no_match"],
            counts["error"],
        )
    else:
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
        return "dry_run"

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
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to sleep between Spotify API calls (default: 1.0)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="Page number to start scraping from (default: 1)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum number of pages to scrape per run (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and match on Spotify but make no DB writes",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cursor and 409 stop signals; scrape all pages up to --max-pages",
    )
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        run(db, start_page=args.start_page, max_pages=args.max_pages, dry_run=args.dry_run, force=args.force, delay=args.delay)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
