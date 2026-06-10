"""Shared test fixtures."""
from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.context import AppContext
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
def context(mock_settings: Settings) -> AppContext:
    return AppContext(mock_settings)


@pytest.fixture
def spain_germany_request() -> ConciergeRequest:
    return ConciergeRequest(text="When does Spain play Germany?", language=Language.EN)
