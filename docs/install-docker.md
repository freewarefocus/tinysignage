# Install with Docker

Run TinySignage in a Docker container. This is the fastest install path and the easiest to maintain.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose (included with Docker Desktop)
- A machine with at least 512MB free RAM

## Install

```bash
git clone https://github.com/freewarefocus/tinysignage.git
cd tinysignage
docker compose up -d
```

The first build takes about a minute (two-stage: Node builds the Vue CMS, then Python runtime). Subsequent starts are instant.

- **Setup wizard**: `http://localhost:8080/setup` (first run only)
- **CMS**: `http://localhost:8080/cms`
- **Player**: `http://localhost:8080/player`

## Data persistence

All data lives in bind-mounted directories next to the compose file:

| Host path | Container path | Contents |
|-----------|---------------|----------|
| `./media` | `/app/media` | Uploaded images, videos, thumbnails |
| `./db` | `/app/db` | SQLite database |
| `./certs` | `/app/certs` | Self-signed TLS certificate and key (only populated if HTTPS is enabled) |
| `./config.yaml` | `/app/config.yaml` | Configuration file |

These directories are visible, portable, and easy to back up. Nothing is hidden inside the container. The `./certs` mount lets self-generated HTTPS certificates survive container rebuilds — see [Configuration → HTTPS](configuration.md#https-optional).

## Updating

```bash
cd tinysignage
git pull
docker compose up -d --build
```

Your data in `./media` and `./db` is preserved across rebuilds.

## Resource limits

The compose file sets a 512MB memory limit. This is sufficient for typical signage workloads. To adjust:

```yaml
# docker-compose.yml
services:
  signage:
    mem_limit: 1g
    memswap_limit: 1g
```

## Health check

The container includes a built-in health check that pings `/health` every 30 seconds. Check container health:

```bash
docker compose ps
```

The `STATUS` column shows `healthy` when the application is running correctly.

## Custom port

To run on a different port, change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "9090:8080"
```

Then access TinySignage at `http://localhost:9090`.

## Logs

View application logs:

```bash
docker compose logs -f signage
```

## Stopping

```bash
docker compose down
```

This stops the container but preserves all data. To remove everything including volumes:

```bash
docker compose down -v
```

## Troubleshooting

**Container won't start -- port already in use:**
Another process is using port 8080. Find it with `docker ps` or `lsof -i :8080` (Linux/macOS) and stop it, or change the port mapping.

**Build fails during npm install:**
Check your internet connection. The first build downloads Node and Python dependencies. Subsequent builds use Docker's layer cache.

**Container starts but `/setup` shows a blank page:**
Wait 10-15 seconds for the application to fully initialize. Check logs with `docker compose logs signage`.

---

## See also

- [Getting Started](getting-started.md) -- Full walkthrough from install to content
- [Configuration](configuration.md) -- config.yaml reference
- [Troubleshooting](troubleshooting.md) -- More common issues
- [Backup and Restore](backup-and-restore.md) -- Exporting your data
