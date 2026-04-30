"""Add global group (spinshare) with is_global and allow_guessing flags

Revision ID: b7d2e4f1a903
Revises: 49fe1734ee79
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2e4f1a903"
down_revision: Union[str, Sequence[str], None] = ("49fe1734ee79", "a3f5c7d2e890")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("groups", sa.Column("is_global", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("group_settings", sa.Column("allow_guessing", sa.Boolean(), nullable=False, server_default="true"))

    conn = op.get_bind()

    result = conn.execute(
        sa.text(
            "INSERT INTO groups (name, is_public, is_global, created_by) "
            "VALUES ('spinshare', true, true, null) RETURNING id"
        )
    )
    global_group_id = result.scalar()

    conn.execute(
        sa.text(
            "INSERT INTO group_settings (group_id, allow_guessing) VALUES (:gid, false)"
        ),
        {"gid": global_group_id},
    )

    conn.execute(
        sa.text(
            "INSERT INTO group_members (group_id, user_id, role) "
            "SELECT :gid, id, 'member' FROM users"
        ),
        {"gid": global_group_id},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM groups WHERE is_global = true"))

    op.drop_column("group_settings", "allow_guessing")
    op.drop_column("groups", "is_global")
