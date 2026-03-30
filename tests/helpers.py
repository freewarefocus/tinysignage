def auth_header(plaintext_token: str) -> dict:
    """Return Authorization header dict for httpx requests."""
    return {"Authorization": f"Bearer {plaintext_token}"}


async def seed_defaults(session) -> tuple:
    """Seed Settings + default Playlist + default Device.
    Returns (settings, playlist, device).
    Used by tests that need the baseline state matching app startup.
    """
    from tests.factories import create_settings, create_playlist, create_device
    settings = await create_settings(session)
    playlist = await create_playlist(session, name="Default Playlist", is_default=True)
    device = await create_device(session, name="Default Player", playlist_id=playlist.id)
    await session.commit()
    return settings, playlist, device
