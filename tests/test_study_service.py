from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.study import (
    apply_rating,
    create_or_get_daily_lesson,
    create_or_get_review_session,
    get_next_session_card,
    record_answer,
)
from collocation_coach.storage.models import (
    Base,
    CollocationItem,
    DailyLessonItem,
    LessonUnit,
    User,
    UserCollocationProgress,
)


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


async def _seed_user_and_content(factory: async_sessionmaker):
    async with factory() as session:
        user = User(
            telegram_user_id=123,
            username="tester",
            first_name="Tester",
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
            topic="make collocations",
            source_path="test.yaml",
        )
        session.add_all([user, lesson_unit])
        await session.flush()

        items = [
            CollocationItem(
                lesson_unit_id=lesson_unit.id,
                external_key=f"item-{index}",
                phrase=f"phrase-{index}",
                translation_ru=f"перевод-{index}",
                explanation_ru=f"объяснение-{index}",
                correct_example=f"correct-{index}",
                common_mistake=f"wrong-{index}",
                mistake_explanation_ru=f"mistake-explanation-{index}",
                practice_prompt=f"practice-{index}",
                option_a=f"option-a-{index}",
                option_b=f"option-b-{index}",
                option_c=f"option-c-{index}",
                correct_option_index=1,
                tags=["tag"],
            )
            for index in range(1, 4)
        ]
        session.add_all(items)
        await session.commit()
        return user.id, [item.id for item in items]


@pytest.mark.asyncio
async def test_create_daily_lesson_includes_due_review_items_first(session_factory) -> None:
    user_id, item_ids = await _seed_user_and_content(session_factory)

    async with session_factory() as session:
        session.add(
            UserCollocationProgress(
                user_id=user_id,
                collocation_item_id=item_ids[0],
                times_seen=1,
                times_correct=1,
                stability_stage=1,
                due_at=datetime(2026, 3, 14, tzinfo=UTC),
            )
        )
        await session.commit()

    async with session_factory() as session:
        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None

        rows = list(
            (
                await session.execute(
                    select(DailyLessonItem)
                    .where(DailyLessonItem.daily_lesson_id == lesson.id)
                    .order_by(DailyLessonItem.position.asc())
                )
            ).scalars()
        )

        assert len(rows) == 4
        assert rows[0].item_type == "review"
        assert rows[1].item_type == "new"
        assert rows[2].item_type == "new"
        assert rows[3].item_type == "new"


@pytest.mark.asyncio
async def test_apply_rating_updates_progress_and_creates_review_session(session_factory) -> None:
    user_id, _ = await _seed_user_and_content(session_factory)

    async with session_factory() as session:
        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None

        card = await get_next_session_card(session, "daily", lesson.id)
        assert card is not None
        assert card.correct_option_index == 1

        recorded = await record_answer(
            session,
            "daily",
            lesson.id,
            card.session_item_id,
            selected_option_index=1,
        )
        assert recorded is not None

        summary = await apply_rating(
            session,
            user_id=user_id,
            session_type="daily",
            session_id=lesson.id,
            session_item_id=card.session_item_id,
            rating="repeat",
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert summary.total_items == 3

        progress = await session.scalar(
            select(UserCollocationProgress).where(
                UserCollocationProgress.user_id == user_id
            )
        )
        assert progress is not None
        assert progress.times_seen == 1
        assert progress.times_correct == 1
        assert progress.last_rating == "repeat"
        assert progress.due_at is not None
        assert progress.due_at.replace(tzinfo=UTC) == datetime(2026, 3, 14, tzinfo=UTC)

        review_session = await create_or_get_review_session(
            session,
            user_id=user_id,
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert review_session is not None

        review_card = await get_next_session_card(session, "review", review_session.id)
        assert review_card is not None
        assert review_card.phrase == card.phrase
