"""Shared helpers for correctness evaluators."""
from __future__ import annotations

import re

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
