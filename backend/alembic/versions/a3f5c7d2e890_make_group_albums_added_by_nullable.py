"""Make group_albums.added_by nullable to support account deletion

Revision ID: a3f5c7d2e890
Revises: fb1b022d98ef
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f5c7d2e890'
down_revision: Union[str, Sequence[str], None] = 'fb1b022d98ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('group_albums', 'added_by',
        existing_type=sa.Integer(),
        nullable=True)


def downgrade() -> None:
    op.alter_column('group_albums', 'added_by',
        existing_type=sa.Integer(),
        nullable=False)
