from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.delivery import (
    run_delivery_tick,
    user_is_due_for_delivery,
)
from collocation_coach.storage.models import (
    Base,
    CollocationItem,
    DailyLesson,
    LessonUnit,
    ProductEvent,
    User,
)


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> None:
        self.messages.append((chat_id, text))


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


async def _seed_due_user(factory: async_sessionmaker) -> int:
    async with factory() as session:
        user = User(
            telegram_user_id=555,
            username="due_user",
            first_name="Due",
            language_code="ru",
            level_band="a2_b1",
            timezone="UTC",
            daily_delivery_time="09:00",
            is_active=True,
        )
        lesson_unit = LessonUnit(
            external_key="lesson-1",
            level_band="a2_b1",
            day_number=1,
            topic="topic",
            source_path="test.yaml",
        )
        session.add_all([user, lesson_unit])
        await session.flush()
        for index in range(3):
            session.add(
                CollocationItem(
                    lesson_unit_id=lesson_unit.id,
                    external_key=f"item-{index}",
                    phrase=f"phrase-{index}",
                    translation_ru=f"translation-{index}",
                    explanation_ru=f"explanation-{index}",
                    correct_example=f"correct-{index}",
                    common_mistake=f"mistake-{index}",
                    mistake_explanation_ru=f"mistake-explanation-{index}",
                    practice_prompt=f"prompt-{index}",
                    option_a=f"a-{index}",
                    option_b=f"b-{index}",
                    option_c=f"c-{index}",
                    correct_option_index=0,
                    tags=["tag"],
                )
            )
        await session.commit()
        return user.id


async def _seed_lapsed_due_user(factory: async_sessionmaker) -> int:
    user_id = await _seed_due_user(factory)
    async with factory() as session:
        lesson = await session.scalar(select(DailyLesson))
        assert lesson is None
        first_unit = await session.scalar(select(LessonUnit).limit(1))
        assert first_unit is not None
        session.add(
            DailyLesson(
                user_id=user_id,
                lesson_date=datetime(2026, 3, 11, 9, 0, tzinfo=UTC).date(),
                lesson_unit_id=first_unit.id,
                status="completed",
                completed_at=datetime(2026, 3, 11, 9, 5, tzinfo=UTC),
            )
        )
        await session.commit()
    return user_id


def test_user_is_due_for_delivery_matches_local_minute() -> None:
    user = User(
        telegram_user_id=1,
        username="u",
        first_name="u",
        language_code="ru",
        level_band="a2_b1",
        timezone="UTC",
        daily_delivery_time="09:00",
        is_active=True,
    )
    assert user_is_due_for_delivery(user, datetime(2026, 3, 15, 9, 0, tzinfo=UTC))
    assert not user_is_due_for_delivery(user, datetime(2026, 3, 15, 9, 1, tzinfo=UTC))


@pytest.mark.asyncio
async def test_delivery_tick_sends_once_per_day(session_factory) -> None:
    await _seed_due_user(session_factory)
    bot = FakeBot()
    now = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)

    delivered_count = await run_delivery_tick(bot, session_factory, now)
    assert delivered_count == 1
    assert len(bot.messages) == 2

    delivered_count = await run_delivery_tick(bot, session_factory, now)
    assert delivered_count == 0
    assert len(bot.messages) == 2

    async with session_factory() as session:
        lesson = await session.scalar(select(DailyLesson))
        assert lesson is not None
        assert lesson.delivered_at is not None


@pytest.mark.asyncio
async def test_delivery_tick_shows_return_prompt_for_lapsed_user(session_factory) -> None:
    await _seed_lapsed_due_user(session_factory)
    bot = FakeBot()
    now = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)

    delivered_count = await run_delivery_tick(bot, session_factory, now)

    assert delivered_count == 1
    assert len(bot.messages) == 3
    assert bot.messages[0][1].startswith("Welcome back.")

    async with session_factory() as session:
        lesson = await session.scalar(
            select(DailyLesson).where(DailyLesson.lesson_date == datetime(2026, 3, 15, 9, 0, tzinfo=UTC).date())
        )
        assert lesson is not None
        assert lesson.return_mode_applied is True

        event_names = set(
            (
                await session.execute(
                    select(ProductEvent.event_name).where(ProductEvent.user_id == lesson.user_id)
                )
            ).scalars()
        )
        assert "return_prompt_shown" in event_names
        assert "daily_lesson_started" in event_names
