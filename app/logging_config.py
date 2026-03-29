"""Three-channel logging: console, rotating file, and JSON error log."""

import json
import logging
import logging.handlers
import traceback
from datetime import datetime, timezone
from pathlib import Path


class JsonErrorHandler(logging.FileHandler):
    """Writes ERROR+ records as JSON lines to errors.jsonl."""

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["traceback"] = "".join(traceback.format_exception(*record.exc_info))
        # Request context is attached by error_handlers.py
        if hasattr(record, "request_method"):
            entry["request"] = {
                "method": record.request_method,
                "path": record.request_path,
                "client_ip": record.client_ip,
            }
        try:
            self.stream.write(json.dumps(entry) + "\n")
            self.stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(log_dir: str = "logs", level: str = "INFO") -> None:
    """Configure the three logging channels."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear any existing handlers (e.g. from basicConfig)
    root.handlers.clear()

    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    datefmt = "%H:%M:%S"

    # Channel 1: Console (stderr)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(console)

    # Channel 2: Rotating file — human-readable, 5 MB x 3 backups
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "tinysignage.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(file_handler)

    # Channel 3: JSON error lines — machine-readable, ERROR+ only
    json_handler = JsonErrorHandler(
        log_path / "errors.jsonl",
        encoding="utf-8",
    )
    json_handler.setLevel(logging.ERROR)
    root.addHandler(json_handler)
