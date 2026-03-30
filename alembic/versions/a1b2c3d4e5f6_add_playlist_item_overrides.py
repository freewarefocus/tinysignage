"""add playlist item transition and duration overrides

Revision ID: a1b2c3d4e5f6
Revises: 09d5e70fb471
Create Date: 2026-03-30 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '09d5e70fb471'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add per-item overrides and copy existing asset-level values."""
    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transition_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('transition_duration', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('duration', sa.Integer(), nullable=True))

    # Data migration: copy per-asset overrides into their playlist items
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE playlist_items
        SET transition_type = (
                SELECT assets.transition_type FROM assets
                WHERE assets.id = playlist_items.asset_id
            ),
            transition_duration = (
                SELECT assets.transition_duration FROM assets
                WHERE assets.id = playlist_items.asset_id
            )
        WHERE EXISTS (
            SELECT 1 FROM assets
            WHERE assets.id = playlist_items.asset_id
              AND (assets.transition_type IS NOT NULL OR assets.transition_duration IS NOT NULL)
        )
    """))


def downgrade() -> None:
    """Remove per-item override columns."""
    with op.batch_alter_table('playlist_items', schema=None) as batch_op:
        batch_op.drop_column('duration')
        batch_op.drop_column('transition_duration')
        batch_op.drop_column('transition_type')
