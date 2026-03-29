"""add layouts and zones

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-03-29 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create layouts and layout_zones tables, add layout_id to devices."""
    op.create_table(
        'layouts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'layout_zones',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('layout_id', sa.String(length=36), sa.ForeignKey('layouts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('zone_type', sa.String(length=20), nullable=False, server_default='main'),
        sa.Column('x_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('y_percent', sa.Float(), nullable=False, server_default='0'),
        sa.Column('width_percent', sa.Float(), nullable=False, server_default='100'),
        sa.Column('height_percent', sa.Float(), nullable=False, server_default='100'),
        sa.Column('z_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('playlist_id', sa.String(length=36), sa.ForeignKey('playlists.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('layout_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_devices_layout_id', 'layouts', ['layout_id'], ['id'])


def downgrade() -> None:
    """Remove layouts and zones."""
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_constraint('fk_devices_layout_id', type_='foreignkey')
        batch_op.drop_column('layout_id')
    op.drop_table('layout_zones')
    op.drop_table('layouts')
