from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env.

    Laravel equivalent: the combination of `.env` + `config/app.php` +
    `config('app.debug')` helper calls, but type-checked at startup instead
    of read ad-hoc as untyped strings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Native Life API"
    app_env: str = "local"
    debug: bool = False

    api_v1_prefix: str = "/api/v1"

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    FastAPI route handlers will depend on this via `Depends(get_settings)`
    rather than importing a module-level singleton, so tests can override it.
    `lru_cache` (not a plain global) makes the override behave correctly with
    FastAPI's dependency_overrides mechanism.
    """
    return Settings()
