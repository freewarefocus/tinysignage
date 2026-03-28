"""initial v3 schema

Revision ID: cba88a050e57
Revises:
Create Date: 2026-03-28 12:51:08.675719

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cba88a050e57'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all v3 tables."""
    op.create_table(
        'schema_version',
        sa.Column('id', sa.Integer(), primary_key=True, default=1),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'assets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('asset_type', sa.String(10), nullable=False),
        sa.Column('uri', sa.String(1024), nullable=False),
        sa.Column('duration', sa.Integer(), default=10),
        sa.Column('play_order', sa.Integer(), default=0),
        sa.Column('is_enabled', sa.Boolean(), default=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('mimetype', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('thumbnail_path', sa.String(1024), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), primary_key=True, default=1),
        sa.Column('transition_duration', sa.Float(), default=1.0),
        sa.Column('transition_type', sa.String(20), default='fade'),
        sa.Column('default_duration', sa.Integer(), default=10),
        sa.Column('shuffle', sa.Boolean(), default=False),
    )

    op.create_table(
        'playlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
    )

    op.create_table(
        'devices',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, server_default='Default Player'),
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id'), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('status', sa.String(20), server_default='offline'),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=True),
        sa.Column('player_version', sa.String(50), nullable=True),
        sa.Column('player_timezone', sa.String(50), nullable=True),
        sa.Column('clock_drift_seconds', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime()),
    )

    op.create_table(
        'playlist_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id'), nullable=False),
        sa.Column('asset_id', sa.String(36), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('order', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime()),
    )


def downgrade() -> None:
    """Drop all v3 tables."""
    op.drop_table('playlist_items')
    op.drop_table('devices')
    op.drop_table('playlists')
    op.drop_table('settings')
    op.drop_table('assets')
    op.drop_table('schema_version')
