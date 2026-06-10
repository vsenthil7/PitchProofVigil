"""Notifications package: unified event-bus assembly."""
from app.notifications.notifier import build_event_bus

__all__ = ["build_event_bus"]
