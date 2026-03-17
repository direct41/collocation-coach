from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.storage.models import ProductEvent

CORE_EVENT_NAMES = (
    "onboarding_completed",
    "daily_lesson_started",
    "daily_lesson_completed",
    "review_session_started",
    "review_session_completed",
    "return_prompt_shown",
    "progress_viewed",
    "content_feedback_submitted",
    "settings_updated",
)


@dataclass(frozen=True, slots=True)
class ProductEventCount:
    event_name: str
    total_count: int
    last_7_days_count: int


@dataclass(frozen=True, slots=True)
class ProductEventSummary:
    counts: tuple[ProductEventCount, ...]
    return_prompts: int
    return_completions_within_72h: int


async def record_product_event(
    session: AsyncSession,
    user_id: int,
    event_name: str,
    *,
    occurred_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
    event_key: str | None = None,
) -> bool:
    if event_key is not None:
        existing_id = await session.scalar(
            select(ProductEvent.id).where(
                ProductEvent.user_id == user_id,
                ProductEvent.event_name == event_name,
                ProductEvent.event_key == event_key,
            )
        )
        if existing_id is not None:
            return False

    session.add(
        ProductEvent(
            user_id=user_id,
            event_name=event_name,
            event_key=event_key,
            event_metadata=metadata or {},
            occurred_at=occurred_at or datetime.now(UTC),
        )
    )
    return True


async def summarize_product_events(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> ProductEventSummary:
    now = now or datetime.now(UTC)
    since = now - timedelta(days=7)

    total_rows = list(
        (
            await session.execute(
                select(ProductEvent.event_name, func.count(ProductEvent.id))
                .where(ProductEvent.event_name.in_(CORE_EVENT_NAMES))
                .group_by(ProductEvent.event_name)
            )
        ).all()
    )
    recent_rows = list(
        (
            await session.execute(
                select(ProductEvent.event_name, func.count(ProductEvent.id))
                .where(
                    ProductEvent.event_name.in_(CORE_EVENT_NAMES),
                    ProductEvent.occurred_at >= since,
                )
                .group_by(ProductEvent.event_name)
            )
        ).all()
    )

    totals = {event_name: count for event_name, count in total_rows}
    recents = {event_name: count for event_name, count in recent_rows}
    counts = tuple(
        ProductEventCount(
            event_name=event_name,
            total_count=totals.get(event_name, 0),
            last_7_days_count=recents.get(event_name, 0),
        )
        for event_name in CORE_EVENT_NAMES
    )

    prompt_rows = list(
        (
            await session.execute(
                select(ProductEvent.user_id, ProductEvent.occurred_at)
                .where(ProductEvent.event_name == "return_prompt_shown")
                .order_by(ProductEvent.user_id.asc(), ProductEvent.occurred_at.asc())
            )
        ).all()
    )
    completion_rows = list(
        (
            await session.execute(
                select(ProductEvent.user_id, ProductEvent.occurred_at)
                .where(ProductEvent.event_name == "daily_lesson_completed")
                .order_by(ProductEvent.user_id.asc(), ProductEvent.occurred_at.asc())
            )
        ).all()
    )

    completions_by_user: dict[int, list[datetime]] = {}
    for user_id, occurred_at in completion_rows:
        completions_by_user.setdefault(user_id, []).append(occurred_at)

    conversion_count = 0
    for user_id, prompt_time in prompt_rows:
        completion_times = completions_by_user.get(user_id, [])
        if any(prompt_time <= completion_time <= prompt_time + timedelta(hours=72) for completion_time in completion_times):
            conversion_count += 1

    return ProductEventSummary(
        counts=counts,
        return_prompts=len(prompt_rows),
        return_completions_within_72h=conversion_count,
    )
