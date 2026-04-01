"""add override template columns (duration_minutes, activated_at)

Revision ID: e4a7b2d1c3f5
Revises: cc77b013f9ce
Create Date: 2026-03-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a7b2d1c3f5'
down_revision: Union[str, None] = 'cc77b013f9ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add duration_minutes and activated_at; backfill activated_at."""
    with op.batch_alter_table('overrides', schema=None) as batch_op:
        batch_op.add_column(sa.Column('duration_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('activated_at', sa.DateTime(), nullable=True))

    # Backfill: any currently-active override gets activated_at = created_at
    op.execute("UPDATE overrides SET activated_at = created_at WHERE is_active = 1")


def downgrade() -> None:
    """Remove duration_minutes and activated_at."""
    with op.batch_alter_table('overrides', schema=None) as batch_op:
        batch_op.drop_column('activated_at')
        batch_op.drop_column('duration_minutes')
