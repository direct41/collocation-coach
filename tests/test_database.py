from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from collocation_coach.storage.database import Database


@pytest.mark.asyncio
async def test_initialize_adds_missing_pace_mode_column(tmp_path: Path) -> None:
    database_path = tmp_path / "upgrade.sqlite"
    database_url = f"sqlite+aiosqlite:///{database_path}"

    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    telegram_user_id BIGINT UNIQUE,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    language_code VARCHAR(32),
                    level_band VARCHAR(32),
                    timezone VARCHAR(64),
                    daily_delivery_time VARCHAR(5),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    await engine.dispose()

    database = Database(database_url)
    await database.initialize()

    async with database.engine.begin() as connection:
        columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"] for column in inspect(sync_connection).get_columns("users")
            }
        )

    await database.dispose()
    assert "pace_mode" in columns
