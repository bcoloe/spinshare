"""Run the weekly recap generator by hand.

The API process schedules this itself (``app/scheduler.py``), generating each
group's recap once its local Monday reaches ``WEEKLY_RECAP_HOUR``. This script is
for manual and operational runs: backfilling a past week or regenerating one.
Without ``--force`` it is idempotent (one recap per group per week, enforced by a
unique constraint). Exits non-zero if any group was rejected or failed.

Usage (from backend/):
    .venv/bin/python scripts/weekly_recap_generator.py                       # all due groups
    .venv/bin/python scripts/weekly_recap_generator.py --group 42            # single group
    .venv/bin/python scripts/weekly_recap_generator.py --group 42 \\
        --week-start 2026-07-27                                              # backfill a past week
    .venv/bin/python scripts/weekly_recap_generator.py --group 42 \\
        --week-start 2026-07-27 --force                                      # regenerate (dev/test)
"""

import argparse
import logging
import sys
from datetime import date

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models import Group
from app.services.scheduled_jobs import run_weekly_recaps

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(group_id: int | None, week_start: date | None, force: bool, db: Session) -> None:
    if group_id is not None and db.get(Group, group_id) is None:
        log.error("Group %d not found", group_id)
        sys.exit(1)
    report = run_weekly_recaps(db, None if group_id is None else [group_id], week_start=week_start, force=force)

    skipped = len(report.rejected) + len(report.failed)
    if skipped:
        log.error("Weekly recap finished with %d of %d group(s) skipped", skipped, report.attempted)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly recap generator")
    parser.add_argument("--group", type=int, default=None, help="Limit to a specific group ID")
    parser.add_argument(
        "--week-start",
        type=date.fromisoformat,
        default=None,
        help="Generate a specific week (YYYY-MM-DD Monday) instead of the most recently completed one",
    )
    parser.add_argument("--force", action="store_true", help="Regenerate even if a recap already exists (dev/test)")
    args = parser.parse_args()

    engine = create_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    db = sessionmaker(bind=engine)()
    try:
        run(group_id=args.group, week_start=args.week_start, force=args.force, db=db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
