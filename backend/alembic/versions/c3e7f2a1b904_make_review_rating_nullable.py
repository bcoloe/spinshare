"""Make review rating nullable for drafts

Revision ID: c3e7f2a1b904
Revises: a9f4b8c1d623
Create Date: 2026-05-01 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e7f2a1b904"
down_revision: str | Sequence[str] | None = "a9f4b8c1d623"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow rating to be NULL (drafts may be saved without a rating)."""
    op.alter_column("reviews", "rating", existing_type=sa.Float(), nullable=True)


def downgrade() -> None:
    """Restore rating as NOT NULL (set any NULLs to 0 first to avoid constraint failure)."""
    op.execute("UPDATE reviews SET rating = 0 WHERE rating IS NULL")
    op.alter_column("reviews", "rating", existing_type=sa.Float(), nullable=False)
