"""Shared test fixtures."""
from __future__ import annotations

import pytest

# Re-export database fixtures so DB-backed tests can use them.
from tests.db_conftest import db, tenant_id  # noqa: F401
from tests.api_conftest import api_settings, client, owner_auth  # noqa: F401

from app.core.config import Settings
from app.core.models import ConciergeRequest, Language


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(use_mocks=True)


@pytest.fixture
def real_settings() -> Settings:
    """Settings that report 'real' modes without real network calls.

    Used to exercise the real-path branches with patched SDKs.
    """
    return Settings(
        use_mocks=False,
        google_cloud_project="test-project",
        arize_api_key="test-key",
        arize_space_id="test-space",
    )


@pytest.fixture
def spain_germany_request() -> ConciergeRequest:
    return ConciergeRequest(text="When does Spain play Germany?", language=Language.EN)
