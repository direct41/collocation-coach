from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import Select, asc, case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.application.onboarding import DEFAULT_PACE_MODE, normalize_pace_mode
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
REVIEW_SESSION_LIMIT = 5


@dataclass(frozen=True, slots=True)
class PacePlan:
    new_items: int
    review_items: int
    extra_items: int


PACE_PLANS: dict[str, PacePlan] = {
    "light": PacePlan(new_items=2, review_items=2, extra_items=3),
    "standard": PacePlan(new_items=3, review_items=2, extra_items=3),
    "intensive": PacePlan(new_items=5, review_items=3, extra_items=5),
}


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


def pace_plan_for_mode(pace_mode: str | None) -> PacePlan:
    return PACE_PLANS.get(normalize_pace_mode(pace_mode), PACE_PLANS[DEFAULT_PACE_MODE])


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


def _extra_progress_query(
    user_id: int,
    level_band: str,
    limit: int,
) -> Select[tuple[int]]:
    rating_priority = case(
        (UserCollocationProgress.last_rating == "repeat", 0),
        (UserCollocationProgress.last_rating == "unsure", 1),
        else_=2,
    )
    return (
        select(UserCollocationProgress.collocation_item_id)
        .join(CollocationItem, CollocationItem.id == UserCollocationProgress.collocation_item_id)
        .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
        .where(
            UserCollocationProgress.user_id == user_id,
            UserCollocationProgress.times_seen > 0,
            LessonUnit.level_band == level_band,
        )
        .order_by(
            asc(rating_priority),
            asc(UserCollocationProgress.last_seen_at),
            asc(UserCollocationProgress.collocation_item_id),
        )
        .limit(limit)
    )


def _new_item_query(
    user_id: int,
    level_band: str,
    limit: int,
) -> Select[tuple[int]]:
    return (
        select(CollocationItem.id)
        .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
        .outerjoin(
            UserCollocationProgress,
            (UserCollocationProgress.collocation_item_id == CollocationItem.id)
            & (UserCollocationProgress.user_id == user_id),
        )
        .where(
            LessonUnit.level_band == level_band,
            UserCollocationProgress.id.is_(None),
        )
        .order_by(
            asc(LessonUnit.day_number),
            asc(CollocationItem.external_key),
        )
        .limit(limit)
    )


async def _resolve_primary_lesson_unit_id(
    session: AsyncSession,
    collocation_item_ids: list[int],
) -> int | None:
    if not collocation_item_ids:
        return None
    return await session.scalar(
        select(CollocationItem.lesson_unit_id)
        .where(CollocationItem.id.in_(collocation_item_ids))
        .order_by(asc(CollocationItem.id))
        .limit(1)
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
    pace_plan = pace_plan_for_mode(user.pace_mode)

    existing = await session.scalar(
        select(DailyLesson).where(
            DailyLesson.user_id == user_id,
            DailyLesson.lesson_date == lesson_date,
        )
    )

    if existing is not None:
        existing_level_band = await get_daily_lesson_level_band(session, existing.id)
        if existing_level_band == user.level_band:
            return existing
        if existing.status == "completed":
            return existing
        await session.execute(delete(DailyLessonItem).where(DailyLessonItem.daily_lesson_id == existing.id))
        daily_lesson = existing
    else:
        daily_lesson = None

    due_review_ids = list(
        (
            await session.execute(
                _due_progress_query(user_id, user.level_band, now, pace_plan.review_items)
            )
        ).scalars()
    )
    new_item_ids = list(
        (
            await session.execute(
                _new_item_query(user_id, user.level_band, pace_plan.new_items)
            )
        ).scalars()
    )

    selected_item_ids = due_review_ids + new_item_ids
    if not selected_item_ids:
        return None

    primary_lesson_unit_id = await _resolve_primary_lesson_unit_id(session, selected_item_ids)
    if primary_lesson_unit_id is None:
        return None

    if daily_lesson is None:
        daily_lesson = DailyLesson(
            user_id=user_id,
            lesson_date=lesson_date,
            lesson_unit_id=primary_lesson_unit_id,
            status="in_progress",
        )
        session.add(daily_lesson)
        await session.flush()
    else:
        daily_lesson.lesson_unit_id = primary_lesson_unit_id
        daily_lesson.status = "in_progress"
        daily_lesson.completed_at = None
        daily_lesson.delivered_at = None

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

    for collocation_item_id in new_item_ids:
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


async def create_or_get_review_session(
    session: AsyncSession,
    user_id: int,
    now: datetime | None = None,
    include_extra: bool = False,
) -> ReviewSession | None:
    now = now or utc_now()
    user = await session.get(User, user_id)
    if user is None or user.level_band is None:
        return None
    pace_plan = pace_plan_for_mode(user.pace_mode)

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

    item_ids = list(
        (
            await session.execute(
                _extra_progress_query(user_id, user.level_band, pace_plan.extra_items)
                if include_extra
                else _due_progress_query(
                    user_id,
                    user.level_band,
                    now,
                    min(REVIEW_SESSION_LIMIT, pace_plan.extra_items if include_extra else REVIEW_SESSION_LIMIT),
                )
            )
        ).scalars()
    )
    if not item_ids:
        return None

    review_session = ReviewSession(user_id=user_id, status="in_progress")
    session.add(review_session)
    await session.flush()

    for index, collocation_item_id in enumerate(item_ids, start=1):
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


async def has_extra_practice_available(session: AsyncSession, user_id: int) -> bool:
    user = await session.get(User, user_id)
    if user is None or user.level_band is None:
        return False
    return bool(
        await session.scalar(
            select(func.count())
            .select_from(UserCollocationProgress)
            .join(CollocationItem, CollocationItem.id == UserCollocationProgress.collocation_item_id)
            .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
            .where(
                UserCollocationProgress.user_id == user_id,
                UserCollocationProgress.times_seen > 0,
                LessonUnit.level_band == user.level_band,
            )
        )
    )


async def get_daily_lesson_level_band(session: AsyncSession, daily_lesson_id: int) -> str | None:
    return await session.scalar(
        select(LessonUnit.level_band)
        .join(CollocationItem, CollocationItem.lesson_unit_id == LessonUnit.id)
        .join(DailyLessonItem, DailyLessonItem.collocation_item_id == CollocationItem.id)
        .where(DailyLessonItem.daily_lesson_id == daily_lesson_id)
        .limit(1)
    )
