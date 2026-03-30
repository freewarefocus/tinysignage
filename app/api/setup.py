"""First-boot wizard API — captures device name, admin account, and initial configuration."""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_registration_key, generate_token, hash_password, hash_registration_key, hash_token
from app.database import get_session
from app.models import ApiToken, Device, Settings, User

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
.section-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
                 color: #666; margin: 0.5rem 0 0.8rem; border-top: 1px solid #2a2d3a;
                 padding-top: 1rem; }
.error { color: #ef5350; font-size: 0.85rem; margin-bottom: 0.5rem; display: none; }
.hero-section { background: #252836; border-radius: 8px; padding: 1rem; margin-top: 1rem; }
details summary:hover { color: #aaa; }
details summary::marker { color: #666; }
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

    <div class="section-label">Admin Account</div>
    <label for="admin_username">Username</label>
    <input type="text" id="admin_username" value="admin" required minlength="3">
    <label for="admin_password">Password</label>
    <input type="password" id="admin_password" required minlength="8" placeholder="Min. 8 characters">
    <label for="admin_password_confirm">Confirm Password</label>
    <input type="password" id="admin_password_confirm" required minlength="8">
    <div class="error" id="error-msg"></div>

    <button type="submit">Complete Setup</button>
  </form>
</div>
<script>
document.getElementById('setup-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const errEl = document.getElementById('error-msg');
  errEl.style.display = 'none';

  const pw = document.getElementById('admin_password').value;
  const pw2 = document.getElementById('admin_password_confirm').value;
  if (pw !== pw2) {
    errEl.textContent = 'Passwords do not match.';
    errEl.style.display = 'block';
    return;
  }
  if (pw.length < 8) {
    errEl.textContent = 'Password must be at least 8 characters.';
    errEl.style.display = 'block';
    return;
  }

  const body = {
    device_name: document.getElementById('device_name').value,
    server_url: document.getElementById('server_url').value,
    admin_username: document.getElementById('admin_username').value,
    admin_password: pw,
  };
  const resp = await fetch('/api/setup', { method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
  if (!resp.ok) {
    const data = await resp.json();
    errEl.textContent = data.detail || 'Setup failed.';
    errEl.style.display = 'block';
    return;
  }
  const data = await resp.json();
  let html = '<div class="done"><h1>Setup Complete!</h1>';
  if (data.device_token && data.device_id) {
    const playerBase = data.server_url || '';
    const playerUrl = playerBase + '/player?device=' + data.device_id + '&token=' + data.device_token;
    html += '<div class="hero-section">';
    html += '<h2 style="font-size:1.1rem;color:#fff;margin-bottom:0.3rem">Your Player URL</h2>';
    html += '<p style="color:#888;font-size:0.85rem;margin-bottom:0.8rem">Open this URL in a fullscreen browser on the screen you want to use as a display.</p>';
    html += '<div style="display:flex;gap:0.5rem;margin-bottom:0.5rem">';
    html += '<input type="text" id="player-url" value="' + playerUrl + '" readonly onclick="this.select()" style="margin-bottom:0;font-size:0.85rem">';
    html += '<button type="button" onclick="navigator.clipboard.writeText(document.getElementById(\\'player-url\\').value)" style="width:auto;padding:0.6rem 1rem;font-size:0.85rem;white-space:nowrap">Copy</button>';
    html += '</div>';
    html += '</div>';
  }
  if (data.registration_key) {
    html += '<div class="hero-section" style="margin-top:1rem">';
    html += '<h2 style="font-size:1.1rem;color:#fff;margin-bottom:0.3rem">Registration Key</h2>';
    html += '<p style="color:#888;font-size:0.85rem;margin-bottom:0.8rem">Give this key to anyone installing a player. Players register themselves and wait for your approval.</p>';
    html += '<div style="display:flex;gap:0.5rem;margin-bottom:0.5rem">';
    html += '<input type="text" id="reg-key" value="' + data.registration_key + '" readonly onclick="this.select()" style="margin-bottom:0;font-size:1.1rem;font-family:monospace;text-align:center;letter-spacing:0.15em">';
    html += '<button type="button" onclick="navigator.clipboard.writeText(document.getElementById(\\'reg-key\\').value)" style="width:auto;padding:0.6rem 1rem;font-size:0.85rem;white-space:nowrap">Copy</button>';
    html += '</div>';
    html += '<p style="color:#666;font-size:0.78rem">This key is shown once. You can regenerate it later in Settings.</p>';
    html += '</div>';
  }
  if (data.admin_token) {
    html += '<details style="margin-top:1rem;border-top:1px solid #2a2d3a;padding-top:0.8rem">';
    html += '<summary style="color:#888;font-size:0.85rem;cursor:pointer;margin-bottom:0.5rem">Technical: API Token (optional)</summary>';
    html += '<p style="color:#666;font-size:0.8rem;margin-bottom:0.5rem">This token is for scripts or external tools. You can create new tokens anytime in the CMS under Users. Safe to skip if you\\\'re just getting started.</p>';
    html += '<label>Admin API Token</label>';
    html += '<input type="text" value="' + data.admin_token + '" readonly onclick="this.select()">';
    html += '<p style="color:#666;font-size:0.78rem;margin-top:0.3rem">This token is shown once for security. You can always create new tokens later.</p>';
    html += '</details>';
  }
  html += '<p style="color:#888;font-size:0.85rem;margin-top:1rem">You can now log in with your admin account.</p>';
  html += '<button onclick="window.location.href=\\'/cms/login\\'" style="margin-top:0.8rem">Continue to Login</button>';
  html += '</div>';
  document.getElementById('form-card').innerHTML = html;
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
    admin_username = body.get("admin_username", "admin").strip()
    admin_password = body.get("admin_password", "")

    # Validate admin credentials
    if len(admin_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(admin_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Guard against duplicate admin creation if marker was deleted
    existing_user = await session.execute(
        select(User).where(User.username == admin_username)
    )
    if existing_user.scalars().first():
        raise HTTPException(status_code=409, detail="Admin user already exists")

    # Update the default device name
    result = await session.execute(select(Device))
    device = result.scalars().first()
    if device:
        device.name = device_name

    # Save server_url to config if provided
    if server_url:
        config = yaml.safe_load(_config_path.read_text())
        config["server_url"] = server_url
        _config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    # Create admin user account
    admin_user = User(
        username=admin_username,
        display_name="Administrator",
        password_hash=hash_password(admin_password),
        role="admin",
    )
    session.add(admin_user)
    await session.flush()  # Get user.id

    # Generate admin API token (for programmatic access)
    admin_plaintext = generate_token()
    admin_token = ApiToken(
        token_hash=hash_token(admin_plaintext),
        name="Setup Admin",
        role="admin",
        user_id=admin_user.id,
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

    # Generate registration key for screen-door registration
    reg_key_plaintext = generate_registration_key()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    settings = await session.get(Settings, 1)
    if settings:
        settings.registration_key_hash = hash_registration_key(reg_key_plaintext)
        settings.registration_key_created_at = now

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
        "registration_key": reg_key_plaintext,
    }
