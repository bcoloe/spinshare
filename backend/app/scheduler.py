"""In-process scheduler for the daily album selection and the weekly recap.

These used to run from crontab as separate processes. Running them here instead:

* keeps every write inside the API process, so in-process caches see them;
* lets each group roll over on its *own* local clock rather than the server's;
* makes the schedule observable (``GET /admin/scheduler``).

Deciding *whether* anything is due never touches the database. The scheduler keeps
a small in-memory map of each group's schedule (timezone, selection days, which
jobs apply) and, once a minute, checks the clock against it. The database is
opened only when a group is actually due, or when the map itself needs reloading —
which happens at startup and shortly after a group or its settings change (the
reload lands within a minute of that write, while Neon is still awake from it).

Every job is idempotent per group-local day (selection) or week (recap), so the
first tick after a restart simply catches up anything missed while the process
was down.

This assumes one process runs the scheduler. The app is pinned to one uvicorn
worker for chat already (see ``main.warn_if_sharded``); scaling out needs a
shared lock so that only one worker schedules.
"""

import asyncio
import logging
import threading
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from itertools import chain
from zoneinfo import ZoneInfo

from sqlalchemy import event
from sqlalchemy.orm import Session, selectinload

from app.models import BotSource, Group, GroupSettings
from app.services.recap_service import RecapService
from app.services.scheduled_jobs import JobReport, run_daily_selection, run_weekly_recaps
from app.utils.time_helpers import group_tz, week_start_for

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class GroupSchedule:
    """What the scheduler needs to know about a group, detached from any Session."""

    group_id: int
    timezone: str
    # None when the group has no settings row: select_daily_albums then draws every day.
    selection_days: frozenset[int] | None
    selects: bool  # dealer-mode groups have no shared daily draw
    recaps: bool

    @classmethod
    def from_group(cls, group: Group) -> "GroupSchedule":
        settings = group.settings
        return cls(
            group_id=group.id,
            timezone=group_tz(settings),
            selection_days=frozenset(settings.selection_days) if settings is not None else None,
            selects=not (settings is not None and settings.dealer_mode),
            recaps=RecapService.recap_eligible(group),
        )


@dataclass(frozen=True)
class Due:
    """Groups to run this tick, each with the local day/week it is being run for."""

    selection: dict[int, date]
    recap: dict[int, date]

    def __bool__(self) -> bool:
        return bool(self.selection or self.recap)


class JobScheduler:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        selection_hour: int,
        recap_hour: int,
        clock: Callable[[], datetime] = _utcnow,
        tick_seconds: float = 60,
        retry_after: timedelta = timedelta(hours=1),
    ):
        self._session_factory = session_factory
        self.selection_hour = selection_hour
        self.recap_hour = recap_hour
        self._clock = clock
        self.tick_seconds = tick_seconds
        self.retry_after = retry_after

        self._lock = threading.Lock()
        self._schedules: dict[int, GroupSchedule] | None = None
        # Bumped by every committed write to a group's schedule. The map is fresh
        # when it was loaded at the current generation; comparing generations (not
        # a boolean flag) keeps a write that lands *during* a reload from being lost.
        self._generation = 0
        self._loaded_generation = -1
        self._selected_on: dict[int, date] = {}
        self._recapped_week: dict[int, date] = {}
        # A group whose job failed (not rejected) waits this long before retrying,
        # so a persistent fault costs one wake an hour, not one a minute.
        self._retry_at: dict[tuple[str, int], datetime] = {}

        self.started_at: datetime | None = None
        self.last_tick_at: datetime | None = None
        self.last_error: str | None = None
        self.runs: deque[dict] = deque(maxlen=20)
        self._task: asyncio.Task | None = None

    # ---------- schedule map ----------

    def mark_stale(self) -> None:
        """Record that a group's schedule may have changed; the next tick reloads."""
        with self._lock:
            self._generation += 1

    def _needs_reload(self) -> bool:
        with self._lock:
            return self._schedules is None or self._loaded_generation != self._generation

    def reload(self, db: Session) -> None:
        """Rebuild the schedule map from the database."""
        with self._lock:
            generation = self._generation
        groups = (
            db.query(Group)
            .options(selectinload(Group.settings), selectinload(Group.bot_sources))
            .all()
        )
        self.load((GroupSchedule.from_group(g) for g in groups), generation=generation)

    def load(self, schedules: Iterable[GroupSchedule], *, generation: int | None = None) -> None:
        """Install a schedule map. ``generation`` is the one current when it was read."""
        installed = {s.group_id: s for s in schedules}
        with self._lock:
            self._schedules = installed
            self._loaded_generation = self._generation if generation is None else generation

    # ---------- due-ness (pure, no database) ----------

    def _selection_due(self, s: GroupSchedule, now: datetime) -> date | None:
        if not s.selects:
            return None
        local = now.astimezone(ZoneInfo(s.timezone))
        today = local.date()
        if local.hour < self.selection_hour or self._selected_on.get(s.group_id) == today:
            return None
        if s.selection_days is not None and today.weekday() not in s.selection_days:
            return None  # select_daily_albums would return [] without drawing
        return today

    def _recap_due(self, s: GroupSchedule, now: datetime) -> date | None:
        if not s.recaps:
            return None
        local = now.astimezone(ZoneInfo(s.timezone))
        # The recap covers the Mon–Sun week that has most recently finished.
        week = week_start_for(local.date()) - timedelta(days=7)
        if self._recapped_week.get(s.group_id) == week:
            return None
        if local.weekday() == 0 and local.hour < self.recap_hour:
            return None
        return week

    def due(self, now: datetime) -> Due:
        """Which groups need a job run at ``now``. Requires a loaded schedule map."""
        with self._lock:
            schedules = list((self._schedules or {}).values())
            selection, recap = {}, {}
            for s in schedules:
                if (day := self._selection_due(s, now)) and not self._waiting("selection", s.group_id, now):
                    selection[s.group_id] = day
                if (week := self._recap_due(s, now)) and not self._waiting("recap", s.group_id, now):
                    recap[s.group_id] = week
        return Due(selection, recap)

    def _waiting(self, job: str, group_id: int, now: datetime) -> bool:
        retry_at = self._retry_at.get((job, group_id))
        return retry_at is not None and now < retry_at

    def record(self, due: Due, selection: JobReport, recap: JobReport, now: datetime) -> None:
        """Fold a run's outcome back into the in-memory state.

        Done and rejected groups are finished for the day/week — a refusal such as
        an exhausted pool will not change on retry. Failed groups retry later.
        """
        with self._lock:
            for job, days, report, finished in (
                ("selection", due.selection, selection, self._selected_on),
                ("recap", due.recap, recap, self._recapped_week),
            ):
                for group_id in chain(report.done, report.rejected):
                    finished[group_id] = days[group_id]
                    self._retry_at.pop((job, group_id), None)
                for group_id in report.failed:
                    self._retry_at[(job, group_id)] = now + self.retry_after

    # ---------- running ----------

    def tick(self) -> None:
        """One scheduling pass. Opens a database session only if there is work."""
        now = self._clock()
        self.last_tick_at = now
        if not self._needs_reload() and not self.due(now):
            return

        db = self._session_factory()
        try:
            if self._needs_reload():
                self.reload(db)
            due = self.due(now)
            if not due:
                return
            selection = run_daily_selection(db, list(due.selection)) if due.selection else JobReport()
            recap = run_weekly_recaps(db, list(due.recap)) if due.recap else JobReport()
            self.record(due, selection, recap, now)
            self.runs.append({
                "ran_at": now,
                "selection": _summary(selection),
                "recap": _summary(recap),
            })
            log.info(
                "Scheduler ran: selection %s, recap %s", _summary(selection), _summary(recap)
            )
        finally:
            db.close()

    async def run_forever(self) -> None:
        self.started_at = self._clock()
        failures = 0
        while True:
            try:
                # Jobs are synchronous database work; keep them off the event loop.
                await asyncio.to_thread(self.tick)
                failures = 0
                self.last_error = None
            except Exception as exc:
                # Back off on repeated failure so a persistent fault doesn't wake
                # the database every minute.
                failures += 1
                self.last_error = repr(exc)
                log.exception("Scheduler tick failed")
            delay = min(self.tick_seconds * 2 ** failures, self.retry_after.total_seconds())
            await asyncio.sleep(delay)

    def start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self.run_forever(), name="job-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    # ---------- observability ----------

    def status(self) -> dict:
        now = self._clock()
        with self._lock:
            schedules = sorted((self._schedules or {}).values(), key=lambda s: s.group_id)
            groups = [
                {
                    "group_id": s.group_id,
                    "timezone": s.timezone,
                    "selected_on": self._selected_on.get(s.group_id),
                    "next_selection_at": self._next_selection_at(s, now),
                    "recapped_week": self._recapped_week.get(s.group_id),
                    "next_recap_at": self._next_recap_at(s, now),
                    "retry_at": max(
                        (t for (_, gid), t in self._retry_at.items() if gid == s.group_id),
                        default=None,
                    ),
                }
                for s in schedules
            ]
        return {
            "running": self._task is not None and not self._task.done(),
            "started_at": self.started_at,
            "last_tick_at": self.last_tick_at,
            "last_error": self.last_error,
            "selection_hour": self.selection_hour,
            "recap_hour": self.recap_hour,
            "schedule_loaded": self._schedules is not None,
            "recent_runs": list(self.runs),
            "groups": groups,
        }

    def _next_selection_at(self, s: GroupSchedule, now: datetime) -> datetime | None:
        if not s.selects:
            return None
        if self._selection_due(s, now) is not None:
            return now
        tz = ZoneInfo(s.timezone)
        local_today = now.astimezone(tz).date()
        for offset in range(8):
            day = local_today + timedelta(days=offset)
            at = datetime.combine(day, time(self.selection_hour), tz)
            if at <= now or self._selected_on.get(s.group_id) == day:
                continue
            if s.selection_days is None or day.weekday() in s.selection_days:
                return at
        return None

    def _next_recap_at(self, s: GroupSchedule, now: datetime) -> datetime | None:
        if not s.recaps:
            return None
        if self._recap_due(s, now) is not None:
            return now
        tz = ZoneInfo(s.timezone)
        local_today = now.astimezone(tz).date()
        monday = week_start_for(local_today)
        at = datetime.combine(monday, time(self.recap_hour), tz)
        return at if at > now else datetime.combine(monday + timedelta(days=7), time(self.recap_hour), tz)


def _summary(report: JobReport) -> dict:
    return {"done": len(report.done), "rejected": len(report.rejected), "failed": len(report.failed)}


# ---------- keeping the schedule map fresh ----------

_SCHEDULE_MODELS = (Group, GroupSettings, BotSource)
_PENDING_KEY = "scheduler_schedule_changed"


@event.listens_for(Session, "after_flush")
def _note_schedule_writes(session: Session, _flush_context) -> None:
    if any(isinstance(obj, _SCHEDULE_MODELS) for obj in chain(session.new, session.dirty, session.deleted)):
        session.info[_PENDING_KEY] = True


@event.listens_for(Session, "after_commit")
def _publish_schedule_writes(session: Session) -> None:
    if session.info.pop(_PENDING_KEY, False):
        scheduler.mark_stale()


@event.listens_for(Session, "after_rollback")
def _discard_schedule_writes(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


def _build_default() -> JobScheduler:
    from app.config import get_settings
    from app.database import SessionLocal

    settings = get_settings()
    return JobScheduler(
        SessionLocal,
        selection_hour=settings.DAILY_SELECTION_HOUR,
        recap_hour=settings.WEEKLY_RECAP_HOUR,
    )


scheduler = _build_default()
