"""One-time bulk backfill of Wikipedia links for albums that predate the feature.

Resolves and stores a Wikipedia URL for every album that has never been checked. Going
forward, albums self-heal lazily on nomination, resolve, daily draw, and detail view; this
script just clears the existing backlog so links appear immediately.

Idempotent: only touches albums with wikipedia_checked_at IS NULL, so it is safe to re-run
(it will pick up any stragglers). Runs sequentially with a small delay to be polite to the
MediaWiki API.

Run from the backend/ directory:
    .venv/bin/python scripts/backfill_wikipedia.py            # backfill all unchecked albums
    .venv/bin/python scripts/backfill_wikipedia.py --limit 20 # cap the number processed
    .venv/bin/python scripts/backfill_wikipedia.py --dry-run  # report candidates, write nothing
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models import Album  # noqa: E402
from app.services.album_service import AlbumService  # noqa: E402
from app.utils import wikipedia_client  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk backfill album Wikipedia links")
    parser.add_argument("--limit", type=int, default=None, help="Max albums to process")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Look up and print results without writing to the database",
    )
    parser.add_argument(
        "--delay", type=float, default=0.3,
        help="Seconds to sleep between API calls (default 0.3)",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = (
            db.query(Album)
            .filter(Album.wikipedia_checked_at.is_(None), Album.wikipedia_url.is_(None))
            .order_by(Album.id)
        )
        if args.limit is not None:
            query = query.limit(args.limit)
        albums = query.all()

        total = len(albums)
        print(f"{total} album(s) to check{' (dry run)' if args.dry_run else ''}\n")

        resolved = 0
        svc = AlbumService(db)
        for i, album in enumerate(albums, start=1):
            label = f"[{i}/{total}] {album.title!r} by {album.artist!r}"
            if args.dry_run:
                url = wikipedia_client.find_wikipedia_url(album.title, album.artist)
            else:
                svc.backfill_wikipedia_url(album.id, album.title, album.artist)
                db.refresh(album)
                url = album.wikipedia_url
            if url:
                resolved += 1
                print(f"{label}\n    -> {url}")
            else:
                print(f"{label}\n    -> (no page found)")
            if args.delay:
                time.sleep(args.delay)

        print(f"\nDone. Resolved {resolved}/{total}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
