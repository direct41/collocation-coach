from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.events import record_product_event, summarize_product_events
from collocation_coach.storage.models import Base, User


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_record_product_event_deduplicates_by_event_key(session_factory) -> None:
    async with session_factory() as session:
        user = User(
            telegram_user_id=999,
            username="events",
            first_name="Events",
            language_code="ru",
            level_band="a2_b1",
            timezone="UTC",
            daily_delivery_time="09:00",
            is_active=True,
        )
        session.add(user)
        await session.commit()

        inserted = await record_product_event(
            session,
            user.id,
            "daily_lesson_started",
            occurred_at=datetime(2026, 3, 14, tzinfo=UTC),
            event_key="daily-lesson-started:1",
        )
        inserted_again = await record_product_event(
            session,
            user.id,
            "daily_lesson_started",
            occurred_at=datetime(2026, 3, 14, tzinfo=UTC),
            event_key="daily-lesson-started:1",
        )
        await session.commit()

        assert inserted is True
        assert inserted_again is False


@pytest.mark.asyncio
async def test_summarize_product_events_reports_return_conversion(session_factory) -> None:
    async with session_factory() as session:
        user = User(
            telegram_user_id=1000,
            username="summary",
            first_name="Summary",
            language_code="ru",
            level_band="a2_b1",
            timezone="UTC",
            daily_delivery_time="09:00",
            is_active=True,
        )
        session.add(user)
        await session.commit()

        await record_product_event(
            session,
            user.id,
            "return_prompt_shown",
            occurred_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
        )
        await record_product_event(
            session,
            user.id,
            "daily_lesson_completed",
            occurred_at=datetime(2026, 3, 11, 9, 0, tzinfo=UTC),
        )
        await session.commit()

        summary = await summarize_product_events(
            session,
            now=datetime(2026, 3, 14, 9, 0, tzinfo=UTC),
        )

        counts = {row.event_name: row.total_count for row in summary.counts}
        assert counts["return_prompt_shown"] == 1
        assert counts["daily_lesson_completed"] == 1
        assert summary.return_prompts == 1
        assert summary.return_completions_within_72h == 1
