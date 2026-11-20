"""Re-run Wikipedia resolution for albums that already have a stored link.

The self-healing backfill only fills *missing* links, so links stored by an older, less
accurate resolver are never revisited. This script re-resolves them with the current
resolver and reports (or applies) the ones that change.

Albums whose Wikipedia link was corrected by an admin via a resolved link report are
skipped, so manual fixes stay authoritative. A new resolution of ``None`` never clears an
existing link.

Run from the backend/ directory:
    .venv/bin/python scripts/wikipedia_reresolve.py              # dry run, all albums
    .venv/bin/python scripts/wikipedia_reresolve.py --limit 100  # dry run, first 100
    .venv/bin/python scripts/wikipedia_reresolve.py --apply      # write changes

Writes bypass the API's response cache; clear it afterwards (see backend/CLAUDE.md).
"""

import argparse
import sys
import time
from datetime import datetime, UTC
from urllib.parse import unquote

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.album import Album  # noqa: E402
from app.models.link_report import LinkReport  # noqa: E402
from app.schemas.link_report import ReportableLink  # noqa: E402
from app.utils import wikipedia_client  # noqa: E402


def _short(url: str | None) -> str:
    return unquote(url.rsplit("/", 1)[-1]) if url else "(none)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-resolve stored Wikipedia album links")
    parser.add_argument("--apply", action="store_true", help="Write changed links to the DB")
    parser.add_argument("--limit", type=int, help="Only check the first N albums (by id)")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to pause between albums, to be polite to the MediaWiki API",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin_fixed = {
            album_id
            for (album_id,) in db.query(LinkReport.album_id).filter(
                LinkReport.link_field == ReportableLink.Wikipedia.value,
                LinkReport.status == "resolved",
            )
        }
        query = db.query(Album).filter(Album.wikipedia_url.isnot(None)).order_by(Album.id)
        if args.limit:
            query = query.limit(args.limit)
        albums = query.all()

        changed = skipped = 0
        for album in albums:
            if album.id in admin_fixed:
                skipped += 1
                continue
            new_url = wikipedia_client.find_wikipedia_url(album.title, album.artist)
            time.sleep(args.delay)
            if new_url is None or new_url == album.wikipedia_url:
                continue
            changed += 1
            print(
                f"[{album.id}] {album.title!r} by {album.artist!r}\n"
                f"    {_short(album.wikipedia_url)}  ->  {_short(new_url)}"
            )
            if args.apply:
                album.wikipedia_url = new_url
                album.wikipedia_checked_at = datetime.now(UTC)

        if args.apply:
            db.commit()
        verb = "Updated" if args.apply else "Would update"
        print(
            f"\nChecked {len(albums) - skipped} albums ({skipped} admin-corrected skipped). "
            f"{verb} {changed}."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
