from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.application.onboarding import DEFAULT_PACE_MODE, normalize_pace_mode
from collocation_coach.application.time import local_today
from collocation_coach.storage.models import (
    CollocationItem,
    DailyLesson,
    LessonUnit,
    User,
    UserCollocationProgress,
)


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    lessons_completed_last_7_days: int
    pace_mode: str
    review_backlog_bucket: str
    completed_units: int
    total_units: int


def backlog_bucket_for_count(review_backlog_count: int) -> str:
    if review_backlog_count <= 0:
        return "0"
    if review_backlog_count <= 5:
        return "1-5"
    if review_backlog_count <= 15:
        return "6-15"
    return "16+"


async def build_progress_snapshot(
    session: AsyncSession,
    user: User,
    *,
    now_utc: datetime | None = None,
) -> ProgressSnapshot:
    now_utc = now_utc or datetime.now(UTC)
    if user.level_band is None:
        return ProgressSnapshot(
            lessons_completed_last_7_days=0,
            pace_mode=normalize_pace_mode(user.pace_mode),
            review_backlog_bucket="0",
            completed_units=0,
            total_units=0,
        )

    timezone_name = user.timezone or "UTC"
    current_local_date = local_today(now_utc, timezone_name)
    lessons_completed_last_7_days = await session.scalar(
        select(func.count(DailyLesson.id)).where(
            DailyLesson.user_id == user.id,
            DailyLesson.status == "completed",
            DailyLesson.lesson_date >= current_local_date - timedelta(days=6),
            DailyLesson.lesson_date <= current_local_date,
        )
    ) or 0

    due_review_count = await session.scalar(
        select(func.count(UserCollocationProgress.id))
        .join(CollocationItem, CollocationItem.id == UserCollocationProgress.collocation_item_id)
        .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
        .where(
            UserCollocationProgress.user_id == user.id,
            UserCollocationProgress.due_at.is_not(None),
            UserCollocationProgress.due_at <= now_utc,
            LessonUnit.level_band == user.level_band,
        )
    ) or 0

    total_units = await session.scalar(
        select(func.count(LessonUnit.id)).where(LessonUnit.level_band == user.level_band)
    ) or 0

    unit_item_counts = (
        select(
            CollocationItem.lesson_unit_id.label("lesson_unit_id"),
            func.count(CollocationItem.id).label("total_items"),
        )
        .group_by(CollocationItem.lesson_unit_id)
        .subquery()
    )
    unit_seen_counts = (
        select(
            CollocationItem.lesson_unit_id.label("lesson_unit_id"),
            func.count(func.distinct(UserCollocationProgress.collocation_item_id)).label("seen_items"),
        )
        .join(
            UserCollocationProgress,
            UserCollocationProgress.collocation_item_id == CollocationItem.id,
        )
        .where(
            UserCollocationProgress.user_id == user.id,
            UserCollocationProgress.times_seen > 0,
        )
        .group_by(CollocationItem.lesson_unit_id)
        .subquery()
    )

    completed_units = await session.scalar(
        select(func.count(LessonUnit.id))
        .join(unit_item_counts, unit_item_counts.c.lesson_unit_id == LessonUnit.id)
        .outerjoin(unit_seen_counts, unit_seen_counts.c.lesson_unit_id == LessonUnit.id)
        .where(
            LessonUnit.level_band == user.level_band,
            func.coalesce(unit_seen_counts.c.seen_items, 0) >= unit_item_counts.c.total_items,
        )
    ) or 0

    return ProgressSnapshot(
        lessons_completed_last_7_days=lessons_completed_last_7_days,
        pace_mode=normalize_pace_mode(user.pace_mode) or DEFAULT_PACE_MODE,
        review_backlog_bucket=backlog_bucket_for_count(due_review_count),
        completed_units=completed_units,
        total_units=total_units,
    )
