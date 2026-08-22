"""replace link report reason with reason_code and detail

Revision ID: 5c83c0dda2cb
Revises: e3c707a1d84b
Create Date: 2026-08-22 08:25:08.552503

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c83c0dda2cb'
down_revision: Union[str, Sequence[str], None] = 'e3c707a1d84b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Free-text `reason` becomes a `reason_code` enum value plus optional
    `reason_detail`. A temporary server_default lets the NOT NULL column land on
    a table that already has rows; any existing prose is carried over as detail
    rather than dropped, and the default is removed afterwards so new inserts
    must state a reason explicitly.
    """
    op.add_column(
        'link_reports',
        sa.Column('reason_code', sa.String(), nullable=False, server_default='bad'),
    )
    op.add_column('link_reports', sa.Column('reason_detail', sa.Text(), nullable=True))
    op.execute('UPDATE link_reports SET reason_detail = reason')
    op.drop_column('link_reports', 'reason')
    op.alter_column('link_reports', 'reason_code', server_default=None)


def downgrade() -> None:
    """Downgrade schema.

    Collapses the pair back into one free-text column, falling back to the code
    when a report carried no detail so the NOT NULL column is never empty.
    """
    op.add_column(
        'link_reports',
        sa.Column('reason', sa.TEXT(), autoincrement=False, nullable=False, server_default=''),
    )
    op.execute('UPDATE link_reports SET reason = COALESCE(reason_detail, reason_code)')
    op.alter_column('link_reports', 'reason', server_default=None)
    op.drop_column('link_reports', 'reason_detail')
    op.drop_column('link_reports', 'reason_code')
