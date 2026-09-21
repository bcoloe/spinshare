"""Concurrency stress simulation for the race-prone service paths.

Not a unit test. Each worker runs on its OWN Session over its OWN connection
against a real Postgres database with the real migration applied, so the
interleavings are genuine rather than simulated by patching. The engine mirrors
production: NullPool, so every worker round-trips like it would on Neon.

Every scenario targets a specific fix and asserts the invariant that fix exists
to protect. Validated as load-bearing: run against the pre-hardening revision
(SIM_BACKEND=<old checkout>, against a database migrated only to 5c83c0dda2cb)
only 6 of 13 invariants hold -- 16 duplicate memberships, UniqueViolations out
of genre creation and the credit ledger, 9 credits lost to overwriting, and an
invitation accepted 10 times.

Usage:
    createdb spinshare_sim
    DATABASE_URL=postgresql://.../spinshare_sim alembic upgrade head
    SIM_DATABASE_URL=postgresql://.../spinshare_sim python scripts/stress_sim.py

WARNING: TRUNCATEs every table between scenarios. Point it only at a throwaway
database -- never at development or production.
"""

import argparse
import os
import random
import sys
import threading
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

# Default to the backend this script lives in; SIM_BACKEND can point at another
# checkout to run the same invariants against a different revision.
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.environ.get("SIM_BACKEND", _HERE))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

DB_URL = os.environ["SIM_DATABASE_URL"]
os.environ["DATABASE_URL"] = DB_URL

from app.models import (  # noqa: E402
    Album,
    Group,
    GroupAlbum,
    GroupInvitation,
    GroupParticipation,
    GroupSettings,
    PriorityReviewCredit,
    Review,
    User,
)
from app.models.genre import Genre  # noqa: E402
from app.models.group import GroupRole, group_members  # noqa: E402
from app.schemas.album import AlbumCreate  # noqa: E402
from app.services.album_service import AlbumService  # noqa: E402
from app.services.group_service import GroupService  # noqa: E402
from app.services.invitation_service import InvitationService  # noqa: E402
from app.services.participation_service import ParticipationService  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

engine = create_engine(DB_URL, poolclass=NullPool)
Session = sessionmaker(bind=engine)

_print_lock = threading.Lock()
RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    with _print_lock:
        RESULTS.append((name, ok, detail))
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


def run_workers(fn, n):
    """Run fn(i) on n threads released as close to simultaneously as possible."""
    barrier = threading.Barrier(n)
    out = []

    def wrapped(i):
        barrier.wait()  # maximise overlap
        try:
            return ("ok", fn(i))
        except HTTPException as exc:
            return ("http", exc.status_code)
        except Exception as exc:  # noqa: BLE001
            return ("exc", f"{type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = [pool.submit(wrapped, i) for i in range(n)]
        for f in as_completed(futures):
            out.append(f.result())
    return out


def reset():
    """Truncate everything between scenarios."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE users, groups, group_members, albums, group_albums, genres, "
                "album_genres, reviews, group_settings, group_participation, "
                "priority_review_credits, group_invitations, group_invite_links, "
                "notifications, album_deals, nomination_guesses, messages, "
                "message_mentions, spotify_connections RESTART IDENTITY CASCADE"
            )
        )


def seed_users(n, prefix="u"):
    db = Session()
    ids = []
    pw = hash_password("a-Fine-Password123!")
    for i in range(n):
        u = User(
            email=f"{prefix}{i}@sim.test", username=f"{prefix}{i}", password_hash=pw
        )
        db.add(u)
        db.flush()
        ids.append(u.id)
    db.commit()
    db.close()
    return ids


def seed_group(owner_id, name="Sim Group", **settings_kw):
    db = Session()
    g = Group(name=name, created_by=owner_id, is_public=True)
    db.add(g)
    db.flush()
    db.execute(
        group_members.insert().values(
            group_id=g.id, user_id=owner_id, role=GroupRole.Owner.value
        )
    )
    s = GroupSettings(group_id=g.id, **settings_kw)
    db.add(s)
    db.commit()
    gid = g.id
    db.close()
    return gid


def seed_album(title="Sim Album", spotify_id=None):
    db = Session()
    a = Album(
        title=title, artist="Sim Artist", spotify_album_id=spotify_id or f"sp-{title}"
    )
    db.add(a)
    db.commit()
    aid = a.id
    db.close()
    return aid


# ---------------------------------------------------------------- scenarios


def scenario_concurrent_join(workers=16):
    """N threads join the same group at once -> exactly one membership row.

    Guards the group_members unique constraint and add_user's (previously dead)
    IntegrityError handler.
    """
    reset()
    owner, joiner = seed_users(2, "j")
    gid = seed_group(owner)

    def work(_i):
        db = Session()
        try:
            return GroupService(db).add_user(gid, joiner)
        finally:
            db.close()

    outcomes = run_workers(work, workers)
    db = Session()
    rows = db.execute(
        select(func.count()).select_from(group_members).where(
            group_members.c.group_id == gid, group_members.c.user_id == joiner
        )
    ).scalar()
    db.close()

    kinds = Counter(k for k, _ in outcomes)
    unexpected = [v for k, v in outcomes if k == "exc"]
    record(
        "concurrent join -> exactly one membership row",
        rows == 1,
        f"rows={rows} outcomes={dict(kinds)}",
    )
    record(
        "concurrent join -> no unhandled exception",
        not unexpected,
        f"{unexpected[:2]}" if unexpected else "",
    )


def scenario_concurrent_genre(workers=12):
    """N threads create albums sharing a brand-new genre -> no 500."""
    reset()
    genre_names = ["shoegaze-sim", "slowcore-sim", "post-rock-sim"]

    def work(i):
        db = Session()
        try:
            return AlbumService(db).get_or_create_album(
                AlbumCreate(
                    spotify_album_id=f"sp-genre-{i}",
                    title=f"Genre Race {i}",
                    artist="Sim",
                    genres=genre_names,
                )
            ).id
        finally:
            db.close()

    outcomes = run_workers(work, workers)
    errs = [v for k, v in outcomes if k != "ok"]
    db = Session()
    dupes = db.execute(
        select(Genre.name, func.count())
        .where(Genre.name.in_(genre_names))
        .group_by(Genre.name)
        .having(func.count() > 1)
    ).all()
    made = db.execute(
        select(func.count()).select_from(Genre).where(Genre.name.in_(genre_names))
    ).scalar()
    db.close()

    record("concurrent genre create -> no errors", not errs, f"{errs[:2]}" if errs else "")
    record(
        "concurrent genre create -> no duplicate genre rows",
        not dupes and made == len(genre_names),
        f"distinct={made} dupes={dupes}",
    )


def scenario_credit_ledger(workers=12):
    """N threads credit the same member for DIFFERENT albums simultaneously.

    Every grant must land: this is the lost-update guard. With the old
    Python read-modify-write, concurrent grants overwrite each other.
    """
    reset()
    owner, member = seed_users(2, "c")
    gid = seed_group(owner, priority_pick_threshold=3)
    db = Session()
    GroupService(db).add_user(gid, member)
    db.close()

    album_ids = []
    for i in range(workers):
        aid = seed_album(f"Credit Album {i}", f"sp-credit-{i}")
        album_ids.append(aid)
        db = Session()
        ga = GroupAlbum(group_id=gid, album_id=aid, added_by=owner)
        db.add(ga)
        db.flush()
        ga.selected_date = func.now()
        db.commit()
        db.close()

    def work(i):
        db = Session()
        try:
            ParticipationService(db)._grant_credit(gid, member, album_ids[i], commit=True)
        finally:
            db.close()

    outcomes = run_workers(work, workers)
    errs = [v for k, v in outcomes if k != "ok"]

    db = Session()
    balance = db.execute(
        select(GroupParticipation.credits).where(
            GroupParticipation.group_id == gid, GroupParticipation.user_id == member
        )
    ).scalar()
    ledger = db.execute(
        select(func.count()).select_from(PriorityReviewCredit).where(
            PriorityReviewCredit.group_id == gid, PriorityReviewCredit.user_id == member
        )
    ).scalar()
    participations = db.execute(
        select(func.count()).select_from(GroupParticipation).where(
            GroupParticipation.group_id == gid, GroupParticipation.user_id == member
        )
    ).scalar()
    db.close()

    record("credit ledger -> no errors", not errs, f"{errs[:2]}" if errs else "")
    record(
        "credit ledger -> no lost update (balance == ledger rows)",
        balance == ledger == workers,
        f"balance={balance} ledger={ledger} expected={workers}",
    )
    record(
        "credit ledger -> exactly one participation row",
        participations == 1,
        f"rows={participations}",
    )


def scenario_duplicate_credit(workers=10):
    """N threads credit the SAME (group,user,album) -> exactly one credit."""
    reset()
    owner, member = seed_users(2, "d")
    gid = seed_group(owner, priority_pick_threshold=3)
    db = Session()
    GroupService(db).add_user(gid, member)
    db.close()
    aid = seed_album("Dup Credit", "sp-dupcredit")
    db = Session()
    ga = GroupAlbum(group_id=gid, album_id=aid, added_by=owner)
    db.add(ga)
    db.flush()
    ga.selected_date = func.now()
    db.commit()
    db.close()

    def work(_i):
        db = Session()
        try:
            ParticipationService(db)._grant_credit(gid, member, aid, commit=True)
        finally:
            db.close()

    outcomes = run_workers(work, workers)
    errs = [v for k, v in outcomes if k != "ok"]
    db = Session()
    balance = db.execute(
        select(GroupParticipation.credits).where(
            GroupParticipation.group_id == gid, GroupParticipation.user_id == member
        )
    ).scalar()
    db.close()
    record("duplicate credit -> no errors", not errs, f"{errs[:2]}" if errs else "")
    record(
        "duplicate credit -> idempotent (balance == 1)",
        balance == 1,
        f"balance={balance}",
    )


def scenario_invitation_accept(workers=10):
    """N threads accept the same invitation token -> exactly one wins."""
    reset()
    owner = seed_users(1, "io")[0]
    gid = seed_group(owner)
    db = Session()
    invitee = User(
        email="invitee@sim.test",
        username="invitee",
        password_hash=hash_password("a-Fine-Password123!"),
    )
    db.add(invitee)
    db.flush()
    from datetime import datetime, timedelta, timezone

    inv = GroupInvitation(
        group_id=gid,
        invited_email="invitee@sim.test",
        invited_by=owner,
        token="sim-token-race",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(inv)
    db.commit()
    invitee_id = invitee.id
    db.close()

    def work(_i):
        db = Session()
        try:
            user = db.get(User, invitee_id)
            return InvitationService(db).accept_invitation(
                "sim-token-race", user, GroupService(db)
            ).id
        finally:
            db.close()

    outcomes = run_workers(work, workers)
    accepted = sum(1 for k, _ in outcomes if k == "ok")
    gone = sum(1 for k, v in outcomes if k == "http" and v == 410)
    other = [v for k, v in outcomes if k == "exc"]

    db = Session()
    rows = db.execute(
        select(func.count()).select_from(group_members).where(
            group_members.c.group_id == gid, group_members.c.user_id == invitee_id
        )
    ).scalar()
    db.close()

    record(
        "invitation accept -> exactly one acceptance",
        accepted == 1 and gone == workers - 1,
        f"accepted={accepted} gone410={gone} other={other[:2]}",
    )
    record(
        "invitation accept -> exactly one membership row", rows == 1, f"rows={rows}"
    )


def scenario_mixed_load(seconds_ops=240):
    """Randomised mixed workload -- the regression sweep.

    Many users, groups, nominations, reviews and reads interleaved on separate
    connections. Asserts no unhandled exception and no 5xx-class HTTPException
    escapes from any path.
    """
    reset()
    users = seed_users(8, "m")
    gids = [seed_group(users[0], f"Mixed {i}", priority_pick_threshold=2) for i in range(3)]
    db = Session()
    gs = GroupService(db)
    for gid in gids:
        for u in users[1:]:
            gs.add_user(gid, u)
    db.close()
    albums = [seed_album(f"Mixed Album {i}", f"sp-mixed-{i}") for i in range(12)]

    def work(i):
        rnd = random.Random(i)
        db = Session()
        try:
            for _ in range(6):
                gid = rnd.choice(gids)
                uid = rnd.choice(users)
                aid = rnd.choice(albums)
                op = rnd.randrange(6)
                if op == 0:
                    AlbumService(db).nominate_album(gid, aid, db.get(User, uid))
                elif op == 1:
                    GroupService(db).get_group_stats(gid)
                elif op == 2:
                    GroupService(db).search_groups(query="Mixed", limit=10)
                elif op == 3:
                    ParticipationService(db).get_progress(gid, uid)
                elif op == 4:
                    AlbumService(db).get_group_albums(gid)
                else:
                    GroupService(db).get_group_members(gid)
        finally:
            db.close()

    outcomes = run_workers(work, 16)
    hard = [v for k, v in outcomes if k == "exc"]
    server_err = [v for k, v in outcomes if k == "http" and int(v) >= 500]
    # 4xx are legitimate business outcomes here (duplicate nomination, limits).
    record("mixed load -> no unhandled exceptions", not hard, f"{hard[:3]}" if hard else "")
    record(
        "mixed load -> no 5xx escaped", not server_err, f"{server_err[:3]}" if server_err else ""
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    scenarios = {
        "join": scenario_concurrent_join,
        "genre": scenario_concurrent_genre,
        "credit": scenario_credit_ledger,
        "dupcredit": scenario_duplicate_credit,
        "invite": scenario_invitation_accept,
        "mixed": scenario_mixed_load,
    }
    for name, fn in scenarios.items():
        if args.only and args.only != name:
            continue
        print(f"\n== {name} ==", flush=True)
        try:
            fn()
        except Exception:  # noqa: BLE001
            record(f"{name} (harness)", False, traceback.format_exc().splitlines()[-1])

    print("\n" + "=" * 62)
    failed = [r for r in RESULTS if not r[1]]
    print(f"  {len(RESULTS) - len(failed)}/{len(RESULTS)} invariants held")
    for name, _, detail in failed:
        print(f"  FAILED: {name} -- {detail}")
    print("=" * 62)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
