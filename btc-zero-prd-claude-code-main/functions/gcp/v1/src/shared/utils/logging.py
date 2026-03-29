"""Structured JSON logging for Cloud Run.

Cloud Logging expects JSON-formatted logs on stdout.
This module provides a formatter that outputs structured JSON
with proper severity levels and extra fields.
"""

import json
import logging
import sys
from typing import Any


class StructuredLogFormatter(logging.Formatter):
    """Format logs as JSON for Cloud Logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string for Cloud Logging
        """
        log_entry: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": self.formatTime(record),
        }

        extra_fields = [
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "message",
            "taskName",
        ]

        for key, value in record.__dict__.items():
            if key not in extra_fields:
                try:
                    json.dumps(value)
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for Cloud Run.

    Sets up the root logger with:
    - JSON formatter for Cloud Logging
    - stdout handler
    - Specified log level

    Args:
        level: Logging level (default: INFO)
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
