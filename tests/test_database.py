from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from collocation_coach.storage.database import Database


@pytest.mark.asyncio
async def test_initialize_adds_phase_5_columns_and_event_table(tmp_path: Path) -> None:
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
        await connection.execute(
            text(
                """
                CREATE TABLE daily_lessons (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    lesson_date DATE NOT NULL,
                    lesson_unit_id INTEGER,
                    status VARCHAR(32) NOT NULL DEFAULT 'in_progress',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    delivered_at DATETIME,
                    completed_at DATETIME
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
        daily_lesson_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"] for column in inspect(sync_connection).get_columns("daily_lessons")
            }
        )
        product_event_tables = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names())
        )

    await database.dispose()
    assert "pace_mode" in columns
    assert "return_mode_started_at" in columns
    assert "return_mode_until" in columns
    assert "return_mode_lessons_remaining" in columns
    assert "return_mode_applied" in daily_lesson_columns
    assert "product_events" in product_event_tables
    assert "content_feedback" in product_event_tables
