from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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
    private_upload_dir: str = "private_uploads"

    plugins_dir: str = "plugins"

    gis_import_max_upload_mb: int = 200

    default_timezone: str = "Asia/Kolkata"
    default_currency: str = Field(default="INR", min_length=3, max_length=3)
    default_state_lgd_code: str = "32"

    ai_provider: Literal["openai", "groq"] = "openai"
    ai_model: str = "gpt-4.1-mini"
    ai_request_timeout_seconds: float = 30.0
    ai_max_output_tokens: int = 1024
    ai_max_tool_iterations: int = 8
    ai_max_retries: int = Field(default=0, ge=0)
    ai_reasoning_effort: Literal["low", "medium", "high"] | None = None

    openai_api_key: str | None = None

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"

    ws_auth_timeout_seconds: float = Field(default=10.0, gt=0)
    ws_send_timeout_seconds: float = Field(default=5.0, gt=0)
    ws_ping_interval_seconds: float = Field(default=25.0, gt=0)
    ws_max_connections_per_user: int = Field(default=5, ge=1)

    otp_length: int = 6
    otp_expire_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60

    refresh_token_expire_days: int = Field(default=30, ge=1)
    registration_token_expire_minutes: int = Field(default=15, ge=1)

    phone_otp_max_sends_per_phone_per_hour: int = Field(default=5, ge=1)
    phone_otp_max_sends_per_ip_per_hour: int = Field(default=20, ge=1)

    sms_provider: Literal["disabled", "console", "twilio"] = "disabled"
    twilio_account_sid: str | None = None
    twilio_api_key_sid: str | None = None
    twilio_api_key_secret: SecretStr | None = None
    twilio_from_number: str | None = None
    twilio_request_timeout_seconds: float = Field(default=10.0, gt=0)

    push_provider: Literal["disabled", "fcm"] = "disabled"
    fcm_project_id: str | None = None
    fcm_service_account_file: str | None = None
    fcm_request_timeout_seconds: float = Field(default=10.0, gt=0)
    push_worker_threads: int = Field(default=2, ge=1)
    fcm_web_api_key: str | None = None
    fcm_web_auth_domain: str | None = None
    fcm_web_storage_bucket: str | None = None
    fcm_web_messaging_sender_id: str | None = None
    fcm_web_app_id: str | None = None
    fcm_web_vapid_key: str | None = None

    google_client_ids: list[str] = []

    registration_allowed_email_domains: list[str] = []

    mandrill_enabled: bool = False

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    mail_from_email: str | None = None

    support_url: str | None = None
    privacy_policy_url: str | None = None
    terms_of_service_url: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _validate_push_provider(self) -> "Settings":
        if self.push_provider == "fcm":
            missing = [
                name
                for name, value in (
                    ("FCM_PROJECT_ID", self.fcm_project_id),
                    ("FCM_SERVICE_ACCOUNT_FILE", self.fcm_service_account_file),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"PUSH_PROVIDER=fcm requires {', '.join(missing)}")
        return self

    @model_validator(mode="after")
    def _validate_sms_provider(self) -> "Settings":
        if self.sms_provider == "console" and self.is_production:
            raise ValueError("SMS_PROVIDER=console is not allowed when APP_ENV=production")
        if self.sms_provider == "twilio":
            missing = [
                name
                for name, value in (
                    ("TWILIO_ACCOUNT_SID", self.twilio_account_sid),
                    ("TWILIO_API_KEY_SID", self.twilio_api_key_sid),
                    ("TWILIO_API_KEY_SECRET", self.twilio_api_key_secret),
                    ("TWILIO_FROM_NUMBER", self.twilio_from_number),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"SMS_PROVIDER=twilio requires {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
