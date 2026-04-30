"""add group-based access control tables

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_group_memberships',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('device_groups.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'playlist_group_memberships',
        sa.Column('playlist_id', sa.String(36), sa.ForeignKey('playlists.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('device_groups.id', ondelete='CASCADE'), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('playlist_group_memberships')
    op.drop_table('user_group_memberships')
