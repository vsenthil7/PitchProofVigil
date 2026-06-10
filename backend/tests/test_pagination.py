"""Tests for the pagination utility."""
from __future__ import annotations

from app.pagination.page import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    Page,
    PageParams,
    paginate,
)


def test_params_defaults():
    p = PageParams.of()
    assert p.limit == DEFAULT_LIMIT
    assert p.offset == 0


def test_params_clamps_limit():
    assert PageParams.of(limit=99999).limit == MAX_LIMIT
    assert PageParams.of(limit=0).limit == 1
    assert PageParams.of(offset=-5).offset == 0


def test_params_passthrough():
    p = PageParams.of(limit=25, offset=50)
    assert p.limit == 25 and p.offset == 50


def test_page_has_more_and_next():
    page = paginate(items=list(range(10)), total=100, params=PageParams.of(limit=10, offset=0))
    assert page.has_more is True
    assert page.next_offset == 10


def test_page_last_page():
    page = paginate(items=list(range(5)), total=25, params=PageParams.of(limit=10, offset=20))
    assert page.has_more is False
    assert page.next_offset is None


def test_page_meta():
    page = Page(items=[1, 2], total=10, limit=2, offset=0)
    meta = page.meta()
    assert meta["total"] == 10
    assert meta["has_more"] is True
    assert meta["next_offset"] == 2
