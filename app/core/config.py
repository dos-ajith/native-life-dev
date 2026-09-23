from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    upload_dir: str = "uploads"

    gis_import_max_upload_mb: int = 200

    default_timezone: str = "Asia/Kolkata"

    ai_provider: Literal["openai", "groq"] = "openai"
    ai_model: str = "gpt-4.1-mini"
    ai_request_timeout_seconds: float = 30.0
    ai_max_output_tokens: int = 1024
    ai_max_tool_iterations: int = 8

    openai_api_key: str | None = None

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
