"""add device capability columns

Revision ID: ff890d243d8b
Revises: d3e4f5a6b7c8
Create Date: 2026-03-29 16:40:03.669727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff890d243d8b'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('player_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('gpio_supported', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('resolution_detected', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('ram_mb', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('storage_total_mb', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('storage_free_mb', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('capabilities', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('capabilities_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('capabilities_updated_at')
        batch_op.drop_column('capabilities')
        batch_op.drop_column('storage_free_mb')
        batch_op.drop_column('storage_total_mb')
        batch_op.drop_column('ram_mb')
        batch_op.drop_column('resolution_detected')
        batch_op.drop_column('gpio_supported')
        batch_op.drop_column('player_type')
