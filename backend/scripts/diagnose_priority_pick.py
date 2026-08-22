"""Diagnose a failing priority pick ("No pending nomination of yours matches that album").

Read-only. Dumps every group_albums row behind an album so you can compare what the
group listing offers the frontend (the canonical row, MIN(id) per album) against what
``ParticipationService.set_priority_pick`` accepts (a row with added_by = caller).

Run from the backend/ directory:
    python scripts/diagnose_priority_pick.py --album-title "Eat the Light"
    python scripts/diagnose_priority_pick.py --album-title "Eat the Light" --username someuser
"""

import argparse
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal  # noqa: E402
from app.models.album import Album  # noqa: E402
from app.models.group import Group  # noqa: E402
from app.models.group_settings import GroupSettings  # noqa: E402
from app.models.participation import GroupParticipation  # noqa: E402
from app.models.group_album import GroupAlbum  # noqa: E402
from app.models.user import User  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect nominations behind a priority pick failure")
    parser.add_argument("--album-title", required=True, help="Album title (case-insensitive substring)")
    parser.add_argument("--username", help="Reporting user; adds a verdict per group")
    parser.add_argument("--group-id", type=int, help="Restrict output to one group")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        albums = (
            db.query(Album)
            .filter(Album.title.ilike(f"%{args.album_title}%"))
            .order_by(Album.id)
            .all()
        )
        if not albums:
            print(f"No album matching {args.album_title!r}", file=sys.stderr)
            sys.exit(1)

        user = None
        if args.username:
            user = db.query(User).filter(User.username == args.username.lower()).first()
            if not user:
                print(f"No user named {args.username!r}", file=sys.stderr)
                sys.exit(1)
            print(f"Caller: {user.username} (id={user.id})")

        for album in albums:
            print(f"\nAlbum {album.id}: {album.title!r} by {album.artist}")

            q = db.query(GroupAlbum).filter(GroupAlbum.album_id == album.id)
            if args.group_id:
                q = q.filter(GroupAlbum.group_id == args.group_id)
            rows = q.order_by(GroupAlbum.group_id, GroupAlbum.id).all()
            if not rows:
                print("  (no nominations)")
                continue

            by_group: dict[int, list[GroupAlbum]] = {}
            for ga in rows:
                by_group.setdefault(ga.group_id, []).append(ga)

            for group_id, group_rows in by_group.items():
                group = db.query(Group).filter(Group.id == group_id).first()
                group_name = group.name if group else "[missing group]"
                # The listing collapses an album to its lowest-id row across ALL statuses.
                canonical_id = min(ga.id for ga in group_rows)
                settings = (
                    db.query(GroupSettings).filter(GroupSettings.group_id == group_id).first()
                )
                threshold = settings.priority_pick_threshold if settings else None
                disabled = (
                    settings is None
                    or settings.dealer_mode
                    or not settings.priority_pick_threshold
                    or bool(group and group.is_global)
                )
                state = "DISABLED" if disabled else f"threshold={threshold}"
                print(f"  Group {group_id} ({group_name!r}) — priority pick {state}")
                for ga in group_rows:
                    nominator = (
                        db.query(User).filter(User.id == ga.added_by).first()
                        if ga.added_by is not None
                        else None
                    )
                    who = f"{nominator.username} (id={nominator.id})" if nominator else "[deleted user]"
                    selected = ga.selected_date.isoformat() if ga.selected_date else "pending"
                    mark = " <- canonical (id sent by the UI)" if ga.id == canonical_id else ""
                    print(f"    group_album id={ga.id}  added_by={who}  selected_date={selected}{mark}")

                if user is None:
                    continue

                participation = (
                    db.query(GroupParticipation)
                    .filter(
                        GroupParticipation.group_id == group_id,
                        GroupParticipation.user_id == user.id,
                    )
                    .first()
                )
                print(
                    f"    caller credits={participation.credits if participation else 0}, "
                    f"queued pick={participation.priority_group_album_id if participation else None}"
                )

                mine = [ga for ga in group_rows if ga.added_by == user.id]
                pickable = [ga for ga in mine if ga.selected_date is None]
                if not mine:
                    print("    VERDICT: caller never nominated this album here — UI should not offer it")
                elif canonical_id not in {ga.id for ga in mine}:
                    print(
                        f"    VERDICT: UI sends id={canonical_id} (owned by another nominator); "
                        f"caller's own row(s) are {[ga.id for ga in mine]} -> backend 404"
                    )
                elif not pickable:
                    print("    VERDICT: caller's row is already selected -> backend 404")
                else:
                    print(f"    VERDICT: id={canonical_id} is the caller's pending row — pick should succeed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
