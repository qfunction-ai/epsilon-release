"""Application configuration for Epsilon backend.

Uses pydantic-settings to load configuration from environment variables
and/or a .env file. Secrets (SECRET_KEY) are auto-generated on first run
if not explicitly provided, ensuring the app works out-of-the-box for
local development while remaining secure by default.
"""

import logging
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Epsilon application settings.

    All values can be overridden via environment variables or a .env file.
    Sensible defaults are provided for local development.
    """

    # --- LettaLocal ---
    LETTA_URL: str = "http://localhost:8283"

    # --- Ollama ---
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "ollama/nemotron-3-nano:4b"

    # --- Embedding ---
    LETTA_EMBEDDING_MODEL: str = "ollama/embeddinggemma:latest"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://epsilon:epsilon@localhost:5432/epsilon"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth / JWT ---
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- CORS ---
    # Comma-separated list of allowed origins for the frontend.
    # Parsed into a list by get_cors_origins().
    CORS_ORIGINS: str = "http://localhost:5173"

    # --- Dev mode ---
    # Controls cookie security: when False, JWT cookie is secure-only (production).
    # When True, cookie is non-secure (local dev over HTTP).
    DEV_MODE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_cors_origin_list(self) -> list[str]:
        """Parse the comma-separated CORS_ORIGINS string into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    SECRET_KEY is auto-generated using secrets.token_urlsafe(32) if not
    explicitly set in the environment or .env file. A warning is logged so
    the operator knows to set it for production deployments.
    """
    settings = Settings()

    if not settings.SECRET_KEY:
        settings.SECRET_KEY = secrets.token_urlsafe(32)
        logger.warning(
            "SECRET_KEY not set — auto-generated a random key. "
            "Set SECRET_KEY in .env for production deployments to persist "
            "tokens across restarts."
        )

    return settings


def get_cors_origins() -> list[str]:
    """Convenience function to get parsed CORS origins list."""
    return get_settings().get_cors_origin_list()
