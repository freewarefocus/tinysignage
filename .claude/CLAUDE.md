# TinySignage

Self-contained digital signage player — one Python process, one browser tab, zero cloud dependencies.

## How to Run

```
venv\Scripts\activate
uvicorn app.main:app --reload --port 8080
```

## Key Constraints

- **aiosqlite==0.21.0** — Pinned. Versions 0.22+ have Windows connection-hanging bugs with SQLAlchemy async sessions.
- **NullPool** — Always use `NullPool` for the SQLite async engine. No connection pooling needed for SQLite.
- **pathlib.Path** — Use everywhere for file paths. Never use string concatenation for paths.
- **Auth required** — All `/api/*` endpoints require Bearer token. Use dependencies from `app/auth.py` (`require_admin`, `require_editor`, `require_viewer`, `require_device`). Only `/health`, `/setup`, and `/api/devices/register` are public.
- **Alembic migrations** — Use Alembic for all schema changes (`alembic revision --autogenerate -m "description"`). Never use raw ALTER TABLE.

## Error Reporting Standard

Zero silent failures. Every error flows through two channels: user-facing (toast/status) and debug log. See `.planning/ERROR_REPORTING_STANDARD.md` for full details.

### Rules for new code
- **No empty catch blocks** — every `catch` must log (`console.error/warn` in CMS, `PlayerLog.*` in player, `log.error/exception` in Python)
- **No `.catch(() => {})`** — use `.catch(err => console.warn('[ComponentName] <context>:', err))` at minimum
- **CMS**: Use `api.get/post/put/del()` from `client.js` — errors auto-dispatch to toast via errorBus. Only catch locally when cleanup/component-specific UI is needed
- **Player**: Use `PlayerLog.info/warn/error()` instead of raw `console.*` — persists to localStorage ring buffer, uploaded to server on heartbeat, viewable via Ctrl+Shift+D debug overlay
- **Backend**: Let exceptions propagate to `error_handlers.py`. Background tasks: catch, `log.exception()`, recover. File ops: catch, log, return meaningful error
- **Audit log**: Failed auth attempts are logged with `action: "auth_failed"`. Auth failures (401/403) on API routes are logged at WARNING level

## Project Layout

- `app/` — FastAPI application package
- `app/api/` — API route modules
- `app/static/` — Frontend files (player, admin)
- `media/` — Uploaded media files (gitignored)
- `db/signage.db` — SQLite database (gitignored)
- `config.yaml` — User-editable configuration
- `.planning/` — Session planning docs
