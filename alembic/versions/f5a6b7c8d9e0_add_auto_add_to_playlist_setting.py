"""add auto_add_to_playlist to settings

Revision ID: f5a6b7c8d9e0
Revises: e4a7b2d1c3f5
Create Date: 2026-03-31 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4a7b2d1c3f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add auto_add_to_playlist boolean column to settings table."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auto_add_to_playlist', sa.Boolean(), server_default='1', nullable=False))


def downgrade() -> None:
    """Remove auto_add_to_playlist column."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('auto_add_to_playlist')
