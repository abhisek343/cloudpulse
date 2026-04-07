"""
CloudPulse AI - Cost Service
Structured logging configuration.

Provides JSON-formatted log output for production and a sanitizer
to strip potentially sensitive data from error messages before
they are persisted or returned to clients.
"""
import logging
import json
import re
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line — compatible with log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        # Propagate extras added by application code
        for key in ("request_id", "provider", "account_id", "task_type"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry, default=str)


def configure_logging(json_output: bool = False, level: str = "INFO") -> None:
    """Set up root logger with optional JSON formatting."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
        )

    root.handlers.clear()
    root.addHandler(handler)


# Patterns that may contain credentials or tokens
_SENSITIVE_PATTERNS = [
    re.compile(r"(key|secret|token|password|credential|authorization)[=:]\s*\S+(\s+\S+)?", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
]


def sanitize_error(exc: BaseException, max_length: int = 500) -> str:
    """Return a safe, truncated error message for storage or API responses."""
    msg = str(exc)
    for pattern in _SENSITIVE_PATTERNS:
        msg = pattern.sub("[REDACTED]", msg)
    if len(msg) > max_length:
        msg = msg[:max_length] + "…"
    return msg
