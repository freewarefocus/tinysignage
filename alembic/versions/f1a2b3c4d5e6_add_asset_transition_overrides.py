"""add asset transition overrides

Revision ID: f1a2b3c4d5e6
Revises: b0e559d660c4
Create Date: 2026-03-29 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'b0e559d660c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add per-asset transition override columns."""
    op.add_column('assets', sa.Column('transition_type', sa.String(length=20), nullable=True))
    op.add_column('assets', sa.Column('transition_duration', sa.Float(), nullable=True))


def downgrade() -> None:
    """Remove per-asset transition override columns."""
    op.drop_column('assets', 'transition_duration')
    op.drop_column('assets', 'transition_type')
