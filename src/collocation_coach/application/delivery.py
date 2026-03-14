import logging
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.application.onboarding import onboarding_complete
from collocation_coach.application.study import (
    create_or_get_daily_lesson,
    get_next_session_card,
    get_session_summary,
)
from collocation_coach.storage.models import DailyLesson, User
from collocation_coach.transport.telegram.messages import (
    daily_intro_text,
    format_item_card,
    format_summary,
    practice_markup,
)

logger = logging.getLogger(__name__)


def _local_now(now_utc: datetime, timezone_name: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(timezone_name))


def user_is_due_for_delivery(user: User, now_utc: datetime) -> bool:
    if not onboarding_complete(user.level_band, user.timezone, user.daily_delivery_time):
        return False
    if not user.is_active or user.timezone is None or user.daily_delivery_time is None:
        return False

    local_now = _local_now(now_utc, user.timezone)
    return local_now.strftime("%H:%M") == user.daily_delivery_time


async def load_due_user_ids(
    session_factory: async_sessionmaker,
    now_utc: datetime,
) -> list[int]:
    async with session_factory() as session:
        users = list(
            (
                await session.execute(
                    select(User).where(
                        and_(
                            User.is_active.is_(True),
                            User.level_band.is_not(None),
                            User.timezone.is_not(None),
                            User.daily_delivery_time.is_not(None),
                        )
                    )
                )
            ).scalars()
        )
    return [user.id for user in users if user_is_due_for_delivery(user, now_utc)]


async def deliver_daily_lesson_for_user(
    bot: Bot,
    session_factory: async_sessionmaker,
    user_id: int,
    now_utc: datetime,
) -> bool:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        if user is None or user.timezone is None:
            return False

        local_today = _local_now(now_utc, user.timezone).date()
        lesson = await create_or_get_daily_lesson(session, user_id, lesson_date=local_today, now=now_utc)
        if lesson is None:
            return False

        lesson = await session.get(DailyLesson, lesson.id)
        if lesson is None:
            return False
        if lesson.delivered_at is not None:
            return False

        summary = await get_session_summary(session, "daily", lesson.id)
        next_card = await get_next_session_card(session, "daily", lesson.id)
        if next_card is None:
            lesson.status = "completed"
            lesson.delivered_at = now_utc
            await session.commit()
            await bot.send_message(user.telegram_user_id, format_summary(summary))
            return True

        await bot.send_message(user.telegram_user_id, daily_intro_text(summary))
        await bot.send_message(
            user.telegram_user_id,
            format_item_card(next_card),
            reply_markup=practice_markup(next_card),
        )

        lesson.delivered_at = now_utc
        await session.commit()
        logger.info("Delivered daily lesson", extra={"user_id": user_id, "lesson_id": lesson.id})
        return True


async def run_delivery_tick(
    bot: Bot,
    session_factory: async_sessionmaker,
    now_utc: datetime | None = None,
) -> int:
    now_utc = now_utc or datetime.now(UTC).replace(second=0, microsecond=0)
    delivered_count = 0
    due_user_ids = await load_due_user_ids(session_factory, now_utc)
    for user_id in due_user_ids:
        try:
            delivered = await deliver_daily_lesson_for_user(bot, session_factory, user_id, now_utc)
        except Exception:
            logger.exception("Delivery failed", extra={"user_id": user_id})
            continue
        if delivered:
            delivered_count += 1
    return delivered_count
