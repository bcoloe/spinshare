"""Daily album selector cron job.

Selects N random unselected albums per group and marks them as today's spins
by setting selected_date = now(UTC). Each group's "today" is determined by its
configured timezone (default: America/New_York), so the cron should run at the
earliest midnight across all group timezones (e.g. UTC midnight covers all groups
west of UTC; run hourly for full global coverage).

Usage:
    python scripts/daily_album_selector.py            # 1 album per group (default)
    python scripts/daily_album_selector.py --n 3      # 3 albums per group
    python scripts/daily_album_selector.py --group 42 # single group only

Cron example (hourly, idempotent — each group selects once per its local day):
    0 * * * * cd /path/to/spinshare/backend && .venv/bin/python scripts/daily_album_selector.py
"""

import argparse
import logging
import sys

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.models import Group, GroupAlbum, GroupSettings  # noqa: F401 — ensure all models are registered
from app.services.group_album_service import GroupAlbumService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(n: int | None, group_id: int | None, db: Session) -> None:
    svc = GroupAlbumService(db)

    groups = db.query(Group).all() if group_id is None else [_get_group(db, group_id)]

    for group in groups:
        # --n flag overrides per-group setting; otherwise use the group's configured count.
        group_n = n if n is not None else (
            group.settings.daily_album_count if group.settings else 1
        )
        try:
            selected = svc.select_daily_albums(group.id, n=group_n)
            titles = [ga.albums.title for ga in selected]
            log.info("Group %d (%s): today's albums: %s", group.id, group.name, titles)
        except Exception as exc:
            log.warning("Group %d (%s): skipped — %s", group.id, group.name, exc)


def _get_group(db: Session, group_id: int) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        log.error("Group %d not found", group_id)
        sys.exit(1)
    return group


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily album selector")
    parser.add_argument("--n", type=int, default=None, help="Albums to select per group (overrides per-group setting)")
    parser.add_argument("--group", type=int, default=None, help="Limit to a specific group ID")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        run(n=args.n, group_id=args.group, db=db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
