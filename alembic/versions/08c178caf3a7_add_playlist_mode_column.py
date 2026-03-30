"""add playlist mode column

Revision ID: 08c178caf3a7
Revises: ff890d243d8b
Create Date: 2026-03-29 19:02:14.142266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08c178caf3a7'
down_revision: Union[str, None] = 'ff890d243d8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode', sa.String(length=10), server_default='simple', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_column('mode')
