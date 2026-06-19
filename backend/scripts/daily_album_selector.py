"""Daily album selector — planner and applier.

Two-phase design to minimise database activity:

  PLANNER (--plan)
    Runs once daily. For every group that does not yet have a cached pre-draw,
    randomly samples the albums that *would* be selected and stores them in a
    local JSON file (the plan cache). No DB writes are made at this stage.

  APPLIER (default, no flags)
    Runs hourly as before. For each group the existing timezone/schedule/
    idempotency logic runs unchanged, but when a pre-drawn entry exists in the
    plan cache those album IDs are used directly instead of performing a new
    random sample. The cache entry is removed once a selection is successfully
    applied so it is not reused on subsequent runs.

Plan cache
    Path: ``DAILY_PLAN_PATH`` env var (default: ``scripts/daily_plan.json``
    relative to this file). The file is a JSON object mapping group ID strings
    to lists of album IDs::

        {"1": [42, 87], "3": [15]}

Cron example:
    # Planner: once daily at noon UTC (after all previous-day midnights,
    #          before the earliest next-day midnight at UTC−12)
    0 12 * * * cd /path/to/spinshare/backend && .venv/bin/python scripts/daily_album_selector.py --plan

    # Applier: hourly, idempotent
    0 * * * * cd /path/to/spinshare/backend && .venv/bin/python scripts/daily_album_selector.py

Usage:
    python scripts/daily_album_selector.py            # apply (1 album per group default)
    python scripts/daily_album_selector.py --n 3      # apply, 3 albums per group
    python scripts/daily_album_selector.py --group 42 # apply, single group only
    python scripts/daily_album_selector.py --plan     # run the planner
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure the app package is importable when run from the backend/ directory.
sys.path.insert(0, ".")

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base
from app.models import Group, GroupAlbum, GroupSettings  # noqa: F401 — ensure all models are registered
from app.services.group_album_service import GroupAlbumService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ==================== PLAN CACHE HELPERS ====================


def _get_cache_path() -> Path:
    default = Path(__file__).parent / "daily_plan.json"
    return Path(os.environ.get("DAILY_PLAN_PATH", default))


def _load_cache() -> dict[str, list[int]]:
    path = _get_cache_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Could not read plan cache (%s); starting fresh", exc)
    return {}


def _save_cache(cache: dict[str, list[int]]) -> None:
    path = _get_cache_path()
    path.write_text(json.dumps(cache, indent=2))


# ==================== PLANNER ====================


def plan(db: Session) -> None:
    """Pre-draw album selections for all groups without an existing cache entry.

    Skips groups that already have a cached pre-draw (i.e. a previous planner run
    whose entry has not yet been applied). Also skips global and chaos-mode groups
    — those require GroupAlbum records to be created at apply time and cannot be
    pre-computed without committing.
    """
    svc = GroupAlbumService(db)
    cache = _load_cache()
    cache_dirty = False

    groups = db.query(Group).all()
    for group in groups:
        key = str(group.id)
        if key in cache:
            log.info("Group %d (%s): already in plan cache, skipping", group.id, group.name)
            continue

        settings = db.query(GroupSettings).filter(GroupSettings.group_id == group.id).first()
        n = settings.daily_album_count if settings else 1

        album_ids = svc.predraw_album_ids(group.id, n)
        if album_ids:
            cache[key] = album_ids
            cache_dirty = True
            log.info(
                "Group %d (%s): pre-drew %d album(s): %s",
                group.id, group.name, len(album_ids), album_ids,
            )
        else:
            log.info(
                "Group %d (%s): skipped (global, chaos, or empty pool)",
                group.id, group.name,
            )

    if cache_dirty:
        _save_cache(cache)
        log.info("Plan cache saved to %s", _get_cache_path())
    else:
        log.info("No new entries to cache")


# ==================== APPLIER ====================


def run(n: int | None, group_id: int | None, db: Session) -> None:
    svc = GroupAlbumService(db)
    cache = _load_cache()
    cache_dirty = False

    groups = db.query(Group).all() if group_id is None else [_get_group(db, group_id)]

    for group in groups:
        # --n flag overrides per-group setting; otherwise use the group's configured count.
        group_n = n if n is not None else (
            group.settings.daily_album_count if group.settings else 1
        )
        key = str(group.id)
        predrawn = cache.get(key)

        try:
            selected = svc.select_daily_albums(
                group.id, n=group_n, predrawn_album_ids=predrawn
            )
            if selected:
                titles = [ga.albums.title for ga in selected]
                log.info("Group %d (%s): today's albums: %s", group.id, group.name, titles)
                # Remove the cache entry whether or not pre-drawn IDs were used — the
                # selection is done for today so the pre-draw is no longer needed.
                if key in cache:
                    del cache[key]
                    cache_dirty = True
            else:
                log.info(
                    "Group %d (%s): no selection (unscheduled day or already selected)",
                    group.id, group.name,
                )
        except Exception as exc:
            log.warning("Group %d (%s): skipped — %s", group.id, group.name, exc)

    if cache_dirty:
        _save_cache(cache)


def _get_group(db: Session, group_id: int) -> Group:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        log.error("Group %d not found", group_id)
        sys.exit(1)
    return group


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily album selector — planner and applier")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Run the planner: pre-draw album selections for all groups and cache them locally",
    )
    parser.add_argument("--n", type=int, default=None, help="Albums to select per group (overrides per-group setting; applier only)")
    parser.add_argument("--group", type=int, default=None, help="Limit to a specific group ID (applier only)")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL, poolclass=NullPool)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        if args.plan:
            plan(db)
        else:
            run(n=args.n, group_id=args.group, db=db)
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    main()
