"""Tests for schedule CRUD endpoints. [FT-7.*]"""

from tests.factories import (
    create_token, create_settings, create_playlist, create_device,
)
from tests.helpers import auth_header


async def test_list_schedules_empty(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.get("/api/schedules", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_schedule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Morning",
            "playlist_id": pl.id,
            "target_type": "all",
            "start_time": "08:00",
            "end_time": "12:00",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Morning"
    assert data["start_time"] == "08:00"


async def test_create_schedule_no_name(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={"playlist_id": pl.id, "target_type": "all"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_schedule_invalid_playlist(client, session):
    _, token = await create_token(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={"name": "Bad", "playlist_id": "nonexistent", "target_type": "all"},
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_create_schedule_invalid_time(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Time",
            "playlist_id": pl.id,
            "target_type": "all",
            "start_time": "25:00",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_schedule_invalid_days(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Days",
            "playlist_id": pl.id,
            "target_type": "all",
            "days_of_week": "7",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_schedule_invalid_rrule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Rule",
            "playlist_id": pl.id,
            "target_type": "all",
            "recurrence_rule": "INTERVAL=2",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_create_schedule_device_target(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    device = await create_device(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Device Schedule",
            "playlist_id": pl.id,
            "target_type": "device",
            "target_id": device.id,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201


async def test_create_schedule_invalid_target(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Target",
            "playlist_id": pl.id,
            "target_type": "device",
            "target_id": "nonexistent",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_get_schedule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={"name": "S1", "playlist_id": pl.id, "target_type": "all"},
        headers=auth_header(token),
    )
    sid = resp.json()["id"]
    resp2 = await client.get(
        f"/api/schedules/{sid}", headers=auth_header(token),
    )
    assert resp2.status_code == 200


async def test_update_schedule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={"name": "Before", "playlist_id": pl.id, "target_type": "all"},
        headers=auth_header(token),
    )
    sid = resp.json()["id"]
    resp2 = await client.patch(
        f"/api/schedules/{sid}",
        json={"name": "After"},
        headers=auth_header(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "After"


async def test_delete_schedule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={"name": "ToDelete", "playlist_id": pl.id, "target_type": "all"},
        headers=auth_header(token),
    )
    sid = resp.json()["id"]
    resp2 = await client.delete(
        f"/api/schedules/{sid}", headers=auth_header(token),
    )
    assert resp2.status_code == 200


async def test_create_schedule_with_rrule(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session)
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Weekly",
            "playlist_id": pl.id,
            "target_type": "all",
            "recurrence_rule": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO,WE,FR"


async def test_create_schedule_with_transition(client, session):
    _, token = await create_token(session)
    pl = await create_playlist(session, name="Main")
    transition_pl = await create_playlist(session, name="Transition")
    await session.commit()
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "With Transition",
            "playlist_id": pl.id,
            "target_type": "all",
            "transition_playlist_id": transition_pl.id,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["transition_playlist_id"] == transition_pl.id


async def test_schedule_timeline_preview(client, session):
    await create_settings(session)
    _, token = await create_token(session)
    pl = await create_playlist(session)
    device = await create_device(session, playlist_id=pl.id)
    await session.commit()
    resp = await client.get(
        f"/api/schedules/preview/timeline?device_id={device.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "slots" in data
    assert len(data["slots"]) == 48
