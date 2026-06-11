"""Unit tests for the AwareDateTime column type (tz normalization)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.db.models._base import AwareDateTime


def test_bind_none_returns_none():
    assert AwareDateTime().process_bind_param(None, None) is None


def test_bind_naive_is_treated_as_utc():
    naive = datetime(2026, 6, 11, 12, 0, 0)
    out = AwareDateTime().process_bind_param(naive, None)
    assert out.tzinfo is timezone.utc
    assert out.hour == 12


def test_bind_aware_is_converted_to_utc():
    # 12:00 at +02:00 -> 10:00 UTC
    from datetime import timedelta
    plus2 = timezone(timedelta(hours=2))
    aware = datetime(2026, 6, 11, 12, 0, 0, tzinfo=plus2)
    out = AwareDateTime().process_bind_param(aware, None)
    assert out.tzinfo is timezone.utc
    assert out.hour == 10


def test_result_none_returns_none():
    assert AwareDateTime().process_result_value(None, None) is None


def test_result_naive_is_tagged_utc():
    naive = datetime(2026, 6, 11, 12, 0, 0)
    out = AwareDateTime().process_result_value(naive, None)
    assert out.tzinfo is timezone.utc
    assert out.hour == 12


def test_result_aware_is_converted_to_utc():
    from datetime import timedelta
    minus5 = timezone(timedelta(hours=-5))
    aware = datetime(2026, 6, 11, 12, 0, 0, tzinfo=minus5)
    out = AwareDateTime().process_result_value(aware, None)
    assert out.tzinfo is timezone.utc
    assert out.hour == 17
