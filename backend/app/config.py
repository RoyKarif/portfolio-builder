from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://portfolio:portfolio@localhost:5432/portfolio_builder"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}


settings = Settings()
