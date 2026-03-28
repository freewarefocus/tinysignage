"""First-boot wizard API — captures device name and initial configuration."""

from pathlib import Path

import yaml
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_token, hash_token
from app.database import get_session
from app.models import ApiToken, Device

router = APIRouter()

_config_path = Path("config.yaml")
_setup_done_marker = Path("db/.setup_done")


def is_setup_done() -> bool:
    return _setup_done_marker.exists()


SETUP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TinySignage — Setup</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: system-ui, sans-serif; background: #0f1117; color: #e0e0e0;
       display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.card { background: #1a1d27; padding: 2.5rem; border-radius: 12px; width: 100%;
        max-width: 420px; }
h1 { font-size: 1.5rem; margin-bottom: 0.5rem; color: #fff; }
p { color: #888; margin-bottom: 1.5rem; font-size: 0.9rem; }
label { display: block; font-size: 0.85rem; color: #aaa; margin-bottom: 0.3rem; }
input { width: 100%; background: #0f1117; border: 1px solid #3a3a5a; color: #eee;
        padding: 0.6rem; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem; }
input:focus { outline: none; border-color: #7c83ff; }
button { background: #7c83ff; color: #fff; border: none; padding: 0.7rem 2rem;
         border-radius: 6px; cursor: pointer; font-size: 1rem; width: 100%; }
button:hover { background: #6b72e8; }
.done { text-align: center; color: #4caf50; }
</style>
</head>
<body>
<div class="card" id="form-card">
  <h1>Welcome to TinySignage</h1>
  <p>Configure your signage player to get started.</p>
  <form id="setup-form">
    <label for="device_name">Device Name</label>
    <input type="text" id="device_name" value="My Signage Player" required>
    <label for="server_url">Server URL (for remote CMS)</label>
    <input type="text" id="server_url" placeholder="http://localhost:8080">
    <button type="submit">Complete Setup</button>
  </form>
</div>
<script>
document.getElementById('setup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = {
    device_name: document.getElementById('device_name').value,
    server_url: document.getElementById('server_url').value,
  };
  const resp = await fetch('/api/setup', { method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
  if (resp.ok) {
    const data = await resp.json();
    let html = '<div class="done"><h1>Setup Complete!</h1>';
    if (data.admin_token) {
      html += '<p style="color:#ff9800;margin:1rem 0 0.5rem">Save these tokens now — they will not be shown again:</p>';
      html += '<label>Admin API Token</label>';
      html += '<input type="text" value="' + data.admin_token + '" readonly onclick="this.select()">';
      if (data.device_token && data.device_id) {
        html += '<label>Device Token</label>';
        html += '<input type="text" value="' + data.device_token + '" readonly onclick="this.select()">';
        const playerBase = data.server_url || '';
        const playerUrl = playerBase + '/player?device=' + data.device_id + '&token=' + data.device_token;
        html += '<label style="margin-top:0.5rem">Player URL</label>';
        html += '<div style="display:flex;gap:0.5rem;margin-bottom:1rem">';
        html += '<input type="text" id="player-url" value="' + playerUrl + '" readonly onclick="this.select()" style="margin-bottom:0">';
        html += '<button type="button" onclick="navigator.clipboard.writeText(document.getElementById(\'player-url\').value)" style="width:auto;padding:0.6rem 1rem;font-size:0.85rem;white-space:nowrap">Copy</button>';
        html += '</div>';
        html += '<a href="' + playerUrl + '" target="_blank" style="color:#7c83ff;font-size:0.85rem">Open Player &rarr;</a>';
      }
      html += '<p style="color:#888;font-size:0.8rem;margin-top:0.5rem">Store the admin token in the CMS (Settings &gt; API Token).</p>';
      html += '<button onclick="localStorage.setItem(\'tinysignage_admin_token\', \'' + data.admin_token + '\');window.location.href=\'/cms\'" style="margin-top:1rem">Continue to CMS</button>';
    } else {
      html += '<p>Redirecting to CMS...</p>';
      html += '</div>';
      setTimeout(() => window.location.href = '/cms', 1500);
    }
    html += '</div>';
    document.getElementById('form-card').innerHTML = html;
  }
});
</script>
</body>
</html>"""


@router.get("/setup")
async def setup_page():
    if is_setup_done():
        return HTMLResponse("<script>window.location.href='/cms'</script>")
    return HTMLResponse(SETUP_HTML)


@router.post("/setup")
async def complete_setup(body: dict, session: AsyncSession = Depends(get_session)):
    if is_setup_done():
        return {"status": "already_done"}

    device_name = body.get("device_name", "My Signage Player")
    server_url = body.get("server_url", "")

    # Update the default device name
    result = await session.execute(select(Device))
    device = result.scalars().first()
    if device:
        device.name = device_name
        await session.commit()

    # Save server_url to config if provided
    if server_url:
        config = yaml.safe_load(_config_path.read_text())
        config["server_url"] = server_url
        _config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    # Generate admin token
    admin_plaintext = generate_token()
    admin_token = ApiToken(
        token_hash=hash_token(admin_plaintext),
        name="Setup Admin",
        role="admin",
        created_by="setup_wizard",
    )
    session.add(admin_token)

    # Generate device token for the default device
    device_plaintext = None
    if device:
        device_plaintext = generate_token()
        device_token = ApiToken(
            token_hash=hash_token(device_plaintext),
            name=f"Device: {device_name}",
            role="device",
            device_id=device.id,
            created_by="setup_wizard",
        )
        session.add(device_token)

    await session.commit()

    # Mark setup as done
    _setup_done_marker.parent.mkdir(parents=True, exist_ok=True)
    _setup_done_marker.touch()

    return {
        "status": "ok",
        "device_name": device_name,
        "device_id": device.id if device else None,
        "admin_token": admin_plaintext,
        "device_token": device_plaintext,
        "server_url": server_url,
    }
