"""default player_restart_hour to midnight

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-13 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set player_restart_hour to 0 (midnight) where it was NULL.

    Every mature open-source signage player assumes browser memory leaks
    are unavoidable and schedules a daily restart as a safety net.
    Defaulting to midnight ensures new and existing installs get this
    protection without manual configuration.
    """
    op.execute("UPDATE settings SET player_restart_hour = 0 WHERE player_restart_hour IS NULL")
    # Add server_default so new rows also get 0
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('player_restart_hour', server_default='0')


def downgrade() -> None:
    """Revert to nullable with no default."""
    with op.batch_alter_table('settings') as batch_op:
        batch_op.alter_column('player_restart_hour', server_default=None)
