"""One-time backfill: resolve apple_music_url for albums that don't have one.

Run from the backend/ directory:
    python scripts/backfill_apple_music_urls.py

Already-resolved albums are skipped. Safe to re-run after partial failures.
"""

import sys
import time

sys.path.insert(0, ".")

from app.database import SessionLocal
from app.models.album import Album
from app.utils.odesli_client import get_apple_music_url


BATCH_SIZE = 10  # commit and report progress every N albums


def main() -> None:
    db = SessionLocal()
    try:
        albums = db.query(Album).filter(Album.apple_music_url.is_(None)).all()
        total = len(albums)
        print(f"Backfilling {total} album(s) without apple_music_url...")
        resolved = 0
        unresolved = 0
        for i, album in enumerate(albums, start=1):
            try:
                url = get_apple_music_url(album.spotify_album_id)
                album.apple_music_url = url
                if url:
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

            time.sleep(6.5)  # Odesli free tier: ~10 requests/minute

    finally:
        db.close()
    print(f"Done: {resolved} resolved, {unresolved} unresolved (re-run to retry failed)")


if __name__ == "__main__":
    main()
