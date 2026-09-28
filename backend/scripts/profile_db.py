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

Workflow (run from the backend/ directory):
    .venv/bin/python scripts/seed_profile_data.py --reset
    .venv/bin/python scripts/profile_db.py --json baseline.json
    # ...make changes...
    .venv/bin/python scripts/profile_db.py --compare baseline.json

The scenarios mirror what the frontend fires; when a frontend change alters which
queries a page triggers (e.g. invalidation after autosave), update SCENARIOS to match.
"""

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from collections import defaultdict
from dataclasses import asdict, dataclass

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
# seeded data: {g} group, {a} reviewed album, {u} username, {d} draft album, {r} draft id.
GROUP_SHELL = [
    ("GET", "/notifications"),
    ("GET", "/invitations/pending"),
    ("GET", "/users/me/stats"),
    ("GET", "/groups/search?username={u}"),
]

SCENARIOS: dict[str, list] = {
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
    """Choose the busiest regular group, a member, a reviewed album, and a draft target."""
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
    member_ids = [
        row[0] for row in db.query(group_members.c.user_id).filter(group_members.c.group_id == gid)
    ]
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
            user = db.get(User, uid)
            return {"g": gid, "a": reviewed_album, "d": draft_album, "user": user}
    raise SystemExit("Every member has reviewed every album — reseed with a lower --review-rate.")


def run(url: str, repeat: int, tls_overhead: int) -> dict:
    target = make_url(url)
    relay = CountingRelay(target.host or "localhost", target.port or 5432)
    os.environ["DATABASE_URL"] = target.set(host="127.0.0.1", port=relay.port).render_as_string(
        hide_password=False
    )

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
    user = fixtures["user"]
    placeholders = {"g": fixtures["g"], "a": fixtures["a"], "d": fixtures["d"], "u": user.username}
    token = create_access_token({"sub": str(user.id)})
    db.close()

    results: dict[str, dict[str, Tally]] = defaultdict(dict)

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}

        def request(method: str, path: str, body=None):
            """Issue one request; return (Tally of its DB cost, response)."""
            relay.wait_idle()
            bytes_before, conns_before = relay.snapshot()
            stmts_before, rows_before = counter.statements, counter.rows
            resp = client.request(method, path, headers=headers, json=body)
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

        # The autosave scenario edits an existing draft, so create one up front.
        _, resp = request(
            "POST", f"/albums/{fixtures['d']}/reviews?group_id={fixtures['g']}",
            {"comment": "first thoughts", "is_draft": True},
        )
        if resp.status_code >= 400:
            raise SystemExit(f"Could not create the draft review: {resp.status_code} {resp.text}")
        placeholders["r"] = resp.json()["id"]

        try:
            for name, steps in SCENARIOS.items():
                for _ in range(repeat):
                    for step in steps:
                        method, template = step[0], step[1]
                        body = step[2] if len(step) > 2 else None
                        path = template.format(**placeholders)
                        tally, resp = request(method, path, body)
                        key = f"{method} {template}"
                        if resp.status_code >= 400:
                            print(f"  ! {name}: {method} {path} -> {resp.status_code}", file=sys.stderr)
                        results[name].setdefault(key, Tally()).add(tally)
        finally:
            db = SessionLocal()
            db.query(Review).filter(Review.id == placeholders["r"]).delete()
            db.commit()
            db.close()

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
    args = parser.parse_args()

    report = run(args.database_url, args.repeat, args.tls_overhead_bytes)
    baseline = None
    if args.compare:
        with open(args.compare) as f:
            baseline = json.load(f)
    print_report(report, baseline)
    if args.json:
        with open(args.json, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nWrote {args.json}")


if __name__ == "__main__":
    main()
