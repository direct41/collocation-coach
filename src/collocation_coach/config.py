from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    default_locale: str = Field(default="ru", alias="DEFAULT_LOCALE")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    content_dir: Path = Field(default=Path("content/lessons"), alias="CONTENT_DIR")
    delivery_batch_size: int = Field(default=100, alias="DELIVERY_BATCH_SIZE")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("content_dir")
    @classmethod
    def validate_content_dir(cls, value: Path) -> Path:
        path = value.expanduser()
        if not path.exists():
            raise ValueError(f"CONTENT_DIR does not exist: {path}")
        return path


def load_settings() -> Settings:
    return Settings()
