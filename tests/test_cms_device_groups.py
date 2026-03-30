"""CMS Device Groups tests — Python equivalent of Phase 6 DeviceGroups.test.js.

Tests group listing and member count display.

[FT-5.1, FT-5.6]
"""

from tests.factories import (
    add_device_to_group,
    create_device,
    create_device_group,
    create_token,
)
from tests.helpers import auth_header


async def test_device_groups_renders_group_list(client, session):
    """GET /api/groups returns group names."""
    _, token = await create_token(session)
    await create_device_group(session, name="Lobby Screens")
    await create_device_group(session, name="Cafeteria")
    await session.commit()

    resp = await client.get("/api/groups", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {g["name"] for g in data}
    assert names == {"Lobby Screens", "Cafeteria"}


async def test_device_groups_shows_member_count(client, session):
    """Group with 3 members shows member_count=3."""
    _, token = await create_token(session)
    group = await create_device_group(session, name="Big Group")
    d1 = await create_device(session, name="Player 1")
    d2 = await create_device(session, name="Player 2")
    d3 = await create_device(session, name="Player 3")
    await add_device_to_group(session, d1.id, group.id)
    await add_device_to_group(session, d2.id, group.id)
    await add_device_to_group(session, d3.id, group.id)
    await session.commit()

    resp = await client.get("/api/groups", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    big_group = next(g for g in data if g["name"] == "Big Group")
    assert big_group["member_count"] == 3
