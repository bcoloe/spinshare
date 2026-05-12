"""Add avg_rating and review_count to group_albums

Revision ID: c7e4a9f12d83
Revises: fb1b022d98ef
Create Date: 2026-05-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c7e4a9f12d83'
down_revision: Union[str, Sequence[str], None] = 'b7d99e9bd33f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('group_albums', sa.Column('avg_rating', sa.Float(), nullable=True))
    op.add_column('group_albums', sa.Column('review_count', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('group_albums', 'review_count')
    op.drop_column('group_albums', 'avg_rating')
