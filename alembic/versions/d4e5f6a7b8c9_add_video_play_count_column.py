"""add video_play_count column to devices

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add video_play_count column for WPE memory pressure tracking."""
    op.add_column('devices', sa.Column('video_play_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove video_play_count column."""
    op.drop_column('devices', 'video_play_count')
