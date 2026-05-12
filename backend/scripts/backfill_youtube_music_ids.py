"""One-time backfill: resolve youtube_music_id for albums that don't have one.

Run from the backend/ directory:
    python scripts/backfill_youtube_music_ids.py

Already-resolved albums are skipped. Safe to re-run after partial failures.
"""

import sys
import time

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.album import Album
from app.utils.ytmusic_client import search_album_browse_id


BATCH_SIZE = 10  # commit and report progress every N albums


def main() -> None:
    db = SessionLocal()
    try:
        albums = db.query(Album).filter(Album.youtube_music_id.is_(None)).all()
        total = len(albums)
        print(f"Backfilling {total} album(s) without youtube_music_id...")
        resolved = 0
        unresolved = 0
        for i, album in enumerate(albums, start=1):
            try:
                browse_id = search_album_browse_id(album.title, album.artist)
                album.youtube_music_id = browse_id
                if browse_id:
                    resolved += 1
                else:
                    unresolved += 1
            except Exception as e:
                print(f"  Error — {album.artist} / {album.title}: {e}", file=sys.stderr)
                unresolved += 1

            if i % BATCH_SIZE == 0 or i == total:
                db.commit()
                pct = i / total * 100
                print(f"  [{i}/{total} {pct:.0f}%]  resolved={resolved}  unresolved={unresolved}  (committed)")

            time.sleep(0.5)  # avoid hitting YouTube Music rate limits

    finally:
        db.close()
    print(f"Done: {resolved} resolved, {unresolved} unresolved (re-run to retry failed)")


if __name__ == "__main__":
    main()
