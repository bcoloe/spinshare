"""add group_members unique constraint and hot-path indexes

Revision ID: 40b659edcbad
Revises: 5c83c0dda2cb
Create Date: 2026-09-17 11:13:48.386005

This migration does two things.

1. De-duplicates ``group_members`` and gives it the unique constraint it never
   had. The table shipped as two bare FK columns: no primary key, no unique
   constraint, no index. ``GroupService.add_user`` does a check-then-act and its
   ``except IntegrityError`` branch has therefore been dead code — there was no
   constraint to violate. A double-clicked Join, or an invite accepted in two
   tabs, inserts a second membership row, which then double-counts unread chat
   (``message_service.unread_counts`` joins this table), inflates member_count,
   duplicates notification fan-out, and makes ``get_user_role``'s ``.scalar()``
   return an arbitrary one of the two roles.

2. Adds indexes for columns that are filtered on hot paths but are not the
   LEADING column of any existing composite constraint, and so today cost a
   sequential scan on every request.

The de-dupe deliberately does NOT just keep the physically-first row. See
``_dedupe_group_members`` for how the survivor is chosen and why.

NOTE: index creation here is non-concurrent, matching the rest of this project's
migrations, so the whole migration is one transaction and the de-dupe cannot be
left half-applied without its constraint. These tables are small; the brief
ACCESS EXCLUSIVE lock is the cheaper trade against a torn migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40b659edcbad'
down_revision: Union[str, Sequence[str], None] = '5c83c0dda2cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Lower rank == higher privilege, mirroring the declaration order of GroupRole in
# app/models/group.py (owner, admin, member), which require_permission reads as
# "role > min_role means insufficient". Anything unrecognised or NULL sorts last
# so a junk role never wins over a real one.
_ROLE_RANK_SQL = """
    CASE role
        WHEN 'owner' THEN 0
        WHEN 'admin' THEN 1
        WHEN 'member' THEN 2
        ELSE 3
    END
"""

_RANK_TO_ROLE_SQL = """
    CASE m.best_rank
        WHEN 0 THEN 'owner'
        WHEN 1 THEN 'admin'
        WHEN 2 THEN 'member'
        ELSE gm.role
    END
"""

# Indexes added purely for read performance, as (table, column, index name).
# Each of these columns is filtered on a hot path but is not the leading column
# of any existing constraint, so it is unusable without its own index:
#   reviews.album_id           - unique_user_album_review is user_id-leading
#   album_genres.*             - bare association table, zero indexes
#   group_albums.album_id      - unique_user_album_per_group is group_id-leading
#   group_albums.added_by      - ditto
#   group_albums.selected_date - the selected_date IS NULL nomination pool scan
#   group_invitations.invited_email - get_user_pending_invitations lookup
_PERF_INDEXES = [
    ("reviews", "album_id", "ix_reviews_album_id"),
    ("album_genres", "album_id", "ix_album_genres_album_id"),
    ("album_genres", "genre_id", "ix_album_genres_genre_id"),
    ("group_albums", "album_id", "ix_group_albums_album_id"),
    ("group_albums", "added_by", "ix_group_albums_added_by"),
    ("group_albums", "selected_date", "ix_group_albums_selected_date"),
    ("group_invitations", "invited_email", "ix_group_invitations_invited_email"),
]

_MEMBER_UNIQUE = "uq_group_members_group_user"
_MEMBER_USER_INDEX = "ix_group_members_user_id"


def _dedupe_group_members() -> None:
    """Collapse duplicate (group_id, user_id) rows to exactly one.

    Choosing the survivor is the whole risk of this migration. Keeping the
    physically-first row (lowest ctid) would be wrong in two ways that both
    cause real damage:

      * it could keep a 'member' row over an 'owner' row and silently demote a
        group owner, which is unrecoverable without manual intervention; and
      * it could keep a stale last_read_message_id and resurrect an entire
        already-read chat backlog as unread.

    So the survivor is built, not merely picked. Within each duplicated
    (group_id, user_id):

      * role                 <- the HIGHEST role present (min rank)
      * last_read_message_id <- the MAX present (furthest read wins)
      * joined_at            <- the MIN present (the real join date)

    The physical row kept is the one already ranked best on (role, joined_at,
    ctid); the aggregate values are then merged onto it, so the surviving row
    holds the best of every field regardless of which physical row carried it.

    Rows with a NULL group_id or user_id are left completely alone: the columns
    are nullable, NULLs are not equal to each other under a unique constraint,
    and grouping them would delete rows that were never duplicates.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        row_id = "ctid"
        # Postgres sorts NULLs last on ASC already, but say it explicitly so an
        # unknown joined_at never wins the tiebreak.
        joined_order = "joined_at ASC NULLS LAST"
    elif dialect == "sqlite":
        # SQLite has no ctid; rowid is its equivalent physical row identity.
        row_id = "rowid"
        joined_order = "joined_at ASC"
    else:
        # Nothing else is supported or used by this project. Fail loudly rather
        # than adding a unique constraint over data that was never de-duped.
        raise RuntimeError(
            f"group_members de-dupe is not implemented for dialect {dialect!r}"
        )

    # 1. Snapshot the merged values BEFORE deleting anything, so values carried
    #    only by a losing row are not lost with it.
    bind.execute(sa.text(f"""
        CREATE TEMPORARY TABLE _gm_merge AS
        SELECT group_id,
               user_id,
               MIN({_ROLE_RANK_SQL}) AS best_rank,
               MAX(last_read_message_id) AS max_last_read,
               MIN(joined_at) AS min_joined_at
        FROM group_members
        WHERE group_id IS NOT NULL AND user_id IS NOT NULL
        GROUP BY group_id, user_id
        HAVING COUNT(*) > 1
    """))

    # 2. Delete every row but the best-ranked one in each duplicated pair.
    ranked = f"""
        SELECT {row_id} AS row_id,
               ROW_NUMBER() OVER (
                   PARTITION BY group_id, user_id
                   ORDER BY {_ROLE_RANK_SQL},
                            {joined_order},
                            {row_id}
               ) AS rn
        FROM group_members
        WHERE group_id IS NOT NULL AND user_id IS NOT NULL
    """
    if dialect == "postgresql":
        deleted = bind.execute(sa.text(f"""
            DELETE FROM group_members gm
            USING ({ranked}) ranked
            WHERE gm.ctid = ranked.row_id AND ranked.rn > 1
        """))
    else:
        deleted = bind.execute(sa.text(f"""
            DELETE FROM group_members
            WHERE rowid IN (
                SELECT row_id FROM ({ranked}) ranked WHERE ranked.rn > 1
            )
        """))

    # 3. Merge the preserved bests onto the survivor. Note this runs AFTER the
    #    delete: an UPDATE moves a row's ctid in Postgres, which would break the
    #    ctid-keyed delete above if the order were reversed.
    if dialect == "postgresql":
        bind.execute(sa.text(f"""
            UPDATE group_members gm
            SET role = {_RANK_TO_ROLE_SQL},
                last_read_message_id = m.max_last_read,
                joined_at = m.min_joined_at
            FROM _gm_merge m
            WHERE gm.group_id = m.group_id AND gm.user_id = m.user_id
        """))
    else:
        bind.execute(sa.text("""
            UPDATE group_members
            SET role = COALESCE(
                    (SELECT CASE m.best_rank
                                WHEN 0 THEN 'owner'
                                WHEN 1 THEN 'admin'
                                WHEN 2 THEN 'member'
                            END
                     FROM _gm_merge m
                     WHERE m.group_id = group_members.group_id
                       AND m.user_id = group_members.user_id),
                    role
                ),
                last_read_message_id = (
                    SELECT m.max_last_read FROM _gm_merge m
                    WHERE m.group_id = group_members.group_id
                      AND m.user_id = group_members.user_id
                ),
                joined_at = (
                    SELECT m.min_joined_at FROM _gm_merge m
                    WHERE m.group_id = group_members.group_id
                      AND m.user_id = group_members.user_id
                )
            WHERE EXISTS (
                SELECT 1 FROM _gm_merge m
                WHERE m.group_id = group_members.group_id
                  AND m.user_id = group_members.user_id
            )
        """))

    bind.execute(sa.text("DROP TABLE _gm_merge"))

    removed = deleted.rowcount if deleted.rowcount is not None else -1
    print(f"group_members de-dupe: removed {removed} duplicate membership row(s)")


def upgrade() -> None:
    """Upgrade schema."""
    _dedupe_group_members()

    op.create_unique_constraint(
        _MEMBER_UNIQUE, "group_members", ["group_id", "user_id"]
    )
    op.create_index(_MEMBER_USER_INDEX, "group_members", ["user_id"], unique=False)

    for table, column, name in _PERF_INDEXES:
        op.create_index(op.f(name), table, [column], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    Only the schema is reversed. The duplicate membership rows the upgrade
    removed are not (and should not be) restored — they were corruption.
    """
    for table, _column, name in reversed(_PERF_INDEXES):
        op.drop_index(op.f(name), table_name=table)

    op.drop_index(_MEMBER_USER_INDEX, table_name="group_members")
    op.drop_constraint(_MEMBER_UNIQUE, "group_members", type_="unique")
