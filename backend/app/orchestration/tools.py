"""Agent tool framework.

A ``Tool`` is a named, typed capability the orchestrator can invoke. Each tool
declares a JSON-schema-ish parameter spec (for LLM function-calling and for
validation), executes synchronously, and reports its own latency. Tools never
raise for expected failures — they return a ``ToolResult`` with ok=False so the
orchestrator can decide whether to retry or degrade.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    name: str
    type: str  # "string" | "integer" | "number" | "boolean"
    description: str
    required: bool = True


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: float = 0.0
    tool: str = ""

    @classmethod
    def success(cls, tool: str, **data: Any) -> "ToolResult":
        return cls(ok=True, data=data, tool=tool)

    @classmethod
    def failure(cls, tool: str, error: str) -> "ToolResult":
        return cls(ok=False, error=error, tool=tool)


class Tool(abc.ABC):
    name: str
    description: str
    params: tuple[ToolParam, ...] = ()

    @abc.abstractmethod
    def _execute(self, **kwargs: Any) -> ToolResult:
        """Concrete tool logic. Return ToolResult; do not raise for expected
        failures."""

    def invoke(self, **kwargs: Any) -> ToolResult:
        """Validate params, execute with timing, normalize errors."""
        missing = [
            p.name for p in self.params if p.required and p.name not in kwargs
        ]
        if missing:
            return ToolResult.failure(
                self.name, f"Missing required parameter(s): {', '.join(missing)}"
            )
        start = time.perf_counter()
        try:
            result = self._execute(**kwargs)
        except Exception as exc:  # tool bug → failure, never crash orchestrator
            result = ToolResult.failure(self.name, f"{type(exc).__name__}: {exc}")
        result.tool = self.name
        result.latency_ms = (time.perf_counter() - start) * 1000.0
        return result

    def schema(self) -> dict[str, Any]:
        """Function-calling style schema for LLM tool use."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    p.name: {"type": p.type, "description": p.description}
                    for p in self.params
                },
                "required": [p.name for p in self.params if p.required],
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools
