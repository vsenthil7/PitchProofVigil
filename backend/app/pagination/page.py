"""Reusable pagination primitives.

``PageParams`` validates and normalizes limit/offset. ``Page`` wraps a result
slice with the metadata a client needs to page through (total, has_more, next
offset). Kept storage-agnostic so repositories and routers share one shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


@dataclass(frozen=True)
class PageParams:
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    @classmethod
    def of(cls, limit: int | None = None, offset: int | None = None) -> "PageParams":
        lim = DEFAULT_LIMIT if limit is None else limit
        off = 0 if offset is None else offset
        lim = max(1, min(MAX_LIMIT, lim))
        off = max(0, off)
        return cls(limit=lim, offset=off)


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    @property
    def next_offset(self) -> int | None:
        return self.offset + self.limit if self.has_more else None

    def meta(self) -> dict:
        return {
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
            "next_offset": self.next_offset,
        }


def paginate(items: list[T], total: int, params: PageParams) -> Page[T]:
    return Page(items=items, total=total, limit=params.limit, offset=params.offset)
