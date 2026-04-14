"""drop WPE-specific columns (cog_rss_mb, video_play_count)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-13 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop cog_rss_mb and video_play_count — WPE browser engine removed."""
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_column('cog_rss_mb')
        batch_op.drop_column('video_play_count')


def downgrade() -> None:
    """Re-add WPE columns as nullable integers."""
    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('cog_rss_mb', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('video_play_count', sa.Integer(), nullable=True))
