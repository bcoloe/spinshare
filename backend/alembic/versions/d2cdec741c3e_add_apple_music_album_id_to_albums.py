"""Add apple_music_album_id to albums

Revision ID: d2cdec741c3e
Revises: a9c3071562f0
Create Date: 2026-05-15 09:50:38.099205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2cdec741c3e'
down_revision: Union[str, Sequence[str], None] = 'a9c3071562f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('albums', sa.Column('apple_music_album_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_albums_apple_music_album_id'), 'albums', ['apple_music_album_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_albums_apple_music_album_id'), table_name='albums')
    op.drop_column('albums', 'apple_music_album_id')
