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

## Project Layout

- `app/` — FastAPI application package
- `app/api/` — API route modules
- `app/static/` — Frontend files (player, admin)
- `media/` — Uploaded media files (gitignored)
- `db/signage.db` — SQLite database (gitignored)
- `config.yaml` — User-editable configuration
- `.planning/` — Session planning docs
