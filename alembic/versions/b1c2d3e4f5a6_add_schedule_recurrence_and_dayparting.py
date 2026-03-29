"""add schedule recurrence and dayparting

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-03-29 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.add_column(
            sa.Column("recurrence_rule", sa.String(500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("priority_weight", sa.Float(), server_default="1.0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("transition_playlist_id", sa.String(36), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("schedules") as batch_op:
        batch_op.drop_column("transition_playlist_id")
        batch_op.drop_column("priority_weight")
        batch_op.drop_column("recurrence_rule")
