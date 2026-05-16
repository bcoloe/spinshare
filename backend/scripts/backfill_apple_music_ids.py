"""One-time backfill: resolve apple_music_album_id for albums that don't have one.

Run from the backend/ directory:
    python scripts/backfill_apple_music_ids.py

Already-resolved albums are skipped. Safe to re-run after partial failures.
Requires APPLE_MUSIC_TEAM_ID, APPLE_MUSIC_KEY_ID, and APPLE_MUSIC_PRIVATE_KEY in .env.

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
from app.utils.apple_music_client import find_apple_music_album  # noqa: E402


BATCH_SIZE = 10
SLEEP_SEC = 0.3

_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_triage_path = f"/tmp/apple_music_backfill_unresolved_{_timestamp}.json"

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
        albums = _db.query(Album).filter(Album.apple_music_album_id.is_(None)).all()
        total = len(albums)
        print(f"Backfilling {total} album(s) without apple_music_album_id...")
        resolved = 0

        for i, album in enumerate(albums, start=1):
            reason: str | None = None
            try:
                result = find_apple_music_album(album.title, album.artist)
                if result:
                    album.apple_music_album_id = result.id
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
                _db.commit()
                pct = i / total * 100
                print(
                    f"  [{i}/{total} {pct:.0f}%]"
                    f"  resolved={resolved}"
                    f"  unresolved={len(_unresolved)}"
                    f"  (committed)"
                )

            time.sleep(SLEEP_SEC)

    finally:
        _db.close()

    print(f"\nDone: {resolved} resolved, {len(_unresolved)} unresolved")
    _write_triage()


if __name__ == "__main__":
    main()
