"""add player_log columns to devices

Revision ID: 08664b6674af
Revises: 4236132c0552
Create Date: 2026-03-30 10:35:11.621093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08664b6674af'
down_revision: Union[str, None] = '4236132c0552'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add player_log and player_log_updated_at columns to devices."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('player_log', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('player_log_updated_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove player_log columns from devices."""
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.drop_column('player_log_updated_at')
        batch_op.drop_column('player_log')
