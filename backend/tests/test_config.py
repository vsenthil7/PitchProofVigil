"""Tests for app.core.config."""
from __future__ import annotations

import importlib

import app.core.config as config_module
from app.core.config import Settings, get_settings


def test_bool_parsing(monkeypatch):
    monkeypatch.setenv("USE_MOCKS", "TRUE")
    assert Settings().use_mocks is True
    monkeypatch.setenv("USE_MOCKS", "off")
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    assert Settings().use_mocks is False
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("USE_MOCKS", raising=False)
    assert Settings().use_mocks is True  # default


def test_bool_default_false(monkeypatch):
    from app.core.config import _bool

    monkeypatch.delenv("NOPE", raising=False)
    assert _bool("NOPE", False) is False


def test_gemini_available_requires_project_and_no_mocks():
    s = Settings(use_mocks=False, jwt_secret="a"*64, google_cloud_project="p")
    assert s.gemini_available is True
    assert s.integration_mode("gemini") == "real"

    s2 = Settings(use_mocks=True, google_cloud_project="p")
    assert s2.gemini_available is False
    assert s2.integration_mode("gemini") == "mock"


def test_arize_ax_available():
    s = Settings(use_mocks=False, jwt_secret="a"*64, arize_api_key="k", arize_space_id="sp")
    assert s.arize_ax_available is True
    assert s.integration_mode("arize_ax") == "real"
    s2 = Settings(use_mocks=False, jwt_secret="a"*64)
    assert s2.arize_ax_available is False


def test_phoenix_mode():
    assert Settings(use_mocks=False, jwt_secret="a"*64).integration_mode("phoenix") == "real"
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


# ---- P1: security guards + CORS wiring ----

def test_jwt_secret_guard_blocks_default_in_real_mode():
    import pytest
    from app.core.config import Settings
    with pytest.raises(ValueError, match="JWT_SECRET must be set"):
        Settings(use_mocks=False, jwt_secret="dev-insecure-secret-change-me")


def test_jwt_secret_guard_passes_in_mock_mode():
    from app.core.config import Settings
    s = Settings(use_mocks=True, jwt_secret="dev-insecure-secret-change-me")
    assert s.jwt_secret == "dev-insecure-secret-change-me"


def test_cors_guard_blocks_wildcard_in_real_mode():
    import pytest
    from app.core.config import Settings
    with pytest.raises(ValueError, match="CORS_ORIGINS='\\*'"):
        Settings(use_mocks=False, jwt_secret="a" * 64, cors_origins=["*"])


def test_cors_origins_parses_from_list():
    from app.core.config import Settings
    s = Settings(cors_origins=["https://app.example.com", "https://staging.example.com"])
    assert "https://app.example.com" in s.cors_origins


def test_cors_origins_default_is_localhost():
    import os
    from app.core.config import Settings
    os.environ.pop("CORS_ORIGINS", None)
    s = Settings()
    assert "http://localhost:8080" in s.cors_origins


def test_redis_url_defaults_to_none():
    import os
    from app.core.config import Settings
    os.environ.pop("REDIS_URL", None)
    s = Settings()
    assert s.redis_url is None


def test_create_app_uses_settings_cors():
    """app.py must pass settings.cors_origins, not a hard-coded wildcard."""
    import app.api.app as app_mod
    from app.core.config import Settings
    s = Settings(cors_origins=["https://test.example.com"])
    application = app_mod.create_app(settings=s, create_schema=False)
    for mw in application.user_middleware:
        cls = getattr(mw, "cls", None)
        kwargs = getattr(mw, "kwargs", {})
        if cls is not None and "CORS" in cls.__name__:
            assert "https://test.example.com" in kwargs.get("allow_origins", [])
            assert "*" not in kwargs.get("allow_origins", [])
            return
    raise AssertionError("CORSMiddleware not found in middleware stack")
