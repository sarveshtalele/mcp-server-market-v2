"""Centralised logging setup for every backend process.

Call :func:`setup_logging` once at process start (the Data API, the AG-UI agent,
the MCP server and the CLI all do). Use :func:`get_logger` everywhere else.

The log level is read from the ``LOG_LEVEL`` env var (default ``INFO``). Set
``LOG_LEVEL=DEBUG`` for verbose, developer-friendly tracing of requests, tool
calls and timings.
"""
from __future__ import annotations

import logging
import sys

from core.config import settings

_LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FORMAT = "%H:%M:%S"
_configured = False


def setup_logging(force: bool = False) -> None:
    """Configure root logging once (idempotent).

    Logs go to stderr so they never corrupt the MCP server's stdio protocol
    (which uses stdout for JSON-RPC frames).
    """
    global _configured
    if _configured and not force:
        return
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        stream=sys.stderr,
        force=True,
    )
    # Tame noisy third-party loggers unless we're explicitly debugging.
    if level > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, ensuring logging is configured first."""
    setup_logging()
    return logging.getLogger(name)
