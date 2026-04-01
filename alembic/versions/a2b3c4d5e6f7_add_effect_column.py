"""add effect column to settings, playlists, playlist_items

Revision ID: a2b3c4d5e6f7
Revises: f5a6b7c8d9e0
Create Date: 2026-04-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add effect column to settings, playlists, and playlist_items."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('effect', sa.String(20), server_default='none', nullable=False))

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('effect', sa.String(20), nullable=True))

    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('effect', sa.String(20), nullable=True))


def downgrade() -> None:
    """Remove effect column from all three tables."""
    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.drop_column('effect')

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_column('effect')

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('effect')
