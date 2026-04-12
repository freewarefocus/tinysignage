"""add cog_rss_mb column to devices

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cog_rss_mb column to devices for Pi process memory monitoring."""
    op.add_column('devices', sa.Column('cog_rss_mb', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove cog_rss_mb column."""
    op.drop_column('devices', 'cog_rss_mb')
