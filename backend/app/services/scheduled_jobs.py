"""The two recurring jobs — daily album selection and the weekly recap — as plain functions.

Both the in-process scheduler (``app/scheduler.py``) and the manual CLI scripts in
``scripts/`` drive these, so there is one definition of what a run does and how a
failing group is contained.

Each group is attempted independently on a shared Session. Outcomes are sorted into
three buckets because callers treat them differently:

* ``done``     — the service returned normally (including "nothing to do today").
* ``rejected`` — the service raised ``HTTPException``: a business refusal such as an
  exhausted nomination pool. Retrying within the day will not change the answer.
* ``failed``   — anything else (a deadlock, a dropped connection). Worth retrying.
"""

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date

from app.models import Group
from app.services.group_album_service import GroupAlbumService
from app.services.recap_service import RecapService
from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

log = logging.getLogger(__name__)


@dataclass
class JobReport:
    done: list[int] = field(default_factory=list)
    rejected: dict[int, str] = field(default_factory=dict)
    failed: dict[int, str] = field(default_factory=dict)

    @property
    def attempted(self) -> int:
        return len(self.done) + len(self.rejected) + len(self.failed)


def _load_groups(db: Session, group_ids: Iterable[int] | None) -> list[Group]:
    query = db.query(Group).options(selectinload(Group.settings)).order_by(Group.id)
    if group_ids is not None:
        query = query.filter(Group.id.in_(list(group_ids)))
    return query.all()


def _run_per_group(db: Session, groups: list[Group], job: Callable[[Group], None]) -> JobReport:
    report = JobReport()
    for group in groups:
        # Read before the job runs: a rollback expires the instance, and reloading
        # it from a Session that just failed is exactly what must be avoided.
        group_id, name = group.id, group.name
        try:
            job(group)
            report.done.append(group_id)
        except HTTPException as exc:
            db.rollback()
            report.rejected[group_id] = str(exc.detail)
            log.warning("Group %d (%s): rejected — %s", group_id, name, exc.detail)
        except Exception as exc:
            # The rollback is what keeps one bad group from taking the rest of the
            # run with it. Every group shares this Session, so a DB-level failure
            # leaves it in pending-rollback; without this, each later group dies on
            # its first query with PendingRollbackError and is reported as another
            # failure, so a run that silently spun nothing still looks plausible.
            db.rollback()
            report.failed[group_id] = repr(exc)
            log.exception("Group %d (%s): failed — %s", group_id, name, exc)
    return report


def run_daily_selection(
    db: Session, group_ids: Iterable[int] | None = None, n: int | None = None
) -> JobReport:
    """Draw today's albums for each group (all groups when ``group_ids`` is None).

    ``n`` overrides every group's configured ``daily_album_count``. Selection is
    idempotent per group-local day, so re-running is harmless.
    """
    svc = GroupAlbumService(db)

    def select(group: Group) -> None:
        group_n = n if n is not None else (group.settings.daily_album_count if group.settings else 1)
        selected = svc.select_daily_albums(group.id, n=group_n)
        log.info(
            "Group %d (%s): today's albums: %s",
            group.id, group.name, [ga.albums.title for ga in selected],
        )

    return _run_per_group(db, _load_groups(db, group_ids), select)


def run_weekly_recaps(
    db: Session,
    group_ids: Iterable[int] | None = None,
    week_start: date | None = None,
    force: bool = False,
) -> JobReport:
    """Generate the most recently completed week's recap for each group.

    With ``week_start`` a specific (group-local Monday) week is generated instead;
    ``force`` regenerates an existing one. Idempotent without ``force``.
    """
    svc = RecapService(db)

    def recap(group: Group) -> None:
        if week_start is not None:
            row = svc.generate_for_group(group.id, week_start, force=force)
            log.info("Group %d (%s): recap for week %s ready (id=%d)", group.id, group.name, week_start, row.id)
            return
        row = svc.generate_due(group.id)
        if row is None:
            log.info("Group %d (%s): no recap due (or global/bot/dealer group)", group.id, group.name)
        else:
            log.info("Group %d (%s): recap for week %s ready (id=%d)", group.id, group.name, row.week_start, row.id)

    return _run_per_group(db, _load_groups(db, group_ids), recap)
