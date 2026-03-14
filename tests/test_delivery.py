from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.delivery import (
    run_delivery_tick,
    user_is_due_for_delivery,
)
from collocation_coach.storage.models import Base, DailyLesson, LessonUnit, CollocationItem, User


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
