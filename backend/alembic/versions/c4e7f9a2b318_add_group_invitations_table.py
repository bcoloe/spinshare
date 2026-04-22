"""Add group_invitations table

Revision ID: c4e7f9a2b318
Revises: 03106b2e46fc
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e7f9a2b318"
down_revision: Union[str, Sequence[str], None] = "03106b2e46fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "group_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("invited_email", sa.String(), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_group_invitations_id"), "group_invitations", ["id"], unique=False)
    op.create_index(op.f("ix_group_invitations_group_id"), "group_invitations", ["group_id"], unique=False)
    op.create_index(op.f("ix_group_invitations_token"), "group_invitations", ["token"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_group_invitations_token"), table_name="group_invitations")
    op.drop_index(op.f("ix_group_invitations_group_id"), table_name="group_invitations")
    op.drop_index(op.f("ix_group_invitations_id"), table_name="group_invitations")
    op.drop_table("group_invitations")
