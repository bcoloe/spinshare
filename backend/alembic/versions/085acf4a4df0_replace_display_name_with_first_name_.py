"""replace display_name with first_name last_name name_is_public on users

Revision ID: 085acf4a4df0
Revises: 653e63d01894
Create Date: 2026-05-12 09:22:48.733707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '085acf4a4df0'
down_revision: Union[str, Sequence[str], None] = '653e63d01894'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('first_name', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('name_is_public', sa.Boolean(), server_default='false', nullable=False))
    op.drop_column('users', 'display_name')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('users', sa.Column('display_name', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.drop_column('users', 'name_is_public')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
