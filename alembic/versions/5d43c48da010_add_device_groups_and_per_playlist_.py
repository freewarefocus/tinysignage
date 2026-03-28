"""add device groups and per-playlist settings

Revision ID: 5d43c48da010
Revises: d6579c860c3c
Create Date: 2026-03-28 18:19:19.538530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d43c48da010'
down_revision: Union[str, None] = 'd6579c860c3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('device_groups',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('device_group_memberships',
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('group_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.ForeignKeyConstraint(['group_id'], ['device_groups.id']),
        sa.PrimaryKeyConstraint('device_id', 'group_id')
    )
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('transition_type', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('transition_duration', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('default_duration', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('shuffle', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_column('shuffle')
        batch_op.drop_column('default_duration')
        batch_op.drop_column('transition_duration')
        batch_op.drop_column('transition_type')

    op.drop_table('device_group_memberships')
    op.drop_table('device_groups')
