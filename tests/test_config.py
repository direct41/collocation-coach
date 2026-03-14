from pathlib import Path

import pytest

from collocation_coach.config import Settings


def test_settings_loads_valid_configuration(tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()

    settings = Settings(
        TELEGRAM_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/app",
        CONTENT_DIR=content_dir,
    )

    assert settings.log_level == "INFO"
    assert settings.content_dir == content_dir


def test_settings_rejects_missing_content_dir(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"

    with pytest.raises(ValueError, match="CONTENT_DIR does not exist"):
        Settings(
            TELEGRAM_BOT_TOKEN="token",
            DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/app",
            CONTENT_DIR=missing_dir,
        )
