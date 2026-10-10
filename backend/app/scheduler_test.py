"""Tests for the in-process job scheduler.

The due-ness tests drive a ``JobScheduler`` with a fixed clock and hand-built
schedules: what they pin down is *when* a group is due, which is pure. The tick
tests stub the job runners to prove the property the scheduler exists for — a
tick with nothing due opens no database session. The last group runs the real
thing against the test database.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import sessionmaker

from app import scheduler as scheduler_module
from app.models import Album, Group, GroupAlbum, GroupSettings, User
from app.scheduler import GroupSchedule, JobScheduler
from app.services.scheduled_jobs import JobReport

NY = "America/New_York"
ALL_DAYS = frozenset(range(7))
# 2026-10-12 is a Monday.
MONDAY = date(2026, 10, 12)


def at(day: date, hour: int, minute: int = 0, tz: str = NY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def schedule(group_id: int = 1, *, tz: str = NY, days=ALL_DAYS, selects=True, recaps=True) -> GroupSchedule:
    return GroupSchedule(group_id=group_id, timezone=tz, selection_days=days, selects=selects, recaps=recaps)


def make_scheduler(*schedules: GroupSchedule, now: datetime, session_factory=None) -> JobScheduler:
    clock = MagicMock(return_value=now)
    sched = JobScheduler(
        session_factory or MagicMock(),
        selection_hour=1,
        recap_hour=4,
        clock=clock,
    )
    sched.load(schedules)
    return sched


def report(done=(), rejected=(), failed=()) -> JobReport:
    return JobReport(
        done=list(done),
        rejected={g: "no" for g in rejected},
        failed={g: "boom" for g in failed},
    )


class TestSelectionDue:
    def test_not_due_before_the_local_selection_hour(self):
        sched = make_scheduler(schedule(), now=at(MONDAY + timedelta(days=1), 0, 59))
        assert sched.due(at(MONDAY + timedelta(days=1), 0, 59)).selection == {}

    def test_due_once_the_local_selection_hour_arrives(self):
        tuesday = MONDAY + timedelta(days=1)
        sched = make_scheduler(schedule(), now=at(tuesday, 1))
        assert sched.due(at(tuesday, 1)).selection == {1: tuesday}

    def test_not_due_again_once_recorded_for_the_day(self):
        tuesday = MONDAY + timedelta(days=1)
        now = at(tuesday, 1)
        sched = make_scheduler(schedule(), now=now)
        due = sched.due(now)
        sched.record(due, report(done=[1]), JobReport(), now)

        assert sched.due(at(tuesday, 23)).selection == {}
        assert sched.due(at(tuesday + timedelta(days=1), 1)).selection == {1: tuesday + timedelta(days=1)}

    def test_each_group_rolls_over_on_its_own_clock(self):
        # 01:00 in Tokyo is noon the previous day in New York.
        now = at(MONDAY, 1, tz="Asia/Tokyo")
        sched = make_scheduler(schedule(1, tz=NY), schedule(2, tz="Asia/Tokyo"), now=now)

        due = sched.due(now)

        assert due.selection == {1: MONDAY - timedelta(days=1), 2: MONDAY}

    def test_unscheduled_weekday_is_never_due(self):
        tuesday = MONDAY + timedelta(days=1)
        sched = make_scheduler(schedule(days=frozenset({0})), now=at(tuesday, 9))
        assert sched.due(at(tuesday, 9)).selection == {}

    def test_group_without_settings_selects_every_day(self):
        sched = make_scheduler(schedule(days=None), now=at(MONDAY, 9))
        assert sched.due(at(MONDAY, 9)).selection == {1: MONDAY}

    def test_dealer_group_never_selects(self):
        sched = make_scheduler(schedule(selects=False), now=at(MONDAY, 9))
        assert sched.due(at(MONDAY, 9)).selection == {}


class TestRecapDue:
    def test_not_due_on_monday_before_the_recap_hour(self):
        sched = make_scheduler(schedule(), now=at(MONDAY, 3, 59))
        assert sched.due(at(MONDAY, 3, 59)).recap == {}

    def test_due_for_the_week_just_finished(self):
        sched = make_scheduler(schedule(), now=at(MONDAY, 4))
        assert sched.due(at(MONDAY, 4)).recap == {1: MONDAY - timedelta(days=7)}

    def test_a_fresh_process_catches_up_later_in_the_week(self):
        thursday = MONDAY + timedelta(days=3)
        sched = make_scheduler(schedule(), now=at(thursday, 0))
        assert sched.due(at(thursday, 0)).recap == {1: MONDAY - timedelta(days=7)}

    def test_not_due_again_until_the_next_week_finishes(self):
        now = at(MONDAY, 4)
        sched = make_scheduler(schedule(), now=now)
        sched.record(sched.due(now), JobReport(), report(done=[1]), now)

        assert sched.due(at(MONDAY + timedelta(days=6), 23)).recap == {}
        assert sched.due(at(MONDAY + timedelta(days=7), 4)).recap == {1: MONDAY}

    def test_ineligible_group_never_recaps(self):
        sched = make_scheduler(schedule(recaps=False), now=at(MONDAY, 9))
        assert sched.due(at(MONDAY, 9)).recap == {}


class TestOutcomes:
    def test_rejected_counts_as_finished_for_the_day(self):
        """An exhausted pool won't refill by retrying; re-asking only wakes the database."""
        now = at(MONDAY, 1)
        sched = make_scheduler(schedule(), now=now)
        sched.record(sched.due(now), report(rejected=[1]), JobReport(), now)
        assert sched.due(now + timedelta(minutes=1)).selection == {}

    def test_failed_waits_before_retrying(self):
        now = at(MONDAY, 1)
        sched = make_scheduler(schedule(), now=now)
        sched.record(sched.due(now), report(failed=[1]), JobReport(), now)

        assert sched.due(now + timedelta(minutes=59)).selection == {}
        assert sched.due(now + sched.retry_after).selection == {1: MONDAY}


@pytest.fixture
def stub_jobs(monkeypatch):
    """Replace the job runners with ones that report every requested group done."""
    calls = {"selection": [], "recap": []}

    def fake(kind):
        def run(_db, group_ids, **_):
            calls[kind].append(list(group_ids))
            return JobReport(done=list(group_ids))
        return run

    monkeypatch.setattr(scheduler_module, "run_daily_selection", fake("selection"))
    monkeypatch.setattr(scheduler_module, "run_weekly_recaps", fake("recap"))
    return calls


class TestTick:
    def test_nothing_due_opens_no_session(self, stub_jobs):
        """The point of the scheduler: idle ticks never touch the database."""
        now = at(MONDAY + timedelta(days=1), 0, 30)  # before the selection hour; recaps off
        factory = MagicMock()
        sched = make_scheduler(schedule(recaps=False), now=now, session_factory=factory)

        sched.tick()

        factory.assert_not_called()

    def test_due_work_runs_in_one_session_and_is_recorded(self, stub_jobs):
        now = at(MONDAY, 5)
        factory = MagicMock()
        sched = make_scheduler(schedule(1), schedule(2), now=now, session_factory=factory)

        sched.tick()
        sched.tick()  # everything recorded: the second tick is idle

        factory.assert_called_once()
        factory.return_value.close.assert_called_once()
        assert stub_jobs == {"selection": [[1, 2]], "recap": [[1, 2]]}
        assert sched.status()["recent_runs"][0]["selection"] == {"done": 2, "rejected": 0, "failed": 0}

    def test_stale_schedule_reloads_before_deciding(self, stub_jobs, monkeypatch):
        now = at(MONDAY, 5)
        sched = make_scheduler(now=now)
        sched.mark_stale()
        reloads = []
        monkeypatch.setattr(sched, "reload", lambda db: reloads.append(db) or sched.load([schedule(7)]))

        sched.tick()

        assert len(reloads) == 1
        assert stub_jobs["selection"] == [[7]]

    def test_write_during_reload_is_not_lost(self):
        """A schedule change committed mid-reload must leave the map stale."""
        sched = make_scheduler(now=at(MONDAY, 5))
        db = MagicMock()
        db.query.return_value.options.return_value.all.side_effect = lambda: sched.mark_stale() or []

        sched.reload(db)

        assert sched._needs_reload()


@pytest.fixture
def sample_group(db_session) -> Group:
    user = User(email="sched@test.com", username="sched", password_hash="x")
    group = Group(name="Scheduled", is_public=True, creator=user)
    db_session.add_all([user, group, GroupSettings(group=group)])
    db_session.commit()
    return group


@pytest.fixture
def sample_group_album(db_session, sample_group) -> GroupAlbum:
    album = Album(spotify_album_id="sched_1", title="Spiderland", artist="Slint")
    ga = GroupAlbum(group=sample_group, albums=album, added_by=sample_group.created_by)
    db_session.add(ga)
    db_session.commit()
    return ga


class TestStaleOnCommit:
    """Writes to a group's schedule, committed anywhere in-process, mark the map stale."""

    def test_settings_change_marks_stale_on_commit(self, db_session, sample_group):
        before = scheduler_module.scheduler._generation
        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).one()
        settings.timezone = "Asia/Tokyo"
        db_session.commit()
        assert scheduler_module.scheduler._generation > before

    def test_rolled_back_change_does_not(self, db_session, sample_group):
        settings = db_session.query(GroupSettings).filter_by(group_id=sample_group.id).one()
        settings.timezone = "Asia/Tokyo"
        db_session.flush()
        before = scheduler_module.scheduler._generation
        db_session.rollback()
        db_session.commit()
        assert scheduler_module.scheduler._generation == before


class TestAgainstDatabase:
    def test_tick_draws_a_due_group_then_goes_idle(self, db_session, sample_group, sample_group_album):
        bind = db_session.connection()
        opened = []

        def factory():
            session = sessionmaker(bind=bind, join_transaction_mode="create_savepoint")()
            opened.append(session)
            return session

        sched = JobScheduler(factory, selection_hour=0, recap_hour=0)
        sched.tick()
        sched.tick()

        db_session.expire_all()
        assert db_session.get(GroupAlbum, sample_group_album.id).selected_date is not None
        assert len(opened) == 1  # the second tick decided "nothing due" from memory
        group = next(g for g in sched.status()["groups"] if g["group_id"] == sample_group.id)
        assert group["selected_on"] is not None
