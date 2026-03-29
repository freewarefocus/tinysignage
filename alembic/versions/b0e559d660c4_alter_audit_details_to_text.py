"""alter audit_logs details column to Text

Revision ID: b0e559d660c4
Revises: c4e8f1a23b67
Create Date: 2026-03-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0e559d660c4'
down_revision: Union[str, None] = 'c4e8f1a23b67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change details from String(4096) to Text for unlimited length."""
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.alter_column('details',
                              existing_type=sa.String(length=4096),
                              type_=sa.Text(),
                              existing_nullable=True)


def downgrade() -> None:
    """Revert details back to String(4096)."""
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.alter_column('details',
                              existing_type=sa.Text(),
                              type_=sa.String(length=4096),
                              existing_nullable=True)
