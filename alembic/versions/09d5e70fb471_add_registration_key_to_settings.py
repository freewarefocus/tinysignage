"""add registration key to settings

Revision ID: 09d5e70fb471
Revises: 08664b6674af
Create Date: 2026-03-30 17:10:18.684358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09d5e70fb471'
down_revision: Union[str, None] = '08664b6674af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('registration_key_hash', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('registration_key_created_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('registration_key_created_at')
        batch_op.drop_column('registration_key_hash')
