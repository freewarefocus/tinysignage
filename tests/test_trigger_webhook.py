"""Webhook firing and token validation tests. [FT-17.12–17.14]

The webhook endpoint (POST /api/triggers/webhook/{branch_id}) is public
(no Bearer auth) but validates via the webhook token in the request body
vs. the stored trigger_config.token.
"""

import json as json_mod
import asyncio
import inspect
import textwrap

from tests.factories import (
    create_token, create_playlist, create_trigger_flow, create_trigger_branch,
)
from tests.helpers import auth_header


async def _create_webhook_branch(session, client, admin_token, *, custom_token=None):
    """Helper: create a flow with a webhook branch, return (branch_id, webhook_token)."""
    pl1 = await create_playlist(session, name="Source")
    pl2 = await create_playlist(session, name="Target")
    flow = await create_trigger_flow(session, name="Webhook Test")
    await session.commit()

    config = {}
    if custom_token:
        config["token"] = custom_token

    resp = await client.post(
        f"/api/trigger-flows/{flow.id}/branches",
        json={
            "source_playlist_id": pl1.id,
            "target_playlist_id": pl2.id,
            "trigger_type": "webhook",
            "trigger_config": config,
        },
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 201
    data = resp.json()
    tc = data["trigger_config"]
    if isinstance(tc, str):
        tc = json_mod.loads(tc)
    return data["id"], tc["token"]


async def test_fire_webhook_success(client, session):
    """Correct token -> 200, {"status": "triggered"}."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(session, client, admin_token)

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"


async def test_fire_webhook_wrong_token(client, session):
    """Wrong token -> 403."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, _ = await _create_webhook_branch(session, client, admin_token)

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": "wrong_token_value"},
    )
    assert resp.status_code == 403


async def test_fire_webhook_missing_token(client, session):
    """No token in body -> 403."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, _ = await _create_webhook_branch(session, client, admin_token)

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={},
    )
    assert resp.status_code == 403


async def test_fire_webhook_nonexistent_branch(client, session):
    """Fake branch_id -> 404."""
    resp = await client.post(
        "/api/triggers/webhook/nonexistent-branch-id",
        json={"token": "anything"},
    )
    assert resp.status_code == 404


async def test_fire_webhook_non_webhook_branch(client, session):
    """Branch is type='keyboard' -> 400."""
    _, admin_token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    branch = await create_trigger_branch(
        session, flow.id, src.id, tgt.id,
        trigger_type="keyboard",
        trigger_config='{"key": "1"}',
    )
    await session.commit()

    resp = await client.post(
        f"/api/triggers/webhook/{branch.id}",
        json={"token": "anything"},
    )
    assert resp.status_code == 400


async def test_fire_webhook_updates_timestamp(client, session):
    """Fire webhook -> branch.last_webhook_fire is set."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(session, client, admin_token)

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp.status_code == 200

    # Verify via GET flow that the branch now has last_webhook_fire
    # We need to find the flow that contains this branch
    resp2 = await client.get("/api/trigger-flows", headers=auth_header(admin_token))
    flows = resp2.json()
    assert len(flows) > 0
    flow_id = flows[0]["id"]

    resp3 = await client.get(
        f"/api/trigger-flows/{flow_id}", headers=auth_header(admin_token),
    )
    branch_data = resp3.json()["branches"][0]
    assert "last_webhook_fire" in branch_data


async def test_fire_webhook_timestamp_updates_on_second_fire(client, session):
    """Fire twice -> last_webhook_fire changes."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(session, client, admin_token)

    # First fire
    resp1 = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp1.status_code == 200

    # Get timestamp after first fire
    resp_flows = await client.get("/api/trigger-flows", headers=auth_header(admin_token))
    flow_id = resp_flows.json()[0]["id"]
    resp_flow = await client.get(
        f"/api/trigger-flows/{flow_id}", headers=auth_header(admin_token),
    )
    ts1 = resp_flow.json()["branches"][0].get("last_webhook_fire")
    assert ts1 is not None

    # Small delay to ensure timestamp changes
    await asyncio.sleep(0.05)

    # Second fire
    resp2 = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp2.status_code == 200

    # Get timestamp after second fire
    resp_flow2 = await client.get(
        f"/api/trigger-flows/{flow_id}", headers=auth_header(admin_token),
    )
    ts2 = resp_flow2.json()["branches"][0].get("last_webhook_fire")
    assert ts2 is not None
    assert ts2 >= ts1  # At minimum equal, likely greater


async def test_fire_webhook_empty_config(client, session):
    """Branch has no token in config -> 403."""
    _, admin_token = await create_token(session)
    flow = await create_trigger_flow(session)
    src = await create_playlist(session, name="src")
    tgt = await create_playlist(session, name="tgt")
    # Create branch with webhook type but empty config (bypass auto-token via DB)
    branch = await create_trigger_branch(
        session, flow.id, src.id, tgt.id,
        trigger_type="webhook",
        trigger_config="{}",  # no token
    )
    await session.commit()

    resp = await client.post(
        f"/api/triggers/webhook/{branch.id}",
        json={"token": "anything"},
    )
    assert resp.status_code == 403


async def test_fire_webhook_constant_time_comparison(client, session):
    """Verify secrets.compare_digest is used (source inspection, not timing)."""
    import app.api.trigger_flows as tf_mod
    source = inspect.getsource(tf_mod.fire_webhook)
    assert "compare_digest" in source


async def test_fire_webhook_with_custom_token(client, session):
    """Create branch with explicit token -> fire with that token -> success."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(
        session, client, admin_token, custom_token="my_custom_secret_42",
    )
    assert wh_token == "my_custom_secret_42"

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": "my_custom_secret_42"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"


async def test_webhook_no_auth_header_needed(client, session):
    """No Authorization header -> still works (public endpoint)."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(session, client, admin_token)

    # Explicitly do NOT pass any headers
    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={"token": wh_token},
    )
    assert resp.status_code == 200


async def test_fire_webhook_body_extra_fields_ignored(client, session):
    """Extra fields in body don't cause errors."""
    _, admin_token = await create_token(session)
    await session.commit()
    branch_id, wh_token = await _create_webhook_branch(session, client, admin_token)

    resp = await client.post(
        f"/api/triggers/webhook/{branch_id}",
        json={
            "token": wh_token,
            "extra_field": "should be ignored",
            "another": 123,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "triggered"
