"""CMS Schedule Editor tests — Python equivalent of Phase 6 ScheduleEditor.test.js.

Tests schedule creation form fields and time format validation.

[FT-7.2, FT-7.7, FT-7.8]
"""

from tests.factories import create_playlist, create_token
from tests.helpers import auth_header


async def test_schedule_form_creates_with_all_fields(client, session):
    """POST /api/schedules accepts time inputs and day checkboxes."""
    _, token = await create_token(session)
    playlist = await create_playlist(session, name="Morning Show")
    await session.commit()

    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Weekday Mornings",
            "playlist_id": playlist.id,
            "start_time": "08:00",
            "end_time": "12:00",
            "days_of_week": "0,1,2,3,4",
            "target_type": "all",
            "priority": 5,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Weekday Mornings"
    assert data["start_time"] == "08:00"
    assert data["end_time"] == "12:00"
    assert data["days_of_week"] == "0,1,2,3,4"
    assert data["priority"] == 5


async def test_schedule_validates_time_format(client, session):
    """Invalid time input returns validation error."""
    _, token = await create_token(session)
    playlist = await create_playlist(session, name="Bad Schedule PL")
    await session.commit()

    # Invalid format: not HH:MM
    resp = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Time",
            "playlist_id": playlist.id,
            "start_time": "8:00",
            "target_type": "all",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400
    assert "HH:MM" in resp.json()["detail"]

    # Invalid hour
    resp2 = await client.post(
        "/api/schedules",
        json={
            "name": "Bad Hour",
            "playlist_id": playlist.id,
            "start_time": "25:00",
            "target_type": "all",
        },
        headers=auth_header(token),
    )
    assert resp2.status_code == 400
