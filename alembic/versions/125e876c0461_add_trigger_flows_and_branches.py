"""add trigger flows and branches

Revision ID: 125e876c0461
Revises: 08c178caf3a7
Create Date: 2026-03-29 19:37:12.227571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '125e876c0461'
down_revision: Union[str, None] = '08c178caf3a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('trigger_flows',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=1024), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('trigger_branches',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('flow_id', sa.String(length=36), nullable=False),
    sa.Column('source_playlist_id', sa.String(length=36), nullable=False),
    sa.Column('target_playlist_id', sa.String(length=36), nullable=False),
    sa.Column('trigger_type', sa.String(length=20), nullable=False),
    sa.Column('trigger_config', sa.Text(), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['flow_id'], ['trigger_flows.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['source_playlist_id'], ['playlists.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_playlist_id'], ['playlists.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trigger_flow_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_playlists_trigger_flow_id', 'trigger_flows', ['trigger_flow_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('playlists', schema=None) as batch_op:
        batch_op.drop_constraint('fk_playlists_trigger_flow_id', type_='foreignkey')
        batch_op.drop_column('trigger_flow_id')

    op.drop_table('trigger_branches')
    op.drop_table('trigger_flows')
