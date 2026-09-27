"""Report duplicate (group_id, user_id) rows in group_members.

STRICTLY READ-ONLY — this script issues SELECTs only and never commits.

Run this BEFORE applying the migration that adds the unique constraint on
group_members, so you know exactly what the de-dupe is about to collapse.

Run from the backend/ directory:
    python scripts/check_member_dupes.py
    python scripts/check_member_dupes.py --group-id 42
    python scripts/check_member_dupes.py --verbose
"""

import argparse
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.group import Group, GroupRole, group_members  # noqa: E402
from app.models.user import User  # noqa: E402

# Lower rank == higher privilege. Mirrors GroupRole's declaration order in
# app/models/group.py, which require_permission reads as "role > min_role means
# insufficient". The migration's de-dupe keeps the MIN rank for this reason.
ROLE_RANK = {role.value: index for index, role in enumerate(GroupRole)}


def _rank(role: str | None) -> int:
    """Rank a raw role string; unknown/NULL sorts below every real role."""
    return ROLE_RANK.get(role, len(ROLE_RANK))


def _best_role(roles: list[str | None]) -> str | None:
    return min(roles, key=_rank)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report duplicate group_members rows (read-only)"
    )
    parser.add_argument(
        "--group-id", type=int, default=None, help="Restrict the scan to one group"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="List every duplicate row, not just the conflicting ones",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        total_rows = db.execute(
            select(func.count()).select_from(group_members)
        ).scalar_one()

        # Rows with a NULL key are reported but never counted as duplicates:
        # NULLs are not equal to each other under a unique constraint, so the
        # migration leaves them entirely alone. Counting them here would
        # over-report and misrepresent what the migration is about to delete.
        null_key_rows = db.execute(
            select(func.count())
            .select_from(group_members)
            .where(
                (group_members.c.group_id.is_(None))
                | (group_members.c.user_id.is_(None))
            )
        ).scalar_one()

        # Find the (group_id, user_id) pairs that appear more than once.
        dupe_stmt = (
            select(
                group_members.c.group_id,
                group_members.c.user_id,
                func.count().label("row_count"),
            )
            .where(
                group_members.c.group_id.is_not(None),
                group_members.c.user_id.is_not(None),
            )
            .group_by(group_members.c.group_id, group_members.c.user_id)
            .having(func.count() > 1)
            .order_by(group_members.c.group_id, group_members.c.user_id)
        )
        if args.group_id is not None:
            dupe_stmt = dupe_stmt.where(group_members.c.group_id == args.group_id)

        dupes = db.execute(dupe_stmt).all()

        scope = f" (group {args.group_id})" if args.group_id is not None else ""
        print()
        print("=" * 72)
        print(f"group_members duplicate report{scope}")
        print("=" * 72)
        print(f"  Total membership rows: {total_rows}")
        if null_key_rows:
            print(
                f"  Rows with a NULL group_id/user_id: {null_key_rows} "
                "(left untouched by the migration)"
            )

        if not dupes:
            print("  Duplicate (group_id, user_id) pairs: 0")
            print()
            print("  No duplicates. The migration's de-dupe step will be a no-op and")
            print("  the unique constraint will apply cleanly.")
            print()
            return

        surplus = sum(row.row_count - 1 for row in dupes)
        print(f"  Duplicate (group_id, user_id) pairs: {len(dupes)}")
        print(f"  Surplus rows the de-dupe would delete: {surplus}")
        print()

        role_conflicts = 0
        read_marker_conflicts = 0

        for pair in dupes:
            rows = db.execute(
                select(
                    group_members.c.role,
                    group_members.c.joined_at,
                    group_members.c.last_read_message_id,
                )
                .where(
                    group_members.c.group_id == pair.group_id,
                    group_members.c.user_id == pair.user_id,
                )
                .order_by(group_members.c.joined_at)
            ).all()

            group = db.get(Group, pair.group_id) if pair.group_id is not None else None
            user = db.get(User, pair.user_id) if pair.user_id is not None else None
            group_label = f"{group.name!r}" if group else "[missing group]"
            user_label = user.username if user else "[missing user]"

            roles = [r.role for r in rows]
            markers = [r.last_read_message_id for r in rows]
            joined = [r.joined_at for r in rows]

            role_disagrees = len(set(roles)) > 1
            marker_disagrees = len(set(markers)) > 1
            if role_disagrees:
                role_conflicts += 1
            if marker_disagrees:
                read_marker_conflicts += 1

            flags = []
            if role_disagrees:
                flags.append("ROLE CONFLICT")
            if marker_disagrees:
                flags.append("READ-MARKER CONFLICT")
            flag_text = f"  <-- {', '.join(flags)}" if flags else ""

            print(
                f"  group {pair.group_id} {group_label} / "
                f"user {pair.user_id} ({user_label}): "
                f"{pair.row_count} rows{flag_text}"
            )

            if role_disagrees or marker_disagrees or args.verbose:
                for row in rows:
                    joined_text = (
                        row.joined_at.isoformat() if row.joined_at else "unknown"
                    )
                    print(
                        f"      role={row.role!r:<10} "
                        f"joined_at={joined_text:<32} "
                        f"last_read_message_id={row.last_read_message_id}"
                    )
                survivor_role = _best_role(roles)
                survivor_marker = max((m for m in markers if m is not None), default=None)
                survivor_joined = min((j for j in joined if j is not None), default=None)
                survivor_joined_text = (
                    survivor_joined.isoformat() if survivor_joined else "unknown"
                )
                print(
                    f"      -> de-dupe keeps: role={survivor_role!r} "
                    f"joined_at={survivor_joined_text} "
                    f"last_read_message_id={survivor_marker}"
                )

        print()
        print("-" * 72)
        print("Summary")
        print("-" * 72)
        print(f"  Duplicate pairs .................. {len(dupes)}")
        print(f"  Surplus rows to be deleted ....... {surplus}")
        print(f"  Pairs disagreeing on role ........ {role_conflicts}")
        print(f"  Pairs disagreeing on read marker . {read_marker_conflicts}")
        print()
        if role_conflicts:
            print(
                "  Role conflicts found. The migration keeps the HIGHEST role "
                "(owner > admin > member),"
            )
            print("  so no member is demoted. Review the rows above to confirm.")
        if read_marker_conflicts:
            print(
                "  Read-marker conflicts found. The migration keeps the MAX "
                "last_read_message_id,"
            )
            print("  so no already-read chat backlog is resurrected as unread.")
        if not role_conflicts and not read_marker_conflicts:
            print("  Duplicates are identical apart from row identity — a clean collapse.")
        print()
    finally:
        # Explicit rollback: this script must never leave a write behind, even
        # from an implicitly opened transaction.
        db.rollback()
        db.close()


if __name__ == "__main__":
    main()
