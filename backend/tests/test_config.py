"""Tests for app.core.config."""
from __future__ import annotations

import importlib

import app.core.config as config_module
from app.core.config import Settings, get_settings


def test_bool_parsing(monkeypatch):
    monkeypatch.setenv("USE_MOCKS", "TRUE")
    assert Settings().use_mocks is True
    monkeypatch.setenv("USE_MOCKS", "off")
    assert Settings().use_mocks is False
    monkeypatch.delenv("USE_MOCKS", raising=False)
    assert Settings().use_mocks is True  # default


def test_bool_default_false(monkeypatch):
    from app.core.config import _bool

    monkeypatch.delenv("NOPE", raising=False)
    assert _bool("NOPE", False) is False


def test_gemini_available_requires_project_and_no_mocks():
    s = Settings(use_mocks=False, google_cloud_project="p")
    assert s.gemini_available is True
    assert s.integration_mode("gemini") == "real"

    s2 = Settings(use_mocks=True, google_cloud_project="p")
    assert s2.gemini_available is False
    assert s2.integration_mode("gemini") == "mock"


def test_arize_ax_available():
    s = Settings(use_mocks=False, arize_api_key="k", arize_space_id="sp")
    assert s.arize_ax_available is True
    assert s.integration_mode("arize_ax") == "real"
    s2 = Settings(use_mocks=False)
    assert s2.arize_ax_available is False


def test_phoenix_mode():
    assert Settings(use_mocks=False).integration_mode("phoenix") == "real"
    assert Settings(use_mocks=True).integration_mode("phoenix") == "mock"


def test_unknown_integration_defaults_mock():
    assert Settings().integration_mode("nonexistent") == "mock"


def test_get_settings_cached():
    importlib.reload(config_module)
    a = config_module.get_settings()
    b = config_module.get_settings()
    assert a is b


def test_regression_threshold_env(monkeypatch):
    monkeypatch.setenv("REGRESSION_THRESHOLD", "0.9")
    assert Settings().regression_threshold == 0.9
