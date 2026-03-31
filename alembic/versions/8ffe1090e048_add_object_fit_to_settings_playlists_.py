"""add object_fit to settings playlists and playlist_items

Revision ID: 8ffe1090e048
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30 19:00:58.988779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8ffe1090e048'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add object_fit column to settings, playlists, and playlist_items."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('object_fit', sa.String(length=20), server_default='contain', nullable=False))

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('object_fit', sa.String(length=20), nullable=True))

    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('object_fit', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Remove object_fit columns."""
    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.drop_column('object_fit')

    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_column('object_fit')

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('object_fit')
