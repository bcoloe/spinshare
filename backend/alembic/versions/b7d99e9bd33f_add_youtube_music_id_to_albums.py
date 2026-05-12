"""Add youtube_music_id to albums

Revision ID: b7d99e9bd33f
Revises: 085acf4a4df0
Create Date: 2026-05-12 11:16:48.699504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d99e9bd33f'
down_revision: Union[str, Sequence[str], None] = '085acf4a4df0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('albums', sa.Column('youtube_music_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('albums', 'youtube_music_id')
