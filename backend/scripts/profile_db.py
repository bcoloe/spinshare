"""Measure how many bytes each page load pulls out of Postgres — the quantity Neon bills.

Neon meters network transfer: every byte the database sends to the app, including
connection setup. This script replays real page loads (the endpoint bursts seen in
the nginx access log) against a local database and reports, per endpoint:

    requests, DB connections opened, SQL statements, rows returned,
    DB→app bytes on the wire, and response body bytes.

How it measures:
  * A small TCP relay sits between the app and Postgres and counts the bytes the
    server sends back, so the figure is actual wire traffic (row data plus protocol
    overhead), not an estimate from row contents.
  * SQLAlchemy cursor events count statements and rows per request.
  * The production engine is used unchanged (NullPool), so connection churn is real.
    Local Postgres has no TLS, so a configurable per-connection overhead is added to
    estimate what the same traffic costs against Neon.

Two reports:

  * Per scenario (default): each page load measured cold, warm (same user again)
    and peer (another group member), per endpoint. Baseline: ``baseline.json``.
  * ``--day``: a synthetic day of sessions replayed in time order, plus the job
    scheduler's database touches, folded into how many minutes Neon compute stays
    awake and how many cold starts that takes. This is the number Neon bills.
    Baseline: ``baseline_day.json``.

Workflow (run from the backend/ directory):
    .venv/bin/python scripts/seed_profile_data.py --reset
    .venv/bin/python scripts/profile_db.py --json baseline.json
    .venv/bin/python scripts/profile_db.py --day --json baseline_day.json
    # ...make changes...
    .venv/bin/python scripts/profile_db.py --compare baseline.json
    .venv/bin/python scripts/profile_db.py --day --compare baseline_day.json

The scenarios mirror what the frontend fires; when a frontend change alters which
queries a page triggers (e.g. invalidation after autosave), update SCENARIOS to match.
Every GET route must appear in a scenario or in UNPROFILED_GETS — see
scripts/profile_db_test.py.
"""

import argparse
import asyncio
import json
import os
import random
import re
import sys
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

sys.path.insert(0, ".")

from sqlalchemy.engine import make_url  # noqa: E402

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/spinshare_profile"
# Rough cost of a fresh TLS + SCRAM Postgres connection to Neon (cert chain,
# handshake, auth, parameter status). Measure against a Neon branch to refine.
DEFAULT_TLS_OVERHEAD_BYTES = 6000


# ==================== BYTE-COUNTING RELAY ====================


class CountingRelay:
    """TCP relay that counts server→client bytes and connections, in a background thread."""

    def __init__(self, upstream_host: str, upstream_port: int):
        self.upstream = (upstream_host, upstream_port)
        self.bytes_down = 0
        self.bytes_up = 0
        self.connections = 0
        self.active = 0
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self.port: int | None = None
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        server = self._loop.run_until_complete(
            asyncio.start_server(self._handle, "127.0.0.1", 0)
        )
        self.port = server.sockets[0].getsockname()[1]
        self._ready.set()
        self._loop.run_forever()

    async def _pipe(self, reader, writer, downstream: bool) -> None:
        try:
            while data := await reader.read(65536):
                with self._lock:
                    if downstream:
                        self.bytes_down += len(data)
                    else:
                        self.bytes_up += len(data)
                writer.write(data)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()

    async def _handle(self, client_reader, client_writer) -> None:
        with self._lock:
            self.connections += 1
            self.active += 1
        try:
            server_reader, server_writer = await asyncio.open_connection(*self.upstream)
            await asyncio.gather(
                self._pipe(client_reader, server_writer, downstream=False),
                self._pipe(server_reader, client_writer, downstream=True),
            )
        finally:
            with self._lock:
                self.active -= 1

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self.bytes_down, self.connections

    def wait_idle(self, timeout: float = 2.0) -> None:
        """Let closing connections flush their last bytes before a snapshot."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.active == 0:
                    return
            time.sleep(0.005)


# ==================== STATEMENT COUNTING ====================


class StatementCounter:
    def __init__(self):
        self.statements = 0
        self.rows = 0

    def attach(self, engine) -> None:
        from sqlalchemy import event

        @event.listens_for(engine, "after_cursor_execute")
        def _after(conn, cursor, statement, parameters, context, executemany):
            self.statements += 1
            if cursor.rowcount and cursor.rowcount > 0 and cursor.description is not None:
                self.rows += cursor.rowcount



# ==================== SCENARIOS ====================

# Each step is (method, path_template[, json_body]). Placeholders are filled from the
# seeded data: {g} group, {a} reviewed album, {u} the caller's username, {d} draft
# album, {r} draft id.
GROUP_SHELL = [
    ("GET", "/notifications"),
    ("GET", "/invitations/pending"),
    ("GET", "/users/me/stats"),
    ("GET", "/groups/search?username={u}"),
]

# Page loads. These are measured three ways (see PASSES).
READ_SCENARIOS: dict[str, list] = {
    # Landing on a group page (default "Today's Spin" tab). The history query is
    # only enabled on the Review History tab (it used to load on every visit).
    "group_page": GROUP_SHELL + [
        ("GET", "/groups/{g}"),
        ("GET", "/groups/{g}/members"),
        ("GET", "/groups/{g}/nominations/count"),
        ("GET", "/groups/{g}/albums/today"),
    ],
    # Switching to the Review History tab.
    "history_tab": [
        ("GET", "/groups/{g}/albums/history"),
        ("GET", "/groups/{g}/reviews/me"),
        ("GET", "/groups/{g}/guesses/me"),
    ],
    "album_page": GROUP_SHELL + [
        ("GET", "/albums/{a}"),
        ("GET", "/albums/{a}/stats"),
        ("GET", "/albums/{a}/reviews"),
        ("GET", "/albums/{a}/reviews/me"),
    ],
    "nominations_tab": [
        ("GET", "/users/me/nominations"),
    ],
}

# Writes. Measured cold only: repeating a write measures the same thing again.
WRITE_SCENARIOS: dict[str, list] = {
    # One draft autosave (fires 3 s after typing stops) plus any refetches that
    # useUpdateReview.onSuccess triggers. Drafts now only patch the author's own
    # cache, so there are none; before that change this scenario also refetched
    # album reviews, album stats, group reviews/me, and the full history.
    # Keep in sync with frontend/src/hooks/useDailySpin.ts.
    "draft_autosave": [
        ("PATCH", "/albums/{d}/reviews/{r}?group_id={g}",
         {"comment": "still thinking about this one", "is_draft": True}),
    ],
}

SCENARIOS: dict[str, list] = {**READ_SCENARIOS, **WRITE_SCENARIOS}

# How each read scenario is measured, in order, every repeat:
#   cold — the first load, as the main user;
#   warm — the same user loads it again straight away;
#   peer — another member of the same group loads it.
# Without server-side caching all three cost the same. With it, warm shows what a
# returning visitor costs and peer shows how much group-shared data is reused.
# Report keys are "<scenario>" for cold (so older baselines still compare) and
# "<scenario> (warm)" / "<scenario> (peer)" for the others.
PASSES = ("cold", "warm", "peer")

# Every GET route must be either exercised by a scenario above or listed here with
# the reason it is not (enforced by scripts/profile_db_test.py). Adding an endpoint
# therefore forces a decision about whether its database cost is being measured.
_ADMIN = "admin-only; negligible traffic"
_EXTERNAL = "third-party auth / catalog lookup; cost is outside our database"
_ONE_SHOT = "one-shot landing (invite or join link); rarely repeated"
_TODO = "user-facing but not yet profiled; add a scenario before optimizing it"
UNPROFILED_GETS: dict[str, str] = {
    "/admin/link-reports": _ADMIN,
    "/admin/link-reports/count": _ADMIN,
    "/admin/metrics": _ADMIN,
    "/admin/scheduler": _ADMIN,
    "/users/": _ADMIN,
    "/users/spotify/callback": _EXTERNAL,
    "/users/spotify/connect-url": _EXTERNAL,
    "/users/spotify/token": _EXTERNAL,
    "/users/apple-music/developer-token": _EXTERNAL,
    "/albums/search": _EXTERNAL,
    "/albums/spotify/{}": _EXTERNAL,
    "/albums/apple-music/{}": _EXTERNAL,
    "/invitations/{}": _ONE_SHOT,
    "/join/{}": _ONE_SHOT,
    "/public/spin": _TODO,
    "/albums/{}/nomination-counts": _TODO,
    "/artists/overview": _TODO,
    "/chat/unread": _TODO,
    "/explore/albums": _TODO,
    "/explore/groups": _TODO,
    "/explore/stats": _TODO,
    "/explore/users": _TODO,
    "/groups/{}/albums": _TODO,
    "/groups/{}/albums/catchup": _TODO,
    "/groups/{}/albums/{}": _TODO,
    "/groups/{}/albums/{}/guess/me": _TODO,
    "/groups/{}/albums/{}/guess/options": _TODO,
    "/groups/{}/deals/today": _TODO,
    "/groups/{}/invitations": _TODO,
    "/groups/{}/invite-link": _TODO,
    "/groups/{}/members/{}": _TODO,
    "/groups/{}/messages": _TODO,
    "/groups/{}/participation/me": _TODO,
    "/groups/{}/presence": _TODO,
    "/groups/{}/recaps": _TODO,
    "/groups/{}/recaps/latest": _TODO,
    "/groups/{}/recaps/{}": _TODO,
    "/groups/{}/reviews": _TODO,
    "/groups/{}/stats": _TODO,
    "/groups/name/{}": _TODO,
    "/notifications/history": _TODO,
    "/stats/albums/{}/reviews": _TODO,
    "/stats/groups/{}/albums/{}/guesses": _TODO,
    "/stats/groups/{}/members/{}/guesses": _TODO,
    "/users/me": _TODO,
    "/users/me/group-activity": _TODO,
    "/users/me/recaps/pending": _TODO,
    "/users/search/{}": _TODO,
    "/users/{}": _TODO,
    "/users/{}/groups": _TODO,
    "/users/{}/nominations/breakdown": _TODO,
    "/users/{}/profile": _TODO,
    "/users/{}/reviews": _TODO,
    "/users/{}/review-stats": _TODO,
}


def route_shape(path: str) -> str:
    """Normalize a route or scenario template: drop the query, blank every placeholder."""
    return re.sub(r"\{[^}]*\}", "{}", path.split("?", 1)[0])


def profiled_get_shapes() -> set[str]:
    return {route_shape(step[1]) for steps in SCENARIOS.values() for step in steps if step[0] == "GET"}


@dataclass
class Tally:
    requests: int = 0
    connections: int = 0
    statements: int = 0
    rows: int = 0
    db_bytes: int = 0
    response_bytes: int = 0
    errors: int = 0

    def add(self, other: "Tally") -> None:
        for field in self.__dataclass_fields__:
            setattr(self, field, getattr(self, field) + getattr(other, field))


def _pick_fixtures(db) -> dict:
    """Choose the busiest regular group, two of its members, a reviewed album, and a draft target."""
    from sqlalchemy import func

    from app.models import Group, GroupAlbum, Review, User, group_members

    gid = (
        db.query(GroupAlbum.group_id)
        .join(Group, Group.id == GroupAlbum.group_id)
        .filter(Group.is_global == False, GroupAlbum.selected_date.isnot(None))  # noqa: E712
        .group_by(GroupAlbum.group_id)
        .order_by(func.count().desc())
        .limit(1)
        .scalar()
    )
    if gid is None:
        raise SystemExit("No selected albums found — run scripts/seed_profile_data.py first.")
    member_ids = sorted(
        row[0] for row in db.query(group_members.c.user_id).filter(group_members.c.group_id == gid)
    )
    if len(member_ids) < 2:
        raise SystemExit("The busiest group has one member — reseed so a peer can be measured.")
    reviewed_album = (
        db.query(Review.album_id)
        .filter(Review.album_id.in_(
            db.query(GroupAlbum.album_id).filter(GroupAlbum.group_id == gid)
        ))
        .group_by(Review.album_id)
        .order_by(func.count().desc())
        .limit(1)
        .scalar()
    )
    # A selected album in the group that some member has not reviewed — the draft target.
    for uid in member_ids:
        mine = db.query(Review.album_id).filter(Review.user_id == uid)
        draft_album = (
            db.query(GroupAlbum.album_id)
            .filter(
                GroupAlbum.group_id == gid,
                GroupAlbum.selected_date.isnot(None),
                GroupAlbum.album_id.notin_(mine),
            )
            .limit(1)
            .scalar()
        )
        if draft_album is not None:
            members = [db.get(User, m) for m in member_ids]
            user = next(m for m in members if m.id == uid)
            return {
                "g": gid, "a": reviewed_album, "d": draft_album,
                "user": user, "members": members,
            }
    raise SystemExit("Every member has reviewed every album — reseed with a lower --review-rate.")


# ==================== HARNESS ====================


@dataclass
class Identity:
    user_id: int
    username: str
    headers: dict


class Harness:
    """The app wired to the profile database through the counting relay.

    ``request`` returns what one call cost the database. ``main`` is the member
    whose pages are profiled (and who owns the autosave draft); ``peer`` is another
    member of the same group; ``members`` is everyone in it.
    """

    def __init__(self, client, relay: CountingRelay, counter: StatementCounter, fixtures: dict, members):
        self.client = client
        self.relay = relay
        self.counter = counter
        self.fixtures = fixtures
        self.members: list[Identity] = members
        self.main = next(m for m in members if m.user_id == fixtures["user"].id)
        self.peer = next(m for m in members if m.user_id != self.main.user_id)

    def placeholders(self, who: Identity) -> dict:
        f = self.fixtures
        return {"g": f["g"], "a": f["a"], "d": f["d"], "r": f.get("r"), "u": who.username}

    def request(self, who: Identity, method: str, path: str, body=None):
        """Issue one request; return (Tally of its DB cost, response)."""
        relay, counter = self.relay, self.counter
        relay.wait_idle()
        bytes_before, conns_before = relay.snapshot()
        stmts_before, rows_before = counter.statements, counter.rows
        resp = self.client.request(method, path, headers=who.headers, json=body)
        relay.wait_idle()
        bytes_after, conns_after = relay.snapshot()
        return Tally(
            requests=1,
            connections=conns_after - conns_before,
            statements=counter.statements - stmts_before,
            rows=counter.rows - rows_before,
            db_bytes=bytes_after - bytes_before,
            response_bytes=len(resp.content),
            errors=int(resp.status_code >= 400),
        ), resp

    def step(self, who: Identity, step, label: str):
        method, template = step[0], step[1]
        body = step[2] if len(step) > 2 else None
        path = template.format(**self.placeholders(who))
        tally, resp = self.request(who, method, path, body)
        if resp.status_code >= 400:
            print(f"  ! {label}: {method} {path} -> {resp.status_code}", file=sys.stderr)
        return tally


@contextmanager
def harness(url: str):
    target = make_url(url)
    relay = CountingRelay(target.host or "localhost", target.port or 5432)
    os.environ["DATABASE_URL"] = target.set(host="127.0.0.1", port=relay.port).render_as_string(
        hide_password=False
    )
    # The scheduler would tick against the profile database during the run and
    # land its queries on whatever request happened to be measured.
    os.environ["SCHEDULER_ENABLED"] = "false"

    # Imported only now: app.database builds its engine from DATABASE_URL at import.
    from fastapi.testclient import TestClient

    from app.database import SessionLocal, engine
    from app.main import app
    from app.models import Review
    from app.utils.security import create_access_token

    counter = StatementCounter()
    counter.attach(engine)

    db = SessionLocal()
    fixtures = _pick_fixtures(db)
    members = [
        Identity(m.id, m.username, {"Authorization": f"Bearer {create_access_token({'sub': str(m.id)})}"})
        for m in fixtures["members"]
    ]
    db.close()

    with TestClient(app) as client:
        h = Harness(client, relay, counter, fixtures, members)
        # The autosave scenario edits an existing draft, so create one up front.
        _, resp = h.request(
            h.main, "POST", f"/albums/{fixtures['d']}/reviews?group_id={fixtures['g']}",
            {"comment": "first thoughts", "is_draft": True},
        )
        if resp.status_code >= 400:
            raise SystemExit(f"Could not create the draft review: {resp.status_code} {resp.text}")
        fixtures["r"] = resp.json()["id"]
        try:
            yield h
        finally:
            db = SessionLocal()
            db.query(Review).filter(Review.id == fixtures["r"]).delete()
            db.commit()
            db.close()


# ==================== PER-SCENARIO REPORT ====================


def _pass_key(name: str, pass_: str) -> str:
    return name if pass_ == "cold" else f"{name} ({pass_})"


def run_scenarios(h: Harness, repeat: int, tls_overhead: int) -> dict:
    results: dict[str, dict[str, Tally]] = defaultdict(dict)

    def measure(key: str, who: Identity, steps) -> None:
        for step in steps:
            results[key].setdefault(f"{step[0]} {step[1]}", Tally()).add(h.step(who, step, key))

    for _ in range(repeat):
        for name, steps in READ_SCENARIOS.items():
            for pass_ in PASSES:
                measure(_pass_key(name, pass_), h.peer if pass_ == "peer" else h.main, steps)
        for name, steps in WRITE_SCENARIOS.items():
            measure(name, h.main, steps)

    # Per-repeat averages, so --repeat only smooths noise and never inflates totals.
    report: dict[str, dict] = {}
    for name, per_endpoint in results.items():
        endpoints = {}
        for key, tally in per_endpoint.items():
            avg = {k: round(v / repeat, 1) for k, v in asdict(tally).items()}
            avg["neon_est_bytes"] = round(avg["db_bytes"] + avg["connections"] * tls_overhead, 1)
            endpoints[key] = avg
        total = {k: round(sum(e[k] for e in endpoints.values()), 1) for k in next(iter(endpoints.values()))}
        report[name] = {"endpoints": endpoints, "total": total}
    return report


# ==================== DAY SIMULATION ====================

# Relative chance a session starts in each server-local hour (00..23). The shape —
# quiet overnight, building through the day, peaking in the evening — follows the
# production nginx log; pass --hourly-weights to replay a measured histogram.
DEFAULT_HOURLY_WEIGHTS = (1, 1, 1, 1, 1, 1, 2, 3, 4, 4, 4, 5, 5, 5, 5, 5, 6, 7, 8, 8, 7, 5, 3, 2)
SERVER_TZ = "America/New_York"
# Neon suspends compute after this long without a query (fixed on the free plan).
AUTOSUSPEND = timedelta(minutes=5)
# Seconds between requests inside a scenario, and between scenarios in a session.
STEP_GAP, SCENARIO_GAP = 1, 20
# Autosave fires 3 s after typing stops; a burst is that many saves in one sitting.
AUTOSAVE_GAP = 30


def awake_intervals(touches: list[datetime], window: timedelta = AUTOSUSPEND) -> list[tuple[datetime, datetime]]:
    """Merge database touches into the intervals Neon compute stays awake.

    Every touch keeps compute up until ``window`` after it; touches closer together
    than that share one interval. Each interval begins with a cold start (a wake).
    """
    intervals: list[tuple[datetime, datetime]] = []
    for t in sorted(touches):
        if intervals and t <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], t + window))
        else:
            intervals.append((t, t + window))
    return intervals


def summarize_touches(touches: list[datetime], connections: int | None = None) -> dict:
    intervals = awake_intervals(touches)
    return {
        "touches": len(touches),
        "connections": len(touches) if connections is None else connections,
        "wakes": len(intervals),
        "awake_minutes": round(sum((end - start).total_seconds() for start, end in intervals) / 60, 1),
    }


def legacy_cron_touches(day: date) -> list[datetime]:
    """When the crontab this scheduler replaced hit the database on ``day``."""
    tz = ZoneInfo(SERVER_TZ)
    touches = [datetime.combine(day, dtime(1), tz)]  # 0 1 * * *  daily_album_selector
    if day.weekday() == 0:
        touches.append(datetime.combine(day, dtime(4), tz))  # 0 4 * * 1  weekly_recap_generator
    return touches


def scheduler_touches(h: Harness, day: date) -> list[datetime]:
    """When the in-process scheduler would hit the database on ``day``, in steady state.

    Drives the real scheduler's due-ness logic minute by minute against the profile
    database's group schedules, recording every due group as done (nothing is
    actually drawn). The state is primed at the start of the day as if every
    earlier day had already run, so startup catch-up is not counted.
    """
    from app.database import SessionLocal
    from app.scheduler import JobScheduler
    from app.services.scheduled_jobs import JobReport

    sched = JobScheduler(SessionLocal, selection_hour=_settings().DAILY_SELECTION_HOUR,
                         recap_hour=_settings().WEEKLY_RECAP_HOUR)
    db = SessionLocal()
    sched.reload(db)
    db.close()

    def run_all(now: datetime) -> bool:
        due = sched.due(now)
        sched.record(due, JobReport(done=list(due.selection)), JobReport(done=list(due.recap)), now)
        return bool(due)

    start = datetime.combine(day, dtime(0), ZoneInfo(SERVER_TZ))
    # A group already caught up through yesterday. Recaps may legitimately come due
    # today (Monday), so prime them from the previous evening, not from midnight.
    run_all(start - timedelta(hours=1))
    touches = []
    for minute in range(24 * 60):
        now = start + timedelta(minutes=minute)
        if run_all(now):
            touches.append(now)
    return touches


def _settings():
    from app.config import get_settings

    return get_settings()


def build_sessions(h: Harness, day: date, users: int, sessions_per_user: int,
                   weights, autosave_saves: int, rng: random.Random) -> list[tuple[datetime, Identity, tuple]]:
    """A day of page loads as (virtual time, who, step) in time order."""
    tz = ZoneInfo(SERVER_TZ)
    people = [h.main] + [m for m in h.members if m is not h.main][: max(users - 1, 0)]
    events = []
    for who in people:
        for _ in range(sessions_per_user):
            hour = rng.choices(range(24), weights=weights)[0]
            t = datetime.combine(day, dtime(hour), tz) + timedelta(seconds=rng.randrange(3600))
            flow = ["group_page"]
            flow += [name for name, p in (("history_tab", 0.5), ("album_page", 0.4), ("nominations_tab", 0.2))
                     if rng.random() < p]
            for name in flow:
                for step in READ_SCENARIOS[name]:
                    events.append((t, who, step))
                    t += timedelta(seconds=STEP_GAP)
                t += timedelta(seconds=SCENARIO_GAP)
            # Only the main member has a draft to autosave.
            if who is h.main:
                for _ in range(autosave_saves):
                    events.append((t, who, WRITE_SCENARIOS["draft_autosave"][0]))
                    t += timedelta(seconds=AUTOSAVE_GAP)
    events.sort(key=lambda e: e[0])
    return events


def simulate_day(h: Harness, *, day: date, users: int, sessions_per_user: int, weights,
                 autosave_saves: int, seed: int) -> dict:
    """Replay a synthetic day and estimate how long it keeps Neon compute awake.

    Requests are issued for real, in virtual-time order, so whatever the server
    does between them (caching, for instance) shows up in the connections each one
    opens. Only requests that open a connection count as touches.

    Caveat: the replay runs in seconds, not a day, so anything that expires on a
    wall-clock timer in the server will look fresher here than it would live.
    """
    events = build_sessions(h, day, users, sessions_per_user, weights, autosave_saves, random.Random(seed))
    user_touches, connections = [], 0
    for t, who, step in events:
        tally = h.step(who, step, "day")
        if tally.connections:
            user_touches.append(t)
            connections += tally.connections
    sched = scheduler_touches(h, day)
    return {
        "day": day.isoformat(),
        "params": {"users": users, "sessions_per_user": sessions_per_user,
                   "autosave_saves": autosave_saves, "seed": seed, "requests": len(events)},
        "user_traffic": summarize_touches(user_touches, connections),
        "scheduler": summarize_touches(sched),
        "legacy_cron": summarize_touches(legacy_cron_touches(day)),
        "total": summarize_touches(user_touches + sched, connections + len(sched)),
    }


def print_day(report: dict, baseline: dict | None) -> None:
    p = report["params"]
    print(f"\n== simulated day {report['day']} — {p['users']} users × {p['sessions_per_user']} sessions, "
          f"{p['requests']} requests ==")
    header = f"{'source':<16}{'connections':>13}{'wakes':>8}{'awake min':>12}"
    print(header)
    print("-" * len(header))
    for source in ("user_traffic", "scheduler", "legacy_cron", "total"):
        s = report[source]
        line = f"{source:<16}{s['connections']:>13}{s['wakes']:>8}{s['awake_minutes']:>12.1f}"
        before = (baseline or {}).get(source)
        if before and before["awake_minutes"]:
            delta = (s["awake_minutes"] - before["awake_minutes"]) / before["awake_minutes"]
            line += f"   {delta:+.0%} awake vs baseline"
        print(line)
    print("(legacy_cron is the replaced crontab, for comparison; it is not part of total)")


# ==================== OUTPUT ====================

COLUMNS = ("requests", "connections", "statements", "rows", "db_bytes", "neon_est_bytes", "response_bytes")


def _kb(n: float) -> str:
    return f"{n / 1024:,.1f}K"


def print_report(report: dict, baseline: dict | None) -> None:
    for name, data in report.items():
        print(f"\n== {name} ==")
        header = f"{'endpoint':<52}{'conn':>6}{'stmts':>7}{'rows':>8}{'db':>11}{'neon est':>11}{'resp':>10}"
        print(header)
        print("-" * len(header))
        rows = list(data["endpoints"].items()) + [("TOTAL", data["total"])]
        for key, e in rows:
            line = (
                f"{key[:51]:<52}{e['connections']:>6.0f}{e['statements']:>7.0f}{e['rows']:>8.0f}"
                f"{_kb(e['db_bytes']):>11}{_kb(e['neon_est_bytes']):>11}{_kb(e['response_bytes']):>10}"
            )
            if baseline and name in baseline:
                before = (
                    baseline[name]["total"] if key == "TOTAL"
                    else baseline[name]["endpoints"].get(key)
                )
                if before and before["neon_est_bytes"]:
                    delta = (e["neon_est_bytes"] - before["neon_est_bytes"]) / before["neon_est_bytes"]
                    line += f"   {delta:+.0%} vs baseline"
            print(line)

    grand = sum(d["total"]["neon_est_bytes"] for d in report.values())
    print(f"\nAll scenarios, estimated Neon transfer: {_kb(grand)}")
    if baseline:
        grand_before = sum(d["total"]["neon_est_bytes"] for d in baseline.values())
        if grand_before:
            print(f"Baseline: {_kb(grand_before)}  ({(grand - grand_before) / grand_before:+.0%})")

def main() -> None:
    parser = argparse.ArgumentParser(description="Profile DB→app transfer per page load")
    parser.add_argument("--database-url", default=DEFAULT_URL)
    parser.add_argument("--repeat", type=int, default=3, help="Runs per scenario (averaged)")
    parser.add_argument("--tls-overhead-bytes", type=int, default=DEFAULT_TLS_OVERHEAD_BYTES)
    parser.add_argument("--json", metavar="PATH", help="Write the report to PATH")
    parser.add_argument("--compare", metavar="PATH", help="Show deltas against a saved report")
    day = parser.add_argument_group("day simulation")
    day.add_argument("--day", action="store_true", help="Simulate a day and report Neon awake time instead")
    day.add_argument("--day-date", type=date.fromisoformat, default=None,
                     help="Day to simulate (default: this week's Monday, so the weekly recap is included)")
    day.add_argument("--users", type=int, default=8, help="Members active during the day")
    day.add_argument("--sessions-per-user", type=int, default=3)
    day.add_argument("--autosave-saves", type=int, default=4, help="Draft saves per session of the main member")
    day.add_argument("--hourly-weights", default=None,
                     help="24 comma-separated relative weights for session start hours (server time)")
    day.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    baseline = None
    if args.compare:
        with open(args.compare) as f:
            baseline = json.load(f)

    with harness(args.database_url) as h:
        if args.day:
            weights = DEFAULT_HOURLY_WEIGHTS
            if args.hourly_weights:
                weights = tuple(float(w) for w in args.hourly_weights.split(","))
                if len(weights) != 24:
                    raise SystemExit("--hourly-weights needs exactly 24 values")
            today = datetime.now(ZoneInfo(SERVER_TZ)).date()
            report = simulate_day(
                h, day=args.day_date or today - timedelta(days=today.weekday()),
                users=args.users, sessions_per_user=args.sessions_per_user, weights=weights,
                autosave_saves=args.autosave_saves, seed=args.seed,
            )
            print_day(report, baseline)
        else:
            report = run_scenarios(h, args.repeat, args.tls_overhead_bytes)
            print_report(report, baseline)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
