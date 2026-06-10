"""Async in-process event bus.

Handlers subscribe to specific EventTypes (or to all). Publishing invokes every
matching handler; a handler raising never blocks the others or the publisher —
errors are collected and logged. This keeps side-effects (alerting, metrics,
audit, webhooks) decoupled from the core workflow.
"""
from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Union

from app.events.types import DomainEvent, EventType
from app.observability.logging import get_logger

_log = get_logger("events")

Handler = Callable[[DomainEvent], Union[None, Awaitable[None]]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)
        self._global: list[Handler] = []

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: Handler) -> None:
        self._global.append(handler)

    def handler_count(self, event_type: EventType) -> int:
        return len(self._handlers.get(event_type, [])) + len(self._global)

    async def publish(self, event: DomainEvent) -> list[Exception]:
        """Dispatch an event to all matching handlers. Returns any errors."""
        errors: list[Exception] = []
        handlers = [*self._handlers.get(event.type, []), *self._global]
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # never let one handler break the rest
                _log.error(
                    "event_handler_failed",
                    event_type=event.type.value,
                    error=str(exc),
                )
                errors.append(exc)
        return errors
