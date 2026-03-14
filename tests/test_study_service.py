from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from collocation_coach.application.study import (
    apply_rating,
    create_or_get_daily_lesson,
    create_or_get_review_session,
    get_daily_lesson_level_band,
    get_next_session_card,
    has_extra_practice_available,
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


async def _seed_second_level_content(factory: async_sessionmaker) -> tuple[int, list[int]]:
    async with factory() as session:
        lesson_unit = LessonUnit(
            external_key="lesson-b1-1",
            level_band="b1_b2",
            day_number=1,
            topic="b1 topic",
            source_path="b1.yaml",
        )
        session.add(lesson_unit)
        await session.flush()
        items = [
            CollocationItem(
                lesson_unit_id=lesson_unit.id,
                external_key=f"b1-item-{index}",
                phrase=f"b1-phrase-{index}",
                translation_ru=f"b1-перевод-{index}",
                explanation_ru=f"b1-объяснение-{index}",
                correct_example=f"b1-correct-{index}",
                common_mistake=f"b1-wrong-{index}",
                mistake_explanation_ru=f"b1-mistake-explanation-{index}",
                practice_prompt=f"b1-practice-{index}",
                option_a=f"b1-a-{index}",
                option_b=f"b1-b-{index}",
                option_c=f"b1-c-{index}",
                correct_option_index=0,
                tags=["tag"],
            )
            for index in range(1, 4)
        ]
        session.add_all(items)
        await session.commit()
        return lesson_unit.id, [item.id for item in items]


async def _seed_additional_a2_content(factory: async_sessionmaker, day_number: int = 2) -> tuple[int, list[int]]:
    async with factory() as session:
        lesson_unit = LessonUnit(
            external_key=f"lesson-a2-{day_number}",
            level_band="a2_b1",
            day_number=day_number,
            topic=f"a2 topic {day_number}",
            source_path=f"a2-{day_number}.yaml",
        )
        session.add(lesson_unit)
        await session.flush()
        items = [
            CollocationItem(
                lesson_unit_id=lesson_unit.id,
                external_key=f"a2-day-{day_number}-item-{index}",
                phrase=f"a2-day-{day_number}-phrase-{index}",
                translation_ru=f"a2-day-{day_number}-перевод-{index}",
                explanation_ru=f"a2-day-{day_number}-объяснение-{index}",
                correct_example=f"a2-day-{day_number}-correct-{index}",
                common_mistake=f"a2-day-{day_number}-wrong-{index}",
                mistake_explanation_ru=f"a2-day-{day_number}-mistake-explanation-{index}",
                practice_prompt=f"a2-day-{day_number}-practice-{index}",
                option_a=f"a2-day-{day_number}-a-{index}",
                option_b=f"a2-day-{day_number}-b-{index}",
                option_c=f"a2-day-{day_number}-c-{index}",
                correct_option_index=0,
                tags=["tag"],
            )
            for index in range(1, 4)
        ]
        session.add_all(items)
        await session.commit()
        return lesson_unit.id, [item.id for item in items]


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

        assert len(rows) == 3
        assert rows[0].item_type == "review"
        assert rows[1].item_type == "new"
        assert rows[2].item_type == "new"


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


@pytest.mark.asyncio
async def test_level_change_uses_first_lesson_of_new_level(session_factory) -> None:
    user_id, _ = await _seed_user_and_content(session_factory)
    b1_lesson_unit_id, _ = await _seed_second_level_content(session_factory)

    async with session_factory() as session:
        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None
        lesson.status = "completed"
        await session.commit()

        user = await session.get(User, user_id)
        assert user is not None
        user.level_band = "b1_b2"
        await session.commit()

        next_lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 15),
            now=datetime(2026, 3, 15, tzinfo=UTC),
        )
        assert next_lesson is not None
        assert next_lesson.lesson_unit_id == b1_lesson_unit_id
        assert await get_daily_lesson_level_band(session, next_lesson.id) == "b1_b2"


@pytest.mark.asyncio
async def test_incomplete_daily_lesson_is_replaced_when_level_changes(session_factory) -> None:
    user_id, _ = await _seed_user_and_content(session_factory)
    b1_lesson_unit_id, _ = await _seed_second_level_content(session_factory)

    async with session_factory() as session:
        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None

        user = await session.get(User, user_id)
        assert user is not None
        user.level_band = "b1_b2"
        await session.commit()

        replaced = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert replaced is not None
        assert replaced.id == lesson.id
        assert replaced.lesson_unit_id == b1_lesson_unit_id
        rows = list(
            (
                await session.execute(
                    select(DailyLessonItem)
                    .where(DailyLessonItem.daily_lesson_id == replaced.id)
                    .order_by(DailyLessonItem.position.asc())
                )
            ).scalars()
        )
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_daily_lesson_review_items_stay_with_current_level(session_factory) -> None:
    user_id, a2_item_ids = await _seed_user_and_content(session_factory)
    _, b1_item_ids = await _seed_second_level_content(session_factory)

    async with session_factory() as session:
        session.add_all(
            [
                UserCollocationProgress(
                    user_id=user_id,
                    collocation_item_id=a2_item_ids[0],
                    times_seen=1,
                    times_correct=1,
                    stability_stage=1,
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                ),
                UserCollocationProgress(
                    user_id=user_id,
                    collocation_item_id=b1_item_ids[0],
                    times_seen=1,
                    times_correct=1,
                    stability_stage=1,
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                ),
            ]
        )
        user = await session.get(User, user_id)
        assert user is not None
        user.level_band = "b1_b2"
        await session.commit()

        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None

        review_item_id = await session.scalar(
            select(DailyLessonItem.collocation_item_id)
            .where(
                DailyLessonItem.daily_lesson_id == lesson.id,
                DailyLessonItem.item_type == "review",
            )
            .limit(1)
        )
        assert review_item_id == b1_item_ids[0]


@pytest.mark.asyncio
async def test_review_session_is_isolated_per_level(session_factory) -> None:
    user_id, a2_item_ids = await _seed_user_and_content(session_factory)
    _, b1_item_ids = await _seed_second_level_content(session_factory)

    async with session_factory() as session:
        session.add_all(
            [
                UserCollocationProgress(
                    user_id=user_id,
                    collocation_item_id=a2_item_ids[0],
                    times_seen=1,
                    times_correct=1,
                    stability_stage=1,
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                ),
                UserCollocationProgress(
                    user_id=user_id,
                    collocation_item_id=b1_item_ids[0],
                    times_seen=1,
                    times_correct=1,
                    stability_stage=1,
                    due_at=datetime(2026, 3, 14, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()

        a2_review = await create_or_get_review_session(
            session,
            user_id=user_id,
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert a2_review is not None

        first_card = await get_next_session_card(session, "review", a2_review.id)
        assert first_card is not None
        assert first_card.phrase == "phrase-1"

        user = await session.get(User, user_id)
        assert user is not None
        user.level_band = "b1_b2"
        await session.commit()

        b1_review = await create_or_get_review_session(
            session,
            user_id=user_id,
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert b1_review is not None
        assert b1_review.id != a2_review.id

        second_card = await get_next_session_card(session, "review", b1_review.id)
        assert second_card is not None
        assert second_card.phrase == "b1-phrase-1"


@pytest.mark.asyncio
async def test_intensive_pace_spans_multiple_content_packs(session_factory) -> None:
    user_id, first_pack_ids = await _seed_user_and_content(session_factory)
    _, second_pack_ids = await _seed_additional_a2_content(session_factory, day_number=2)

    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.pace_mode = "intensive"
        await session.commit()

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
        item_ids = [row.collocation_item_id for row in rows]

        assert len(rows) == 5
        assert item_ids == first_pack_ids + second_pack_ids[:2]


@pytest.mark.asyncio
async def test_light_pace_limits_new_items(session_factory) -> None:
    user_id, _ = await _seed_user_and_content(session_factory)
    await _seed_additional_a2_content(session_factory, day_number=2)

    async with session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        user.pace_mode = "light"
        await session.commit()

        lesson = await create_or_get_daily_lesson(
            session,
            user_id=user_id,
            lesson_date=date(2026, 3, 14),
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )
        assert lesson is not None

        new_item_count = await session.scalar(
            select(func.count())
            .select_from(DailyLessonItem)
            .where(
                DailyLessonItem.daily_lesson_id == lesson.id,
                DailyLessonItem.item_type == "new",
            )
        )
        assert new_item_count == 2


@pytest.mark.asyncio
async def test_extra_practice_available_after_daily_progress(session_factory) -> None:
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
        await record_answer(session, "daily", lesson.id, card.session_item_id, selected_option_index=1)
        await apply_rating(
            session,
            user_id=user_id,
            session_type="daily",
            session_id=lesson.id,
            session_item_id=card.session_item_id,
            rating="know",
            now=datetime(2026, 3, 14, tzinfo=UTC),
        )

        assert await has_extra_practice_available(session, user_id)

        extra_session = await create_or_get_review_session(
            session,
            user_id=user_id,
            now=datetime(2026, 3, 14, tzinfo=UTC),
            include_extra=True,
        )
        assert extra_session is not None

        extra_card = await get_next_session_card(session, "review", extra_session.id)
        assert extra_card is not None
        assert extra_card.phrase == card.phrase
