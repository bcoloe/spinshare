"""Add is_draft to reviews

Revision ID: a9f4b8c1d623
Revises: fb1b022d98ef
Create Date: 2026-05-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9f4b8c1d623"
down_revision: str | Sequence[str] | None = "b7d2e4f1a903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add is_draft column to reviews table."""
    op.add_column(
        "reviews",
        sa.Column("is_draft", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove is_draft column from reviews table."""
    op.drop_column("reviews", "is_draft")
