from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_origin: str = "http://127.0.0.1:8000"
    database_url: SecretStr
    # 직접 SQL 연결에서는 사용하지 않으며, 로그에 키가 노출되지 않게 합니다.
    supabase_url: str | None = None
    supabase_key: SecretStr | None = None
    secret_key: SecretStr
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)
    cookie_secure: bool = False

    @field_validator("app_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("APP_ORIGIN은 경로와 끝의 /가 없는 http(s) 주소여야 합니다.")
        # 잘못된 포트도 설정 단계에서 거부합니다.
        _ = parsed.port
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not raw.startswith(("postgresql://", "postgres://")) or "YOUR_" in raw:
            raise ValueError("DATABASE_URL에 실제 Supabase PostgreSQL URI를 입력하세요.")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if len(raw) < 32 or raw.startswith("CHANGE_ME"):
            raise ValueError("SECRET_KEY에 32자 이상의 무작위 비밀키를 입력하세요.")
        return value

    @model_validator(mode="after")
    def require_secure_cookie_for_https(self) -> "Settings":
        if self.app_origin.startswith("https://") and not self.cookie_secure:
            raise ValueError("HTTPS 환경에서는 COOKIE_SECURE=true로 설정하세요.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
