from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_audience: str | None = None
    jwt_issuer: str | None = None

    # CORS
    cors_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True

    # Rate limiting — slowapi format: "N/second|minute|hour"
    rate_limit_default: str = "100/minute"

    # Downstream HTTP client
    downstream_timeout_seconds: float = 10.0
    downstream_max_retries: int = 3
    downstream_retry_backoff: float = 0.5  # base seconds for exponential backoff

    # Service routing: map path prefix -> base URL
    # Set via env vars like: SERVICES__movies=http://movies-service:8000
    services: dict[str, str] = {}

    # Paths that bypass JWT validation (prefix-matched)
    public_paths: list[str] = ["/auth/login", "/auth/register", "/auth/refresh", "/recommendations"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
