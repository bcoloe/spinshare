"""Add group_settings table

Revision ID: a1b2c3d4e5f6
Revises: d8f3a1c2e947
Create Date: 2026-04-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "d8f3a1c2e947"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "group_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column(
            "min_role_to_add_members",
            sa.String(),
            nullable=False,
            server_default="admin",
        ),
        sa.Column("daily_album_count", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id"),
    )
    op.create_index(op.f("ix_group_settings_id"), "group_settings", ["id"], unique=False)

    # Backfill settings rows for existing groups with defaults.
    op.execute(
        "INSERT INTO group_settings (group_id, min_role_to_add_members, daily_album_count) "
        "SELECT id, 'admin', 1 FROM groups "
        "WHERE id NOT IN (SELECT group_id FROM group_settings)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_group_settings_id"), table_name="group_settings")
    op.drop_table("group_settings")
