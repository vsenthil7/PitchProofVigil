"""Central configuration for PitchProof Vigil.

Single source of truth for credentials and the mock/real switch. Every
integration (Gemini, Phoenix, Arize AX) reads from here and degrades to a
mock implementation when its credentials are absent, so the system runs
end-to-end on a laptop and switches to real services the moment Claude
Desktop is granted access.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    # Global mock switch. When True, every integration uses its mock path.
    # When False, integrations require real credentials and raise if absent.
    use_mocks: bool = field(default_factory=lambda: _bool("USE_MOCKS", True))

    # Google Cloud / Gemini
    google_cloud_project: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    google_application_credentials: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )
    agent_builder_app_id: str | None = field(
        default_factory=lambda: os.getenv("AGENT_BUILDER_APP_ID")
    )

    # Arize Phoenix
    phoenix_collector_endpoint: str = field(
        default_factory=lambda: os.getenv(
            "PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006"
        )
    )
    phoenix_api_key: str | None = field(
        default_factory=lambda: os.getenv("PHOENIX_API_KEY")
    )

    # Arize AX (optional, production evals)
    arize_api_key: str | None = field(
        default_factory=lambda: os.getenv("ARIZE_API_KEY")
    )
    arize_space_id: str | None = field(
        default_factory=lambda: os.getenv("ARIZE_SPACE_ID")
    )

    # Eval gate
    regression_threshold: float = field(
        default_factory=lambda: float(os.getenv("REGRESSION_THRESHOLD", "0.85"))
    )

    # Database
    database_dsn: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_DSN", "sqlite+aiosqlite:///./pitchproof.db"
        )
    )
    db_echo: bool = field(default_factory=lambda: _bool("DB_ECHO", False))

    # Auth / security
    jwt_secret: str = field(
        default_factory=lambda: os.getenv("JWT_SECRET", "dev-insecure-secret-change-me")
    )
    jwt_algorithm: str = field(
        default_factory=lambda: os.getenv("JWT_ALGORITHM", "HS256")
    )
    access_token_ttl_minutes: int = field(
        default_factory=lambda: int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "60"))
    )
    api_key_prefix: str = field(
        default_factory=lambda: os.getenv("API_KEY_PREFIX", "ppv")
    )
    rate_limit_capacity: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_CAPACITY", "120"))
    )
    rate_limit_refill_per_second: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_REFILL_PER_SECOND", "10"))
    )
    encryption_keys: str = field(
        default_factory=lambda: os.getenv("ENCRYPTION_KEYS", "")
    )

    @property
    def gemini_available(self) -> bool:
        return bool(self.google_cloud_project) and not self.use_mocks

    @property
    def arize_ax_available(self) -> bool:
        return bool(self.arize_api_key and self.arize_space_id) and not self.use_mocks

    def integration_mode(self, integration: str) -> str:
        """Return 'real' or 'mock' for a named integration."""
        mapping = {
            "gemini": self.gemini_available,
            "arize_ax": self.arize_ax_available,
            # Phoenix can run locally via Docker, treated as real unless mocks forced.
            "phoenix": not self.use_mocks,
        }
        return "real" if mapping.get(integration, False) else "mock"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
