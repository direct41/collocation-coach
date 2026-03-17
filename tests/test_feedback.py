from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.feedback import (
    feedback_rows_to_csv,
    feedback_rows_to_jsonl,
    load_feedback_export_rows,
    submit_content_feedback,
)
from collocation_coach.storage.models import (
    Base,
    CollocationItem,
    ContentFeedback,
    LessonUnit,
    ProductEvent,
    User,
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


async def _seed_feedback_target(factory: async_sessionmaker) -> tuple[int, int]:
    async with factory() as session:
        user = User(
            telegram_user_id=111,
            username="feedback",
            first_name="Feedback",
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
            topic="feedback unit",
            source_path="feedback.yaml",
        )
        session.add_all([user, lesson_unit])
        await session.flush()
        item = CollocationItem(
            lesson_unit_id=lesson_unit.id,
            external_key="feedback-item",
            phrase="take action",
            translation_ru="предпринять действие",
            explanation_ru="объяснение",
            correct_example="take action now",
            common_mistake="do action",
            mistake_explanation_ru="ошибка",
            practice_prompt="choose the best option",
            option_a="take action",
            option_b="do action",
            option_c="make action",
            correct_option_index=0,
            tags=["tag"],
        )
        session.add(item)
        await session.commit()
        return user.id, item.id


@pytest.mark.asyncio
async def test_submit_content_feedback_is_idempotent_per_session_item(session_factory) -> None:
    user_id, item_id = await _seed_feedback_target(session_factory)

    async with session_factory() as session:
        created = await submit_content_feedback(
            session,
            user_id=user_id,
            collocation_item_id=item_id,
            feedback_type="wrong_or_broken",
            session_type="daily",
            session_id=10,
            session_item_id=99,
            now=datetime(2026, 3, 17, tzinfo=UTC),
        )
        created_again = await submit_content_feedback(
            session,
            user_id=user_id,
            collocation_item_id=item_id,
            feedback_type="wrong_or_broken",
            session_type="daily",
            session_id=10,
            session_item_id=99,
            now=datetime(2026, 3, 17, tzinfo=UTC),
        )
        await session.commit()

        feedback_count = await session.scalar(select(func.count(ContentFeedback.id)))
        event_count = await session.scalar(
            select(func.count(ProductEvent.id)).where(
                ProductEvent.event_name == "content_feedback_submitted"
            )
        )

        assert created is True
        assert created_again is False
        assert feedback_count == 1
        assert event_count == 1


@pytest.mark.asyncio
async def test_submit_content_feedback_rejects_invalid_type(session_factory) -> None:
    user_id, item_id = await _seed_feedback_target(session_factory)

    async with session_factory() as session:
        with pytest.raises(ValueError, match="Invalid feedback type"):
            await submit_content_feedback(
                session,
                user_id=user_id,
                collocation_item_id=item_id,
                feedback_type="bad_type",
            )


@pytest.mark.asyncio
async def test_feedback_export_outputs_csv_and_jsonl(session_factory) -> None:
    user_id, item_id = await _seed_feedback_target(session_factory)

    async with session_factory() as session:
        await submit_content_feedback(
            session,
            user_id=user_id,
            collocation_item_id=item_id,
            feedback_type="too_hard",
            session_type="daily",
            session_id=7,
            session_item_id=8,
            now=datetime(2026, 3, 17, 10, 0, tzinfo=UTC),
        )
        await session.commit()

        rows = await load_feedback_export_rows(session)
        csv_output = feedback_rows_to_csv(rows)
        jsonl_output = feedback_rows_to_jsonl(rows)

        assert len(rows) == 1
        assert "too_hard" in csv_output
        assert "take action" in csv_output
        assert '"feedback_type": "too_hard"' in jsonl_output
        assert '"collocation_external_key": "feedback-item"' in jsonl_output
