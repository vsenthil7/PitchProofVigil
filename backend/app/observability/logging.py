"""Structured logging via structlog.

Emits JSON logs in production (machine-parseable for log aggregation) and
pretty console logs in dev. A request-scoped context (request_id, tenant_id)
can be bound so every log line within a request is correlated.
"""
from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def configure_logging(json_logs: bool = True, level: str = "INFO") -> None:
    """Configure structlog + stdlib logging once."""
    global _configured
    if _configured:
        return

    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=getattr(logging, level, logging.INFO)
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "pitchproof"):
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)


def bind_request_context(**kwargs) -> None:
    """Bind correlation fields for the current async context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
