"""add cascade delete to api_token device_id fk

Revision ID: 2c1112014fc6
Revises: a0cfb5623d30
Create Date: 2026-03-28 19:41:12.199697

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c1112014fc6'
down_revision: Union[str, None] = 'a0cfb5623d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

naming_convention = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table(
        'api_tokens', schema=None, naming_convention=naming_convention
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_api_tokens_device_id_devices', type_='foreignkey'
        )
        batch_op.create_foreign_key(
            'fk_api_tokens_device_id_devices',
            'devices', ['device_id'], ['id'], ondelete='CASCADE',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table(
        'api_tokens', schema=None, naming_convention=naming_convention
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_api_tokens_device_id_devices', type_='foreignkey'
        )
        batch_op.create_foreign_key(
            'fk_api_tokens_device_id_devices',
            'devices', ['device_id'], ['id'],
        )
