"""Application configuration loaded from environment variables.

Single source of truth for all settings. Anything that comes from
the environment goes here, then code reads `from app.config import settings`.

Why Pydantic Settings (and not os.getenv): types are validated at startup.
If JWT_SECRET is missing, the app fails *immediately* on boot — not in
the middle of a request three hours later. This is the "fail fast"
principle.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings. Read from env vars or .env file.

    Each field becomes a Settings attribute. Pydantic enforces the type:
    if ACCESS_TOKEN_EXPIRE_MINUTES is set to "abc" in .env, boot fails
    with a clear validation error.
    """

    # --- Database ---
    DATABASE_URL: str

    # --- JWT ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # SettingsConfigDict tells Pydantic where to find the .env file
    # and how to behave. case_sensitive=True means JWT_SECRET (caps)
    # and not jwt_secret.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # ignore env vars we don't declare here
    )


# Module-level singleton — every importer gets the same instance.
# Computed at import time, so missing env vars crash on boot.
settings = Settings()
