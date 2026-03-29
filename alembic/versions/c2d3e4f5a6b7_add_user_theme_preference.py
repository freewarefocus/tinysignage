"""add user theme preference

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-29 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add theme_preference column to users table."""
    op.add_column(
        'users',
        sa.Column('theme_preference', sa.String(length=20), nullable=False, server_default='dark'),
    )


def downgrade() -> None:
    """Remove theme_preference column from users table."""
    op.drop_column('users', 'theme_preference')
