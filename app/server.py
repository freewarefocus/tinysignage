"""Programmatic uvicorn entry point for TinySignage.

Reads ``config.yaml``, decides whether to enable TLS, generates a
self-signed cert on first boot if requested, and calls ``uvicorn.run``
with the right arguments. All startup tooling (Docker, systemd,
launchd, Windows batch, ``launcher.py``) invokes this via
``python -m app.server`` so HTTPS logic lives in exactly one place.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import uvicorn
import yaml

from app.tls import ensure_cert

log = logging.getLogger(__name__)

_CONFIG_PATH = Path("config.yaml")


def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(_CONFIG_PATH.read_text()) or {}
    except Exception as e:  # pragma: no cover
        print(f"ERROR: could not parse {_CONFIG_PATH}: {e}", file=sys.stderr)
        return {}


def main() -> None:
    config = _load_config()
    server_cfg = config.get("server", {}) or {}
    host = server_cfg.get("host", "0.0.0.0")
    port = int(server_cfg.get("port", 8080))

    https_cfg = server_cfg.get("https", {}) or {}
    https_enabled = bool(https_cfg.get("enabled", False))

    ssl_kwargs: dict = {}
    if https_enabled:
        cert_file = Path(https_cfg.get("cert_file", "./certs/cert.pem"))
        key_file = Path(https_cfg.get("key_file", "./certs/key.pem"))
        auto_gen = bool(https_cfg.get("auto_generate_self_signed", True))

        if auto_gen:
            try:
                ensure_cert(cert_file, key_file)
            except Exception as e:
                print(
                    f"ERROR: failed to generate self-signed certificate: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

        if not cert_file.exists() or not key_file.exists():
            print(
                f"ERROR: HTTPS is enabled but cert/key not found "
                f"({cert_file}, {key_file}). "
                f"Set server.https.auto_generate_self_signed: true or "
                f"provide your own cert files.",
                file=sys.stderr,
            )
            sys.exit(1)

        ssl_kwargs["ssl_certfile"] = str(cert_file)
        ssl_kwargs["ssl_keyfile"] = str(key_file)
        print(
            f"TinySignage: HTTPS enabled on https://{host}:{port}",
            file=sys.stderr,
        )
    else:
        print(
            f"TinySignage: HTTP mode on http://{host}:{port}",
            file=sys.stderr,
        )

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        **ssl_kwargs,
    )


if __name__ == "__main__":
    main()
