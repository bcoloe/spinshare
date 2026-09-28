"""Seed a throwaway local database with a realistic, deterministic dataset for profiling.

Pairs with scripts/profile_db.py. The dataset is shaped like production — a handful
of groups, a long selected-album history, and many reviews with real-length
comments — because the costs being measured (rows and bytes shipped from Postgres)
scale with exactly those things. Same --seed, same data, so before/after runs of the
profiler compare like with like.

The schema is built with Base.metadata.create_all, the same way the test suite
builds its database; this database is disposable and never migrated.

Run from the backend/ directory:
    .venv/bin/python scripts/seed_profile_data.py --reset
    .venv/bin/python scripts/seed_profile_data.py --reset --albums 1200 --users 30
"""

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, ".")

from sqlalchemy import create_engine, insert, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/spinshare_profile"

# Not a real bcrypt hash — profiling never logs in (tokens are minted directly).
_DUMMY_PASSWORD_HASH = "$2b$12$profileprofileprofileprofileprofileprofileprofileprof"

_WORDS = (
    "warm fuzzy guitars drift over a steady motorik pulse while the vocals sit low and "
    "hazy in the mix the second half opens up with brass and a restless bassline that "
    "never quite resolves production is dense but rewarding on repeat listens standout "
    "tracks carry the record though the middle stretch sags a little lyrics lean wistful "
    "and nostalgic without tipping into cliche drums are crisp and upfront synths shimmer"
).split()


def _comment(rng: random.Random) -> str | None:
    """A review comment with a production-like length distribution (some empty)."""
    if rng.random() < 0.2:
        return None
    n_words = int(rng.triangular(10, 250, 60))
    return " ".join(rng.choice(_WORDS) for _ in range(n_words)).capitalize() + "."


def _ensure_database(url: str, reset: bool) -> None:
    """Create (or recreate with --reset) the target database via the server's postgres DB."""
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        ).scalar()
        if exists and reset:
            conn.execute(text(f'DROP DATABASE "{target.database}" WITH (FORCE)'))
            exists = False
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


def seed(url: str, *, users: int, groups: int, albums: int, selected_frac: float,
         review_rate: float, seed_value: int) -> dict:
    from app.database import Base
    from app.models import Album, Group, GroupAlbum, GroupSettings, Review, User, group_members

    rng = random.Random(seed_value)
    engine = create_engine(url)
    Base.metadata.create_all(bind=engine)
    now = datetime.now(UTC)

    with Session(engine) as db:
        if db.query(User).first() is not None:
            raise SystemExit("Database is not empty — rerun with --reset.")

        user_rows = [
            User(
                email=f"profile{i}@example.com",
                username=f"profile{i}",
                first_name=f"First{i}",
                last_name=f"Last{i}",
                password_hash=_DUMMY_PASSWORD_HASH,
            )
            for i in range(users)
        ]
        db.add_all(user_rows)
        db.flush()

        # Every user is in the global group; regular groups draw overlapping memberships
        # so the same album is reviewed from several groups, as in production.
        global_group = Group(name="Global", is_public=True, is_global=True, created_by=user_rows[0].id)
        regular = [
            Group(name=f"Profile Group {g}", is_public=False, created_by=user_rows[g % users].id)
            for g in range(groups)
        ]
        db.add_all([global_group, *regular])
        db.flush()
        db.add_all([GroupSettings(group_id=g.id) for g in [global_group, *regular]])

        memberships: dict[int, list[int]] = {global_group.id: [u.id for u in user_rows]}
        for g in regular:
            size = max(3, int(users * rng.uniform(0.4, 0.8)))
            memberships[g.id] = sorted(rng.sample([u.id for u in user_rows], size))
        db.execute(
            insert(group_members),
            [
                {"group_id": gid, "user_id": uid, "role": "owner" if i == 0 else "member"}
                for gid, uids in memberships.items()
                for i, uid in enumerate(uids)
            ],
        )

        # Wikipedia checked "just now" so album reads never reach out to Wikipedia.
        album_rows = [
            Album(
                spotify_album_id=f"profile{a:06d}",
                title=f"Profile Album {a}",
                artist=f"Profile Artist {a % 400}",
                release_date=f"{rng.randint(1965, 2025)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
                cover_url=f"https://i.scdn.co/image/profile{a:06d}",
                youtube_music_id=f"MPREb_profile{a:06d}",
                wikipedia_checked_at=now,
            )
            for a in range(albums)
        ]
        db.add_all(album_rows)
        db.flush()

        # Split the album catalog across the regular groups; a slice is co-nominated.
        group_album_rows: list[GroupAlbum] = []
        selected_by_group: dict[int, list[int]] = {}
        for album in album_rows:
            owners = rng.sample(regular, 2 if rng.random() < 0.15 else 1)
            for g in owners:
                nominator = rng.choice(memberships[g.id])
                is_selected = rng.random() < selected_frac
                selected_date = now - timedelta(days=rng.randint(1, 365)) if is_selected else None
                group_album_rows.append(
                    GroupAlbum(
                        group_id=g.id,
                        album_id=album.id,
                        added_by=nominator,
                        selected_date=selected_date,
                        added_at=now - timedelta(days=rng.randint(366, 500)),
                    )
                )
                if is_selected:
                    selected_by_group.setdefault(g.id, []).append(album.id)
        db.add_all(group_album_rows)
        db.flush()

        # Members review most of their group's selected albums.
        reviewed: set[tuple[int, int]] = set()
        review_rows: list[Review] = []
        for gid, album_ids in selected_by_group.items():
            for album_id in album_ids:
                for uid in memberships[gid]:
                    if (uid, album_id) in reviewed or rng.random() > review_rate:
                        continue
                    reviewed.add((uid, album_id))
                    review_rows.append(
                        Review(
                            album_id=album_id,
                            user_id=uid,
                            rating=round(rng.uniform(2, 10), 1),
                            comment=_comment(rng),
                            is_draft=False,
                        )
                    )
        db.add_all(review_rows)
        db.flush()

        # Fill the cached per-group averages the way ReviewService maintains them.
        ratings_by_album: dict[int, list[tuple[int, float]]] = {}
        for r in review_rows:
            ratings_by_album.setdefault(r.album_id, []).append((r.user_id, r.rating))
        for ga in group_album_rows:
            members = set(memberships[ga.group_id])
            ratings = [rt for uid, rt in ratings_by_album.get(ga.album_id, []) if uid in members]
            ga.avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
            ga.review_count = len(ratings)

        db.commit()
        summary = {
            "users": len(user_rows),
            "groups": len(regular) + 1,
            "albums": len(album_rows),
            "group_albums": len(group_album_rows),
            "selected": sum(len(v) for v in selected_by_group.values()),
            "reviews": len(review_rows),
        }
    engine.dispose()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a local profiling database")
    parser.add_argument("--database-url", default=DEFAULT_URL)
    parser.add_argument("--reset", action="store_true", help="Drop and recreate the database first")
    parser.add_argument("--users", type=int, default=15)
    parser.add_argument("--groups", type=int, default=3, help="Regular groups (plus one global)")
    parser.add_argument("--albums", type=int, default=600)
    parser.add_argument("--selected-frac", type=float, default=0.65)
    parser.add_argument("--review-rate", type=float, default=0.75,
                        help="Chance a member reviews a selected album in their group")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    _ensure_database(args.database_url, args.reset)
    summary = seed(
        args.database_url,
        users=args.users,
        groups=args.groups,
        albums=args.albums,
        selected_frac=args.selected_frac,
        review_rate=args.review_rate,
        seed_value=args.seed,
    )
    print("Seeded:", ", ".join(f"{k}={v}" for k, v in summary.items()))


if __name__ == "__main__":
    main()
