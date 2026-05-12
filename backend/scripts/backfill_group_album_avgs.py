"""Backfill avg_rating and review_count on group_albums.

Run once after deploying the c7e4a9f12d83 migration to populate cached averages
for all previously-selected albums. Safe to re-run (idempotent).

Usage:
    python scripts/backfill_group_album_avgs.py
"""

import os
import sys
from pathlib import Path

# Allow imports from the backend package when run from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import GroupAlbum, Review
from app.models.group import group_members


def backfill(session: Session) -> None:
    group_albums = list(
        session.scalars(
            select(GroupAlbum).where(GroupAlbum.selected_date.isnot(None))
        ).all()
    )

    print(f"Backfilling {len(group_albums)} selected group_album rows…")
    updated = 0

    for ga in group_albums:
        member_ids = list(
            session.scalars(
                select(group_members.c.user_id).where(group_members.c.group_id == ga.group_id)
            ).all()
        )
        ratings = (
            list(
                session.scalars(
                    select(Review.rating).where(
                        Review.album_id == ga.album_id,
                        Review.user_id.in_(member_ids),
                        Review.is_draft == False,  # noqa: E712
                        Review.rating.isnot(None),
                    )
                ).all()
            )
            if member_ids
            else []
        )

        new_avg = round(sum(ratings) / len(ratings), 2) if ratings else None
        new_count = len(ratings)

        if ga.avg_rating != new_avg or ga.review_count != new_count:
            ga.avg_rating = new_avg
            ga.review_count = new_count
            updated += 1

    session.commit()
    print(f"Done. {updated} rows updated, {len(group_albums) - updated} already correct.")


if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(database_url)
    with Session(engine) as session:
        backfill(session)
