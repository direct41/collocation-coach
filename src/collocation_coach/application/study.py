from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Select, asc, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.storage.models import (
    CollocationItem,
    DailyLesson,
    DailyLessonItem,
    LessonUnit,
    ReviewSession,
    ReviewSessionItem,
    User,
    UserCollocationProgress,
)

SessionType = Literal["daily", "review"]
Rating = Literal["know", "unsure", "repeat"]

SUCCESS_INTERVALS_DAYS = (3, 7, 14)
DAILY_REVIEW_LIMIT = 2
REVIEW_SESSION_LIMIT = 5


@dataclass(slots=True)
class StudyItemCard:
    session_type: SessionType
    session_id: int
    session_item_id: int
    position: int
    total_items: int
    item_type: str
    phrase: str
    translation_ru: str
    explanation_ru: str
    correct_example: str
    common_mistake: str
    mistake_explanation_ru: str
    practice_prompt: str
    options: tuple[str, str, str]
    correct_option_index: int


@dataclass(slots=True)
class SessionSummary:
    session_type: SessionType
    session_id: int
    total_items: int
    correct_answers: int
    review_items: int
    new_items: int
    completed: bool


def utc_now() -> datetime:
    return datetime.now(UTC)


def _session_item_model(session_type: SessionType):
    return DailyLessonItem if session_type == "daily" else ReviewSessionItem


def _session_parent_model(session_type: SessionType):
    return DailyLesson if session_type == "daily" else ReviewSession


def _session_fk_name(session_type: SessionType) -> str:
    return "daily_lesson_id" if session_type == "daily" else "review_session_id"


def _build_step_query(session_type: SessionType, session_id: int) -> Select[tuple[object, CollocationItem]]:
    session_item_model = _session_item_model(session_type)
    fk_name = _session_fk_name(session_type)
    return (
        select(session_item_model, CollocationItem)
        .join(CollocationItem, session_item_model.collocation_item_id == CollocationItem.id)
        .where(getattr(session_item_model, fk_name) == session_id)
        .where(session_item_model.self_rating.is_(None))
        .order_by(asc(session_item_model.position))
    )


def _build_item_lookup_query(
    session_type: SessionType,
    session_id: int,
    session_item_id: int,
) -> Select[tuple[object, CollocationItem]]:
    session_item_model = _session_item_model(session_type)
    fk_name = _session_fk_name(session_type)
    return (
        select(session_item_model, CollocationItem)
        .join(CollocationItem, session_item_model.collocation_item_id == CollocationItem.id)
        .where(session_item_model.id == session_item_id)
        .where(getattr(session_item_model, fk_name) == session_id)
    )


def _options_for_collocation(item: CollocationItem) -> tuple[tuple[str, str, str], int]:
    options = (item.option_a, item.option_b, item.option_c)
    return options, item.correct_option_index


def _to_card(session_type: SessionType, row: tuple[object, CollocationItem], total_items: int) -> StudyItemCard:
    session_item, collocation_item = row
    options, correct_option_index = _options_for_collocation(collocation_item)
    item_type = getattr(session_item, "item_type", "review")
    return StudyItemCard(
        session_type=session_type,
        session_id=getattr(session_item, _session_fk_name(session_type)),
        session_item_id=session_item.id,
        position=session_item.position,
        total_items=total_items,
        item_type=item_type,
        phrase=collocation_item.phrase,
        translation_ru=collocation_item.translation_ru,
        explanation_ru=collocation_item.explanation_ru,
        correct_example=collocation_item.correct_example,
        common_mistake=collocation_item.common_mistake,
        mistake_explanation_ru=collocation_item.mistake_explanation_ru,
        practice_prompt=collocation_item.practice_prompt,
        options=options,
        correct_option_index=correct_option_index,
    )


async def _load_session_total(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
) -> int:
    session_item_model = _session_item_model(session_type)
    fk_name = _session_fk_name(session_type)
    return await session.scalar(
        select(func.count()).select_from(session_item_model).where(
            getattr(session_item_model, fk_name) == session_id
        )
    ) or 0


async def _load_next_card(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
) -> StudyItemCard | None:
    total_items = await _load_session_total(session, session_type, session_id)
    row = (await session.execute(_build_step_query(session_type, session_id).limit(1))).first()
    if row is None:
        return None
    return _to_card(session_type, row, total_items)


async def _fetch_session_item_card(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
    session_item_id: int,
) -> StudyItemCard | None:
    total_items = await _load_session_total(session, session_type, session_id)
    row = (
        await session.execute(
            _build_item_lookup_query(session_type, session_id, session_item_id)
        )
    ).first()
    if row is None:
        return None
    return _to_card(session_type, row, total_items)


async def _load_existing_in_progress_review_session(
    session: AsyncSession,
    user_id: int,
    level_band: str,
) -> ReviewSession | None:
    return await session.scalar(
        select(ReviewSession)
        .join(ReviewSessionItem, ReviewSessionItem.review_session_id == ReviewSession.id)
        .join(CollocationItem, CollocationItem.id == ReviewSessionItem.collocation_item_id)
        .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
        .where(
            ReviewSession.user_id == user_id,
            ReviewSession.status == "in_progress",
            LessonUnit.level_band == level_band,
        )
        .order_by(ReviewSession.id.desc())
        .limit(1)
    )


def _due_progress_query(
    user_id: int,
    level_band: str,
    now: datetime,
    limit: int,
) -> Select[tuple[int]]:
    return (
        select(UserCollocationProgress.collocation_item_id)
        .join(CollocationItem, CollocationItem.id == UserCollocationProgress.collocation_item_id)
        .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
        .where(
            UserCollocationProgress.user_id == user_id,
            UserCollocationProgress.due_at.is_not(None),
            UserCollocationProgress.due_at <= now,
            LessonUnit.level_band == level_band,
        )
        .order_by(asc(UserCollocationProgress.due_at))
        .limit(limit)
    )


async def create_or_get_daily_lesson(
    session: AsyncSession,
    user_id: int,
    lesson_date: date,
    now: datetime | None = None,
) -> DailyLesson | None:
    now = now or utc_now()
    user = await session.get(User, user_id)
    if user is None or user.level_band is None:
        return None

    existing = await session.scalar(
        select(DailyLesson).where(
            DailyLesson.user_id == user_id,
            DailyLesson.lesson_date == lesson_date,
        )
    )

    lesson_unit = await _select_next_lesson_unit_for_level(session, user_id, user.level_band)
    if lesson_unit is None:
        return None

    if existing is not None:
        existing_level_band = await get_daily_lesson_level_band(session, existing.id)
        if existing_level_band == user.level_band:
            return existing
        if existing.status == "completed":
            return existing

        await session.execute(
            delete(DailyLessonItem).where(DailyLessonItem.daily_lesson_id == existing.id)
        )
        existing.lesson_unit_id = lesson_unit.id
        existing.status = "in_progress"
        existing.completed_at = None
        existing.delivered_at = None
        daily_lesson = existing
    else:
        daily_lesson = DailyLesson(
            user_id=user_id,
            lesson_date=lesson_date,
            lesson_unit_id=lesson_unit.id,
            status="in_progress",
        )
        session.add(daily_lesson)
        await session.flush()

    due_review_ids = list(
        (await session.execute(_due_progress_query(user_id, user.level_band, now, DAILY_REVIEW_LIMIT))).scalars()
    )

    new_items = list(
        (
            await session.execute(
                select(CollocationItem.id)
                .where(CollocationItem.lesson_unit_id == lesson_unit.id)
                .order_by(asc(CollocationItem.external_key))
            )
        ).scalars()
    )

    position = 1
    for collocation_item_id in due_review_ids:
        session.add(
            DailyLessonItem(
                daily_lesson_id=daily_lesson.id,
                collocation_item_id=collocation_item_id,
                item_type="review",
                position=position,
            )
        )
        position += 1

    for collocation_item_id in new_items:
        session.add(
            DailyLessonItem(
                daily_lesson_id=daily_lesson.id,
                collocation_item_id=collocation_item_id,
                item_type="new",
                position=position,
            )
        )
        position += 1

    await session.commit()
    await session.refresh(daily_lesson)
    return daily_lesson


async def _select_next_lesson_unit_for_level(
    session: AsyncSession,
    user_id: int,
    level_band: str,
) -> LessonUnit | None:
    served_count = await session.scalar(
        select(func.count())
        .select_from(DailyLesson)
        .join(LessonUnit, LessonUnit.id == DailyLesson.lesson_unit_id)
        .where(
            DailyLesson.user_id == user_id,
            LessonUnit.level_band == level_band,
        )
    ) or 0

    return await session.scalar(
        select(LessonUnit)
        .where(LessonUnit.level_band == level_band)
        .order_by(asc(LessonUnit.day_number))
        .offset(served_count)
        .limit(1)
    )


async def create_or_get_review_session(
    session: AsyncSession,
    user_id: int,
    now: datetime | None = None,
) -> ReviewSession | None:
    now = now or utc_now()
    user = await session.get(User, user_id)
    if user is None or user.level_band is None:
        return None

    existing = await _load_existing_in_progress_review_session(session, user_id, user.level_band)
    if existing is not None:
        has_pending = await session.scalar(
            select(func.count())
            .select_from(ReviewSessionItem)
            .where(
                ReviewSessionItem.review_session_id == existing.id,
                ReviewSessionItem.self_rating.is_(None),
            )
        ) or 0
        if has_pending > 0:
            return existing

    due_item_ids = list(
        (await session.execute(_due_progress_query(user_id, user.level_band, now, REVIEW_SESSION_LIMIT))).scalars()
    )
    if not due_item_ids:
        return None

    review_session = ReviewSession(user_id=user_id, status="in_progress")
    session.add(review_session)
    await session.flush()

    for index, collocation_item_id in enumerate(due_item_ids, start=1):
        session.add(
            ReviewSessionItem(
                review_session_id=review_session.id,
                collocation_item_id=collocation_item_id,
                position=index,
            )
        )

    await session.commit()
    await session.refresh(review_session)
    return review_session


async def get_next_session_card(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
) -> StudyItemCard | None:
    return await _load_next_card(session, session_type, session_id)


async def get_session_item_card(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
    session_item_id: int,
) -> StudyItemCard | None:
    return await _fetch_session_item_card(session, session_type, session_id, session_item_id)


async def record_answer(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
    session_item_id: int,
    selected_option_index: int,
) -> StudyItemCard | None:
    card = await _fetch_session_item_card(session, session_type, session_id, session_item_id)
    if card is None:
        return None

    session_item_model = _session_item_model(session_type)
    session_item = await session.get(session_item_model, session_item_id)
    if session_item is None or session_item.self_rating is not None:
        return None

    if not 0 <= selected_option_index < len(card.options):
        raise ValueError("Selected option is out of range")

    session_item.answer_selected = card.options[selected_option_index]
    session_item.answered_correctly = selected_option_index == card.correct_option_index
    await session.commit()
    return card


def _next_due_at_for_rating(now: datetime, rating: Rating, current_stage: int) -> tuple[int, datetime]:
    if rating == "know":
        next_stage = current_stage + 1
        interval_days = SUCCESS_INTERVALS_DAYS[min(next_stage - 1, len(SUCCESS_INTERVALS_DAYS) - 1)]
        return next_stage, now + timedelta(days=interval_days)
    if rating == "unsure":
        return max(current_stage, 0), now + timedelta(days=1)
    return 0, now


async def apply_rating(
    session: AsyncSession,
    user_id: int,
    session_type: SessionType,
    session_id: int,
    session_item_id: int,
    rating: Rating,
    now: datetime | None = None,
) -> SessionSummary:
    now = now or utc_now()
    session_item_model = _session_item_model(session_type)
    parent_model = _session_parent_model(session_type)

    session_item = await session.get(session_item_model, session_item_id)
    if session_item is None:
        raise ValueError("Session item not found")
    if session_item.answered_correctly is None:
        raise ValueError("Cannot rate an unanswered item")

    session_item.self_rating = rating
    session_item.answered_at = now

    progress = await session.scalar(
        select(UserCollocationProgress).where(
            UserCollocationProgress.user_id == user_id,
            UserCollocationProgress.collocation_item_id == session_item.collocation_item_id,
        )
    )
    if progress is None:
        progress = UserCollocationProgress(
            user_id=user_id,
            collocation_item_id=session_item.collocation_item_id,
            times_seen=0,
            times_correct=0,
            stability_stage=0,
        )
        session.add(progress)

    progress.times_seen += 1
    if session_item.answered_correctly:
        progress.times_correct += 1
    progress.last_seen_at = now
    progress.last_rating = rating
    progress.stability_stage, progress.due_at = _next_due_at_for_rating(
        now, rating, progress.stability_stage
    )

    pending_count = await session.scalar(
        select(func.count())
        .select_from(session_item_model)
        .where(
            getattr(session_item_model, _session_fk_name(session_type)) == session_id,
            session_item_model.self_rating.is_(None),
        )
    ) or 0

    parent = await session.get(parent_model, session_id)
    if pending_count == 0 and parent is not None:
        parent.status = "completed"
        parent.completed_at = now

    await session.commit()
    return await get_session_summary(session, session_type, session_id)


async def get_session_summary(
    session: AsyncSession,
    session_type: SessionType,
    session_id: int,
) -> SessionSummary:
    session_item_model = _session_item_model(session_type)
    total_items = await _load_session_total(session, session_type, session_id)
    correct_answers = await session.scalar(
        select(func.count())
        .select_from(session_item_model)
        .where(
            getattr(session_item_model, _session_fk_name(session_type)) == session_id,
            session_item_model.answered_correctly.is_(True),
        )
    ) or 0
    new_items = 0
    review_items = total_items
    if session_type == "daily":
        new_items = await session.scalar(
            select(func.count())
            .select_from(DailyLessonItem)
            .where(
                DailyLessonItem.daily_lesson_id == session_id,
                DailyLessonItem.item_type == "new",
            )
        ) or 0
        review_items = await session.scalar(
            select(func.count())
            .select_from(DailyLessonItem)
            .where(
                DailyLessonItem.daily_lesson_id == session_id,
                DailyLessonItem.item_type == "review",
            )
        ) or 0

    parent_model = _session_parent_model(session_type)
    parent = await session.get(parent_model, session_id)
    completed = bool(parent and parent.status == "completed")

    return SessionSummary(
        session_type=session_type,
        session_id=session_id,
        total_items=total_items,
        correct_answers=correct_answers,
        review_items=review_items,
        new_items=new_items,
        completed=completed,
    )


async def load_user_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))


async def get_daily_lesson_level_band(session: AsyncSession, daily_lesson_id: int) -> str | None:
    return await session.scalar(
        select(LessonUnit.level_band)
        .join(DailyLesson, DailyLesson.lesson_unit_id == LessonUnit.id)
        .where(DailyLesson.id == daily_lesson_id)
    )
