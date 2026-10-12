"""Run the daily album selection by hand.

The API process schedules this itself (``app/scheduler.py``), drawing each group's
albums once its local clock reaches ``DAILY_SELECTION_HOUR``. This script is for
manual and operational runs: re-drawing after an outage, targeting one group, or
forcing a different count. Selection is idempotent per group-local day, so running
it alongside the scheduler is harmless.

Usage (from backend/):
    .venv/bin/python scripts/daily_album_selector.py            # every group, configured count
    .venv/bin/python scripts/daily_album_selector.py --n 3      # 3 albums per group
    .venv/bin/python scripts/daily_album_selector.py --group 42 # single group only

Exits non-zero if any group was rejected or failed, so a partial run never looks clean.
"""

import argparse
import logging
import sys

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models import Group
from app.services.scheduled_jobs import run_daily_selection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(n: int | None, group_id: int | None, db: Session) -> None:
    if group_id is not None and db.get(Group, group_id) is None:
        log.error("Group %d not found", group_id)
        sys.exit(1)

    report = run_daily_selection(db, None if group_id is None else [group_id], n=n)

    skipped = len(report.rejected) + len(report.failed)
    if skipped:
        log.error("Daily selection finished with %d of %d group(s) skipped", skipped, report.attempted)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily album selector")
    parser.add_argument("--n", type=int, default=None, help="Albums to select per group (overrides per-group setting)")
    parser.add_argument("--group", type=int, default=None, help="Limit to a specific group ID")
    args = parser.parse_args()

    engine = create_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    db = sessionmaker(bind=engine)()
    try:
        run(n=args.n, group_id=args.group, db=db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
