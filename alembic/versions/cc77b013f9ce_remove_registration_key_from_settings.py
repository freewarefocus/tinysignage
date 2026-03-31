"""remove registration key from settings

Revision ID: cc77b013f9ce
Revises: 8ffe1090e048
Create Date: 2026-03-31 14:26:26.950406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc77b013f9ce'
down_revision: Union[str, None] = '8ffe1090e048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('registration_key_hash')
        batch_op.drop_column('registration_key_created_at')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('registration_key_created_at', sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column('registration_key_hash', sa.VARCHAR(length=64), nullable=True))
