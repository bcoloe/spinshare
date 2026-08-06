"""Weekly recap generator cron job.

Generates the frozen weekly recap for each group once its Mon–Sun week (in the
group's timezone) has fully elapsed. The generator is idempotent — a group gets
at most one recap per week (enforced by a unique constraint). Running hourly
ensures every group-timezone Monday midnight is caught.

Usage:
    python scripts/weekly_recap_generator.py                       # all due groups
    python scripts/weekly_recap_generator.py --group 42            # single group
    python scripts/weekly_recap_generator.py --group 42 \\
        --week-start 2026-07-27                                    # backfill a past week
    python scripts/weekly_recap_generator.py --group 42 \\
        --week-start 2026-07-27 --force                            # regenerate (dev/test)

Cron example (hourly, idempotent):
    0 * * * * cd /path/to/spinshare/backend && .venv/bin/python scripts/weekly_recap_generator.py
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
from app.models import Group, GroupAlbum, GroupRecap, GroupSettings  # noqa: F401 — register models
from app.services.recap_service import RecapService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(group_id: int | None, week_start: date | None, force: bool, db: Session) -> None:
    svc = RecapService(db)
    groups = db.query(Group).all() if group_id is None else [_get_group(db, group_id)]

    for group in groups:
        try:
            if week_start is not None:
                recap = svc.generate_for_group(group.id, week_start, force=force)
                log.info("Group %d (%s): recap for week %s ready (id=%d)", group.id, group.name, week_start, recap.id)
            else:
                recap = svc.generate_due(group.id)
                if recap is None:
                    log.info("Group %d (%s): no recap due (or global/bot group)", group.id, group.name)
                else:
                    log.info("Group %d (%s): recap for week %s ready (id=%d)", group.id, group.name, recap.week_start, recap.id)
        except Exception as exc:
            db.rollback()
            log.warning("Group %d (%s): skipped — %s", group.id, group.name, exc)


def _get_group(db: Session, group_id: int) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        log.error("Group %d not found", group_id)
        sys.exit(1)
    return group


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

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        run(group_id=args.group, week_start=args.week_start, force=args.force, db=db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
