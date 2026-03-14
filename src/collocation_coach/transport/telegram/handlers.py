from datetime import UTC, date, datetime
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.application.onboarding import onboarding_complete
from collocation_coach.application.study import (
    apply_rating,
    create_or_get_daily_lesson,
    create_or_get_review_session,
    get_next_session_card,
    get_session_item_card,
    get_session_summary,
    load_user_by_telegram_id,
    record_answer,
)
from collocation_coach.application.users import ensure_user
from collocation_coach.config import Settings
from collocation_coach.storage.models import User
from collocation_coach.transport.telegram.callbacks import (
    DeliveryTimeSelectionCallback,
    LevelSelectionCallback,
    SettingsActionCallback,
    StudyActionCallback,
    TimezoneSelectionCallback,
)
from collocation_coach.transport.telegram.keyboards import (
    answer_keyboard,
    delivery_time_keyboard,
    level_keyboard,
    rating_keyboard,
    settings_keyboard,
    timezone_keyboard,
)
from collocation_coach.transport.telegram.messages import (
    daily_intro_text,
    format_feedback,
    format_item_card,
    format_practice,
    format_settings,
    format_summary,
    practice_markup,
)

logger = logging.getLogger(__name__)


def _is_ready(user: User) -> bool:
    return onboarding_complete(user.level_band, user.timezone, user.daily_delivery_time)


async def _send_onboarding_next_step(message: Message, user: User, default_timezone: str) -> None:
    if not user.level_band:
        await message.answer(
            "Choose your current level band.",
            reply_markup=level_keyboard(),
        )
        return
    if not user.timezone or (user.timezone == default_timezone and not user.daily_delivery_time):
        await message.answer(
            "Choose your timezone.",
            reply_markup=timezone_keyboard(),
        )
        return
    if not user.daily_delivery_time:
        await message.answer(
            "Choose when to receive your daily lesson.",
            reply_markup=delivery_time_keyboard(),
        )
        return
    await message.answer(
        "Onboarding complete.\n\n"
        f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time)}\n\n"
        "Use /today to start your current lesson.",
    )


async def _send_next_card(
    session_factory: async_sessionmaker,
    target_message: Message,
    session_type: str,
    session_id: int,
) -> None:
    async with session_factory() as session:
        card = await get_next_session_card(session, session_type, session_id)
        if card is None:
            summary = await get_session_summary(session, session_type, session_id)
            await target_message.answer(format_summary(summary))
            return

    await target_message.answer(
        format_item_card(card),
        reply_markup=practice_markup(card),
    )


def create_router(
    settings: Settings,
    session_factory: async_sessionmaker,
) -> Router:
    router = Router()

    @router.message(CommandStart())
    async def start_handler(message: Message) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        async with session_factory() as session:
            user, created = await ensure_user(session, from_user, settings.default_timezone)

        logger.info("Handled /start", extra={"telegram_user_id": from_user.id})

        if created or not _is_ready(user):
            await message.answer(
                "Welcome to Collocation Coach.\n\n"
                "Let’s set up your daily collocation practice."
            )
            await _send_onboarding_next_step(message, user, settings.default_timezone)
            return

        await message.answer(
            "You are already set up.\n\n"
            f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time)}\n\n"
            "Use /today to open today's lesson or /settings to change preferences."
        )

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Collocation Coach is an open-source Telegram bot for daily collocation practice.\n\n"
            "Commands:\n"
            "/start - register or reopen the bot\n"
            "/today - open today's lesson\n"
            "/review - start a review session\n"
            "/settings - change your preferences\n"
            "/help - show this help message\n\n"
            "Ratings:\n"
            "Know - this item felt solid\n"
            "Unsure - show it again tomorrow\n"
            "Repeat - keep it due right away"
        )

    @router.message(Command("today"))
    async def today_handler(message: Message) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, from_user.id)
            if user is None:
                await message.answer("Use /start first.")
                return
            if not _is_ready(user):
                await message.answer("Finish onboarding first.")
                await _send_onboarding_next_step(message, user, settings.default_timezone)
                return

            lesson = await create_or_get_daily_lesson(
                session,
                user.id,
                lesson_date=date.today(),
                now=datetime.now(UTC),
            )
            if lesson is None:
                await message.answer("No lesson content is available for your current level yet.")
                return

            summary = await get_session_summary(session, "daily", lesson.id)
            if summary.completed:
                await message.answer(format_summary(summary))
                return

            if lesson.delivered_at is None:
                lesson.delivered_at = datetime.now(UTC)
                await session.commit()
            await message.answer(daily_intro_text(summary))

        await _send_next_card(session_factory, message, "daily", lesson.id)

    @router.message(Command("review"))
    async def review_handler(message: Message) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, from_user.id)
            if user is None:
                await message.answer("Use /start first.")
                return
            if not _is_ready(user):
                await message.answer("Finish onboarding first.")
                await _send_onboarding_next_step(message, user, settings.default_timezone)
                return

            review_session = await create_or_get_review_session(
                session,
                user.id,
                now=datetime.now(UTC),
            )
            if review_session is None:
                await message.answer("Your review queue is empty right now.")
                return

        await message.answer("Review session started.")
        await _send_next_card(session_factory, message, "review", review_session.id)

    @router.message(Command("settings"))
    async def settings_handler(message: Message) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, from_user.id)
            if user is None:
                await message.answer("Use /start first.")
                return

            await message.answer(
                format_settings(user.level_band, user.timezone, user.daily_delivery_time),
                reply_markup=settings_keyboard(),
            )

    @router.callback_query(LevelSelectionCallback.filter())
    async def level_selected(callback: CallbackQuery, callback_data: LevelSelectionCallback) -> None:
        if callback.from_user is None or callback.message is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            user.level_band = callback_data.level_band
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(f"Level set to {callback_data.level_band}.")
        if not _is_ready(user):
            if not user.timezone or user.timezone == settings.default_timezone:
                await callback.message.answer(
                    "Choose your timezone.",
                    reply_markup=timezone_keyboard(),
                )
            else:
                await callback.message.answer(
                    "Choose your daily lesson time.",
                    reply_markup=delivery_time_keyboard(),
                )
        else:
            await callback.message.answer(
                f"Updated.\n\n{format_settings(user.level_band, user.timezone, user.daily_delivery_time)}"
            )
        await callback.answer()

    @router.callback_query(TimezoneSelectionCallback.filter())
    async def timezone_selected(
        callback: CallbackQuery,
        callback_data: TimezoneSelectionCallback,
    ) -> None:
        if callback.from_user is None or callback.message is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            user.timezone = callback_data.timezone
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(f"Timezone set to {callback_data.timezone}.")
        if not user.daily_delivery_time:
            await callback.message.answer(
                "Choose your daily lesson time.",
                reply_markup=delivery_time_keyboard(),
            )
        else:
            await callback.message.answer(
                f"Updated.\n\n{format_settings(user.level_band, user.timezone, user.daily_delivery_time)}"
            )
        await callback.answer()

    @router.callback_query(DeliveryTimeSelectionCallback.filter())
    async def delivery_time_selected(
        callback: CallbackQuery,
        callback_data: DeliveryTimeSelectionCallback,
    ) -> None:
        if callback.from_user is None or callback.message is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            user.daily_delivery_time = callback_data.delivery_time
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(
            "Daily delivery time saved.\n\n"
            f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time)}\n\n"
            "Use /today to start your lesson."
        )
        await callback.answer()

    @router.callback_query(SettingsActionCallback.filter())
    async def settings_action(
        callback: CallbackQuery,
        callback_data: SettingsActionCallback,
    ) -> None:
        if callback.message is None:
            return

        if callback_data.action == "level":
            await callback.message.answer("Choose a new level band.", reply_markup=level_keyboard())
        elif callback_data.action == "timezone":
            await callback.message.answer("Choose a new timezone.", reply_markup=timezone_keyboard())
        else:
            await callback.message.answer(
                "Choose a new delivery time.",
                reply_markup=delivery_time_keyboard(),
            )
        await callback.answer()

    @router.callback_query(StudyActionCallback.filter())
    async def study_action(
        callback: CallbackQuery,
        callback_data: StudyActionCallback,
    ) -> None:
        if callback.message is None or callback.from_user is None:
            return

        session_type = "daily" if callback_data.session_type == "daily" else "review"

        if callback_data.action == "practice":
            async with session_factory() as session:
                card = await get_session_item_card(
                    session,
                    session_type,
                    callback_data.session_id,
                    callback_data.item_id,
                )
            if card is None:
                await callback.answer("This item is no longer available.", show_alert=True)
                return
            await callback.message.edit_text(
                format_practice(card),
                reply_markup=answer_keyboard(
                    card.session_type,
                    card.session_id,
                    card.session_item_id,
                    card.options,
                ),
            )
            await callback.answer()
            return

        if callback_data.action == "answer":
            async with session_factory() as session:
                card = await record_answer(
                    session,
                    session_type,
                    callback_data.session_id,
                    callback_data.item_id,
                    int(callback_data.value),
                )
            if card is None:
                await callback.answer("This item is no longer available.", show_alert=True)
                return

            await callback.message.edit_text(
                format_feedback(card, int(callback_data.value)),
                reply_markup=rating_keyboard(
                    card.session_type,
                    card.session_id,
                    card.session_item_id,
                ),
            )
            await callback.answer()
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.answer("Use /start first.", show_alert=True)
                return
            summary = await apply_rating(
                session,
                user.id,
                session_type,
                callback_data.session_id,
                callback_data.item_id,
                callback_data.value,  # type: ignore[arg-type]
                now=datetime.now(UTC),
            )
            next_card = await get_next_session_card(
                session,
                session_type,
                callback_data.session_id,
            )

        await callback.message.edit_text(f"Saved rating: {callback_data.value}.")
        if next_card is None:
            await callback.message.answer(format_summary(summary))
        else:
            await callback.message.answer(
                format_item_card(next_card),
                reply_markup=practice_markup(next_card),
            )
        await callback.answer()

    return router
