"""add player health monitoring columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add player health monitoring columns to devices and settings."""
    # Device columns
    op.add_column('devices', sa.Column('uptime_seconds', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('js_heap_used_mb', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('js_heap_total_mb', sa.Integer(), nullable=True))
    op.add_column('devices', sa.Column('dom_responsive', sa.Boolean(), nullable=True))
    op.add_column('devices', sa.Column('restart_requested', sa.Boolean(), nullable=True, server_default='0'))

    # Settings columns
    op.add_column('settings', sa.Column('player_restart_hour', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('player_memory_limit_mb', sa.Integer(), nullable=True, server_default='200'))


def downgrade() -> None:
    """Remove player health monitoring columns."""
    op.drop_column('settings', 'player_memory_limit_mb')
    op.drop_column('settings', 'player_restart_hour')
    op.drop_column('devices', 'restart_requested')
    op.drop_column('devices', 'dom_responsive')
    op.drop_column('devices', 'js_heap_total_mb')
    op.drop_column('devices', 'js_heap_used_mb')
    op.drop_column('devices', 'uptime_seconds')
