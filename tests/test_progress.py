from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.progress import build_progress_snapshot
from collocation_coach.storage.models import (
    Base,
    CollocationItem,
    DailyLesson,
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


@pytest.mark.asyncio
async def test_build_progress_snapshot_returns_phase_5_metrics(session_factory) -> None:
    async with session_factory() as session:
        user = User(
            telegram_user_id=321,
            username="progress_user",
            first_name="Progress",
            language_code="ru",
            level_band="a2_b1",
            timezone="UTC",
            daily_delivery_time="09:00",
            pace_mode="light",
            is_active=True,
        )
        first_unit = LessonUnit(
            external_key="lesson-1",
            level_band="a2_b1",
            day_number=1,
            topic="unit 1",
            source_path="unit-1.yaml",
        )
        second_unit = LessonUnit(
            external_key="lesson-2",
            level_band="a2_b1",
            day_number=2,
            topic="unit 2",
            source_path="unit-2.yaml",
        )
        session.add_all([user, first_unit, second_unit])
        await session.flush()

        first_unit_items = []
        second_unit_items = []
        for unit, target in ((first_unit, first_unit_items), (second_unit, second_unit_items)):
            for index in range(3):
                item = CollocationItem(
                    lesson_unit_id=unit.id,
                    external_key=f"{unit.external_key}-item-{index}",
                    phrase=f"phrase-{unit.id}-{index}",
                    translation_ru=f"перевод-{unit.id}-{index}",
                    explanation_ru=f"объяснение-{unit.id}-{index}",
                    correct_example=f"correct-{unit.id}-{index}",
                    common_mistake=f"mistake-{unit.id}-{index}",
                    mistake_explanation_ru=f"mistake-explanation-{unit.id}-{index}",
                    practice_prompt=f"prompt-{unit.id}-{index}",
                    option_a=f"a-{unit.id}-{index}",
                    option_b=f"b-{unit.id}-{index}",
                    option_c=f"c-{unit.id}-{index}",
                    correct_option_index=0,
                    tags=["tag"],
                )
                session.add(item)
                await session.flush()
                target.append(item.id)

        session.add_all(
            [
                DailyLesson(
                    user_id=user.id,
                    lesson_date=date(2026, 3, 12),
                    lesson_unit_id=first_unit.id,
                    status="completed",
                ),
                DailyLesson(
                    user_id=user.id,
                    lesson_date=date(2026, 3, 14),
                    lesson_unit_id=second_unit.id,
                    status="completed",
                ),
            ]
        )
        session.add_all(
            [
                UserCollocationProgress(
                    user_id=user.id,
                    collocation_item_id=item_id,
                    times_seen=1,
                    times_correct=1,
                    last_seen_at=datetime(2026, 3, 14, tzinfo=UTC),
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                )
                for item_id in first_unit_items
            ]
        )
        session.add_all(
            [
                UserCollocationProgress(
                    user_id=user.id,
                    collocation_item_id=item_id,
                    times_seen=1,
                    times_correct=0,
                    last_seen_at=datetime(2026, 3, 14, tzinfo=UTC),
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                )
                for item_id in second_unit_items
            ]
        )
        await session.commit()

        snapshot = await build_progress_snapshot(
            session,
            user,
            now_utc=datetime(2026, 3, 14, 12, 0, tzinfo=UTC),
        )

        assert snapshot.lessons_completed_last_7_days == 2
        assert snapshot.pace_mode == "light"
        assert snapshot.review_backlog_bucket == "6-15"
        assert snapshot.completed_units == 2
        assert snapshot.total_units == 2
