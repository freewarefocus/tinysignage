"""add last_webhook_fire to trigger_branches

Revision ID: 4236132c0552
Revises: 125e876c0461
Create Date: 2026-03-29 20:13:23.216695

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4236132c0552'
down_revision: Union[str, None] = '125e876c0461'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('trigger_branches', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_webhook_fire', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('trigger_branches', schema=None) as batch_op:
        batch_op.drop_column('last_webhook_fire')
