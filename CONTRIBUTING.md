# Contributing to TinySignage

TinySignage is a self-contained digital signage system. The guiding principle is simplicity: one process, one database, zero external services. Contributions that maintain this simplicity are welcome.

---

## Development setup

### Backend

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage

python -m venv venv
source venv/bin/activate    # Linux/macOS
venv\Scripts\activate       # Windows

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080
```

The setup wizard runs at `http://localhost:8080/setup` on first boot. After that, the CMS is at `/cms` and the player at `/player`.

### CMS frontend (hot reload)

```bash
cd cms
npm install
npm run dev
```

Vite proxies `/api/*` and `/media/*` to `localhost:8080` during development. Edit Vue components and see changes immediately.

### Full Docker build

```bash
docker compose up --build
```

Multi-stage build: Node 22 compiles the Vue CMS into static files, then Python 3.11-slim runs the backend.

---

## Code conventions

### Paths

Use `pathlib.Path` everywhere for file paths. Never use string concatenation for paths.

### Database

- **aiosqlite 0.21.0** is pinned. Versions 0.22+ have Windows connection-hanging bugs with SQLAlchemy async sessions. Do not upgrade.
- **NullPool** is required for the SQLite async engine. No connection pooling for SQLite.
- **Alembic migrations** for all schema changes. Run `alembic revision --autogenerate -m "description"` to create a migration. Never use raw ALTER TABLE.
- **Naive UTC datetimes** -- SQLite stores naive datetimes. Use `datetime.now(timezone.utc).replace(tzinfo=None)` when creating timestamps.

### Auth

All `/api/*` endpoints require a Bearer token. Use the dependencies from `app/auth.py`:

| Dependency | Minimum role |
|------------|-------------|
| `require_admin` | admin |
| `require_editor` | editor or admin |
| `require_viewer` | viewer, editor, or admin |
| `require_device` | device (player polling) |

Only `/health`, `/setup`, and `/api/devices/register` are public.

### Audit logging

All mutating API calls (POST, PATCH, PUT, DELETE) on content endpoints must log to the audit trail via `app/audit.py`.

---

## How to add a new endpoint

1. Create or edit the route module in `app/api/`.
2. Add the appropriate auth dependency (`require_admin`, `require_editor`, etc.).
3. Add Pydantic request/response schemas in `app/schemas.py`.
4. If the endpoint mutates data, add audit logging.
5. Mount the router in `app/main.py` if it is a new module.

## How to add a new model

1. Define the model in `app/models.py`.
2. Add Pydantic schemas in `app/schemas.py`.
3. Create an Alembic migration: `alembic revision --autogenerate -m "add model_name table"`.
4. Test the migration: `alembic upgrade head`.

## How to add a CMS view

1. Create a Vue component in `cms/src/views/`.
2. Add a route in `cms/src/router/index.js`.
3. Add sidebar navigation in `cms/src/App.vue`.
4. Use `cms/src/api/client.js` for API calls (handles Bearer token automatically).

---

## Architecture decisions not to break

These are intentional design choices. Do not change them without discussion.

- **Polling, not WebSocket.** The player polls every 30 seconds. For digital signage, this is invisible to viewers and makes the player survive network outages without reconnect logic.
- **SQLite only.** No PostgreSQL, no Redis, no message queue. SQLite is sufficient for self-hosted single-instance signage.
- **Single process.** One FastAPI process serves the API, CMS, player, and media. No separate worker processes.
- **No external services.** No cloud APIs, no CDN, no telemetry, no license server. Everything runs locally.
- **Browser player.** The player is a static HTML page. No native app, no Electron wrapper.

---

## Pull request guidelines

- Keep PRs focused. One feature or fix per PR.
- Include a clear description of what changed and why.
- Test your changes against a fresh database (delete `db/signage.db` and run through setup).
- Run the backend and verify the CMS and player work.
- If you add or change an API endpoint, update the request/response schemas.

---

## License

By contributing to TinySignage, you agree that your contributions will be licensed under the [AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html) license.

---

## See also

- [Architecture](docs/architecture.md) -- System design and project layout
- [API Reference](docs/api-reference.md) -- All endpoints
- [Configuration](docs/configuration.md) -- config.yaml reference
