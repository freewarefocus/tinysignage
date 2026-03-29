"""fix missing ondelete FK constraints

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-03-29 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fks_by_column(batch_op, table_name, columns):
    """Drop all existing FK constraints on the given columns (by reflected name).

    SQLite unnamed FKs get auto-generated names during reflection. We inspect
    the reflected table to find and drop them before creating replacements.
    """
    from sqlalchemy import inspect as sa_inspect, create_engine
    eng = create_engine(f"sqlite:///db/signage.db")
    inspector = sa_inspect(eng)
    fks = inspector.get_foreign_keys(table_name)
    eng.dispose()
    for fk in fks:
        if fk.get("constrained_columns") and fk["constrained_columns"][0] in columns:
            name = fk.get("name")
            if name:
                try:
                    batch_op.drop_constraint(name, type_='foreignkey')
                except (ValueError, KeyError):
                    pass  # constraint name mismatch between reflection and batch


def upgrade() -> None:
    """Recreate ForeignKey constraints with proper ondelete rules.

    SQLite doesn't support ALTER CONSTRAINT, so we use batch mode
    which recreates the table under the hood. We reflect existing FK
    names (which may be auto-generated) and drop them before creating
    named replacements with ondelete rules.
    """
    # devices: playlist_id SET NULL, layout_id SET NULL
    with op.batch_alter_table('devices', recreate='always') as batch_op:
        _drop_fks_by_column(batch_op, 'devices', {'playlist_id', 'layout_id'})
        batch_op.create_foreign_key(
            'fk_devices_layout_id', 'layouts', ['layout_id'], ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_devices_playlist_id', 'playlists', ['playlist_id'], ['id'],
            ondelete='SET NULL',
        )

    # device_group_memberships: both FKs CASCADE
    with op.batch_alter_table('device_group_memberships', recreate='always') as batch_op:
        _drop_fks_by_column(batch_op, 'device_group_memberships', {'device_id', 'group_id'})
        batch_op.create_foreign_key(
            'fk_dgm_device_id', 'devices', ['device_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_foreign_key(
            'fk_dgm_group_id', 'device_groups', ['group_id'], ['id'],
            ondelete='CASCADE',
        )

    # playlist_items: playlist_id CASCADE, asset_id CASCADE
    with op.batch_alter_table('playlist_items', recreate='always') as batch_op:
        _drop_fks_by_column(batch_op, 'playlist_items', {'playlist_id', 'asset_id'})
        batch_op.create_foreign_key(
            'fk_pi_playlist_id', 'playlists', ['playlist_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_foreign_key(
            'fk_pi_asset_id', 'assets', ['asset_id'], ['id'],
            ondelete='CASCADE',
        )

    # layout_zones: playlist_id SET NULL (layout_id already has CASCADE)
    with op.batch_alter_table('layout_zones', recreate='always') as batch_op:
        _drop_fks_by_column(batch_op, 'layout_zones', {'playlist_id'})
        batch_op.create_foreign_key(
            'fk_lz_playlist_id', 'playlists', ['playlist_id'], ['id'],
            ondelete='SET NULL',
        )

    # schedules: playlist_id CASCADE, transition_playlist_id SET NULL
    with op.batch_alter_table('schedules', recreate='always') as batch_op:
        _drop_fks_by_column(batch_op, 'schedules', {'playlist_id', 'transition_playlist_id'})
        batch_op.create_foreign_key(
            'fk_sched_playlist_id', 'playlists', ['playlist_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_foreign_key(
            'fk_sched_transition_playlist_id', 'playlists',
            ['transition_playlist_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    """Remove named FK constraints (revert to unnamed originals)."""
    with op.batch_alter_table('schedules') as batch_op:
        batch_op.drop_constraint('fk_sched_transition_playlist_id', type_='foreignkey')
        batch_op.drop_constraint('fk_sched_playlist_id', type_='foreignkey')

    with op.batch_alter_table('layout_zones') as batch_op:
        batch_op.drop_constraint('fk_lz_playlist_id', type_='foreignkey')

    with op.batch_alter_table('playlist_items') as batch_op:
        batch_op.drop_constraint('fk_pi_asset_id', type_='foreignkey')
        batch_op.drop_constraint('fk_pi_playlist_id', type_='foreignkey')

    with op.batch_alter_table('device_group_memberships') as batch_op:
        batch_op.drop_constraint('fk_dgm_group_id', type_='foreignkey')
        batch_op.drop_constraint('fk_dgm_device_id', type_='foreignkey')

    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_constraint('fk_devices_playlist_id', type_='foreignkey')
        batch_op.drop_constraint('fk_devices_layout_id', type_='foreignkey')
        batch_op.create_foreign_key(
            'fk_devices_layout_id', 'layouts', ['layout_id'], ['id'],
        )
