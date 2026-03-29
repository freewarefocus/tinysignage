"""add overrides table

Revision ID: b3f7a2c91d4e
Revises: 19002c88f68e
Create Date: 2026-03-29 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7a2c91d4e'
down_revision: Union[str, None] = '19002c88f68e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('overrides',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=20), nullable=False),
        sa.Column('content', sa.String(length=4096), nullable=False),
        sa.Column('target_type', sa.String(length=20), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('overrides', schema=None) as batch_op:
        batch_op.create_index('ix_overrides_is_active', ['is_active'], unique=False)
        batch_op.create_index('ix_overrides_expires_at', ['expires_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('overrides', schema=None) as batch_op:
        batch_op.drop_index('ix_overrides_expires_at')
        batch_op.drop_index('ix_overrides_is_active')

    op.drop_table('overrides')
