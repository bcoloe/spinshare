"""Backfill genres for albums that have no genre associations.

Genres are sourced from Apple Music only (Spotify deprecated album genres).

Run from the backend/ directory:
    python scripts/backfill_genres.py

Albums that already have at least one genre are skipped. Safe to re-run after
partial failures — the backfill is idempotent.

On completion (or SIGINT/SIGTERM), unresolved albums are written to a JSON file
in /tmp/ for manual triage.
"""

import json
import signal
import sys
import time
from datetime import datetime

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.album import Album  # noqa: E402
from app.models.genre import album_genres  # noqa: E402
from app.services.album_service import AlbumService  # noqa: E402


BATCH_SIZE = 10
SLEEP_SEC = 0.3

_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_triage_path = f"/tmp/genres_backfill_unresolved_{_timestamp}.json"

_db = None
_unresolved: list[dict] = []


def _write_triage() -> None:
    if not _unresolved:
        print("No unresolved albums — triage file not written.")
        return
    with open(_triage_path, "w") as f:
        json.dump(_unresolved, f, indent=2, default=str)
    print(f"Triage file: {_triage_path} ({len(_unresolved)} entries)")


def _handle_signal(sig: int, _: object) -> None:
    print(f"\nInterrupted (signal {sig}), committing pending changes...")
    if _db:
        try:
            _db.commit()
        except Exception:
            pass
    _write_triage()
    sys.exit(1)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def main() -> None:
    global _db

    _db = SessionLocal()
    try:
        # Albums with no rows in the album_genres join table
        albums_with_genres_subq = (
            _db.query(album_genres.c.album_id).distinct().scalar_subquery()
        )
        albums = (
            _db.query(Album)
            .filter(Album.id.notin_(albums_with_genres_subq))
            .order_by(Album.id)
            .all()
        )
        total = len(albums)
        print(f"Backfilling genres for {total} album(s) with no genre associations...")
        resolved = 0

        svc = AlbumService(_db)

        for i, album in enumerate(albums, start=1):
            reason: str | None = None
            try:
                svc.backfill_genres(album.id, album.title, album.artist)
                _db.refresh(album)
                if album.genres:
                    resolved += 1
                else:
                    reason = "no_match"
            except Exception as e:
                reason = str(e) or type(e).__name__
                print(f"  Error — {album.artist} / {album.title}: {reason}", file=sys.stderr)

            if reason is not None:
                _unresolved.append({
                    "id": album.id,
                    "title": album.title,
                    "artist": album.artist,
                    "release_date": album.release_date,
                    "reason": reason,
                })

            if i % BATCH_SIZE == 0 or i == total:
                pct = i / total * 100
                print(
                    f"  [{i}/{total} {pct:.0f}%]"
                    f"  resolved={resolved}"
                    f"  unresolved={len(_unresolved)}"
                )

            time.sleep(SLEEP_SEC)

    finally:
        _db.close()

    print(f"\nDone: {resolved} resolved, {len(_unresolved)} unresolved")
    _write_triage()


if __name__ == "__main__":
    main()
