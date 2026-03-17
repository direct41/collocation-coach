from datetime import UTC, datetime
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.application.events import record_product_event
from collocation_coach.application.feedback import submit_content_feedback
from collocation_coach.application.onboarding import (
    decode_delivery_time,
    onboarding_complete,
    validate_delivery_time_option,
    validate_timezone_option,
)
from collocation_coach.application.progress import build_progress_snapshot
from collocation_coach.application.study import (
    activate_return_mode_if_lapsed,
    apply_rating,
    create_or_get_daily_lesson,
    create_or_get_review_session,
    has_extra_practice_available,
    get_next_session_card,
    get_daily_lesson_level_band,
    get_session_item_card,
    get_session_summary,
    load_user_by_telegram_id,
    record_answer,
)
from collocation_coach.application.time import local_today
from collocation_coach.application.users import ensure_user
from collocation_coach.config import Settings
from collocation_coach.storage.models import DailyLesson, User
from collocation_coach.transport.telegram.callbacks import (
    DeliveryTimeSelectionCallback,
    LevelSelectionCallback,
    PaceSelectionCallback,
    PracticeMenuCallback,
    SettingsActionCallback,
    StudyActionCallback,
    TimezoneSelectionCallback,
)
from collocation_coach.transport.telegram.keyboards import (
    answer_keyboard,
    delivery_time_keyboard,
    level_keyboard,
    pace_keyboard,
    rating_keyboard,
    settings_keyboard,
    timezone_keyboard,
)
from collocation_coach.transport.telegram.messages import (
    daily_intro_text,
    extra_practice_markup,
    extra_practice_prompt,
    format_feedback,
    format_item_card,
    format_practice,
    format_progress,
    format_settings,
    format_summary,
    practice_markup,
    return_intro_text,
)

logger = logging.getLogger(__name__)


def _is_ready(user: User) -> bool:
    return onboarding_complete(user.level_band, user.timezone, user.daily_delivery_time)


async def _record_user_state_events(
    session,
    user: User,
    *,
    changed_field: str,
    changed: bool,
    was_ready: bool,
    occurred_at: datetime,
) -> None:
    if changed and was_ready:
        await record_product_event(
            session,
            user.id,
            "settings_updated",
            occurred_at=occurred_at,
            metadata={"field": changed_field},
        )
    if not was_ready and _is_ready(user):
        await record_product_event(
            session,
            user.id,
            "onboarding_completed",
            occurred_at=occurred_at,
            metadata={
                "level_band": user.level_band or "",
                "timezone": user.timezone or "",
                "delivery_time": user.daily_delivery_time or "",
            },
            event_key="onboarding-completed",
        )


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
        f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}\n\n"
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
            f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}\n\n"
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
            "/progress - see current learning status\n"
            "/settings - change your preferences\n"
            "/help - show this help message\n\n"
            "Pace modes:\n"
            "Light - fewer new items\n"
            "Standard - balanced daily load\n"
            "Intensive - more new items\n\n"
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

            now_utc = datetime.now(UTC)
            lesson_date = local_today(now_utc, user.timezone or settings.default_timezone)
            missed_days = await activate_return_mode_if_lapsed(session, user, lesson_date, now_utc)
            lesson = await create_or_get_daily_lesson(
                session,
                user.id,
                lesson_date=lesson_date,
                now=now_utc,
            )
            if lesson is None:
                if await has_extra_practice_available(session, user.id):
                    await message.answer(
                        "No new main session is available right now.",
                    )
                    await message.answer(
                        extra_practice_prompt(),
                        reply_markup=extra_practice_markup(),
                    )
                else:
                    await message.answer("No lesson content is available for your current level yet.")
                return

            summary = await get_session_summary(session, "daily", lesson.id)
            lesson_level_band = await get_daily_lesson_level_band(session, lesson.id)
            if summary.completed:
                if lesson_level_band != user.level_band:
                    await message.answer(
                        "Today's lesson was already completed with your previous level.\n"
                        "Your new level will apply to the next generated lesson."
                    )
                await message.answer(format_summary(summary))
                if not lesson.return_mode_applied and await has_extra_practice_available(session, user.id):
                    await message.answer(
                        extra_practice_prompt(),
                        reply_markup=extra_practice_markup(),
                    )
                return

            should_commit = False
            if lesson.delivered_at is None:
                lesson.delivered_at = now_utc
                should_commit = True
                await record_product_event(
                    session,
                    user.id,
                    "daily_lesson_started",
                    occurred_at=now_utc,
                    metadata={
                        "daily_lesson_id": lesson.id,
                        "source": "today",
                        "return_mode": lesson.return_mode_applied,
                    },
                    event_key=f"daily-lesson-started:{lesson.id}",
                )
            if missed_days is not None:
                await record_product_event(
                    session,
                    user.id,
                    "return_prompt_shown",
                    occurred_at=now_utc,
                    metadata={
                        "daily_lesson_id": lesson.id,
                        "missed_days": missed_days,
                        "source": "today",
                    },
                    event_key=f"return-prompt:{lesson.id}",
                )
                should_commit = True
            if should_commit:
                await session.commit()
            if missed_days is not None:
                await message.answer(return_intro_text(missed_days))
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
                if await has_extra_practice_available(session, user.id):
                    await message.answer(
                        extra_practice_prompt(),
                        reply_markup=extra_practice_markup(),
                    )
                return

        await message.answer("Review session started.")
        await _send_next_card(session_factory, message, "review", review_session.id)

    @router.message(Command("progress"))
    async def progress_handler(message: Message) -> None:
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

            now_utc = datetime.now(UTC)
            snapshot = await build_progress_snapshot(session, user, now_utc=now_utc)
            await record_product_event(
                session,
                user.id,
                "progress_viewed",
                occurred_at=now_utc,
                metadata={"level_band": user.level_band or "", "pace_mode": user.pace_mode},
            )
            await session.commit()

        await message.answer(format_progress(snapshot))

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
                format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode),
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
            occurred_at = datetime.now(UTC)
            was_ready = _is_ready(user)
            changed = user.level_band != callback_data.level_band
            user.level_band = callback_data.level_band
            await _record_user_state_events(
                session,
                user,
                changed_field="level_band",
                changed=changed,
                was_ready=was_ready,
                occurred_at=occurred_at,
            )
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
                f"Updated.\n\n{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}"
            )
        await callback.answer()

    @router.callback_query(TimezoneSelectionCallback.filter())
    async def timezone_selected(
        callback: CallbackQuery,
        callback_data: TimezoneSelectionCallback,
    ) -> None:
        if callback.from_user is None or callback.message is None:
            return
        try:
            selected_timezone = validate_timezone_option(callback_data.timezone)
        except ValueError:
            await callback.answer("Unsupported timezone option.", show_alert=True)
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            occurred_at = datetime.now(UTC)
            was_ready = _is_ready(user)
            changed = user.timezone != selected_timezone
            user.timezone = selected_timezone
            await _record_user_state_events(
                session,
                user,
                changed_field="timezone",
                changed=changed,
                was_ready=was_ready,
                occurred_at=occurred_at,
            )
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(f"Timezone set to {selected_timezone}.")
        if not user.daily_delivery_time:
            await callback.message.answer(
                "Choose your daily lesson time.",
                reply_markup=delivery_time_keyboard(),
            )
        else:
            await callback.message.answer(
                f"Updated.\n\n{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}"
            )
        await callback.answer()

    @router.callback_query(PaceSelectionCallback.filter())
    async def pace_selected(callback: CallbackQuery, callback_data: PaceSelectionCallback) -> None:
        if callback.from_user is None or callback.message is None:
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            occurred_at = datetime.now(UTC)
            was_ready = _is_ready(user)
            changed = user.pace_mode != callback_data.pace_mode
            user.pace_mode = callback_data.pace_mode
            await _record_user_state_events(
                session,
                user,
                changed_field="pace_mode",
                changed=changed,
                was_ready=was_ready,
                occurred_at=occurred_at,
            )
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(f"Pace set to {callback_data.pace_mode}.")
        await callback.message.answer(
            f"Updated.\n\n{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}"
        )
        await callback.answer()

    @router.callback_query(DeliveryTimeSelectionCallback.filter())
    async def delivery_time_selected(
        callback: CallbackQuery,
        callback_data: DeliveryTimeSelectionCallback,
    ) -> None:
        if callback.from_user is None or callback.message is None:
            return
        try:
            next_delivery_time = validate_delivery_time_option(
                decode_delivery_time(callback_data.delivery_time)
            )
        except ValueError:
            await callback.answer("Unsupported delivery time option.", show_alert=True)
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.message.answer("Use /start first.")
                await callback.answer()
                return
            occurred_at = datetime.now(UTC)
            was_ready = _is_ready(user)
            changed = user.daily_delivery_time != next_delivery_time
            user.daily_delivery_time = next_delivery_time
            await _record_user_state_events(
                session,
                user,
                changed_field="daily_delivery_time",
                changed=changed,
                was_ready=was_ready,
                occurred_at=occurred_at,
            )
            await session.commit()
            await session.refresh(user)

        await callback.message.edit_text(
            "Daily delivery time saved.\n\n"
            f"{format_settings(user.level_band, user.timezone, user.daily_delivery_time, user.pace_mode)}\n\n"
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
        elif callback_data.action == "pace":
            await callback.message.answer("Choose your pace.", reply_markup=pace_keyboard())
        elif callback_data.action == "timezone":
            await callback.message.answer("Choose a new timezone.", reply_markup=timezone_keyboard())
        else:
            await callback.message.answer(
                "Choose a new delivery time.",
                reply_markup=delivery_time_keyboard(),
            )
        await callback.answer()

    @router.callback_query(PracticeMenuCallback.filter())
    async def practice_menu_action(
        callback: CallbackQuery,
        callback_data: PracticeMenuCallback,
    ) -> None:
        if callback.message is None or callback.from_user is None:
            return
        if callback_data.action != "extra":
            await callback.answer()
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.answer("Use /start first.", show_alert=True)
                return
            review_session = await create_or_get_review_session(
                session,
                user.id,
                now=datetime.now(UTC),
                include_extra=True,
            )
            if review_session is None:
                await callback.message.answer("No extra practice is available yet.")
                await callback.answer()
                return

        await callback.message.answer("Extra practice started.")
        await _send_next_card(session_factory, callback.message, "review", review_session.id)
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

        if callback_data.action == "feedback":
            async with session_factory() as session:
                user = await load_user_by_telegram_id(session, callback.from_user.id)
                if user is None:
                    await callback.answer("Use /start first.", show_alert=True)
                    return
                card = await get_session_item_card(
                    session,
                    session_type,
                    callback_data.session_id,
                    callback_data.item_id,
                )
                if card is None:
                    await callback.answer("This item is no longer available.", show_alert=True)
                    return
                try:
                    created = await submit_content_feedback(
                        session,
                        user_id=user.id,
                        collocation_item_id=card.collocation_item_id,
                        feedback_type=callback_data.value,
                        session_type=card.session_type,
                        session_id=card.session_id,
                        session_item_id=card.session_item_id,
                        now=datetime.now(UTC),
                    )
                except ValueError:
                    await callback.answer("Unsupported feedback option.", show_alert=True)
                    return
                await session.commit()

            await callback.answer(
                "Feedback saved." if created else "Feedback already saved for this card."
            )
            return

        async with session_factory() as session:
            user = await load_user_by_telegram_id(session, callback.from_user.id)
            if user is None:
                await callback.answer("Use /start first.", show_alert=True)
                return
            daily_lesson = None
            if session_type == "daily":
                daily_lesson = await session.get(DailyLesson, callback_data.session_id)
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
            if session_type == "daily" and daily_lesson is not None and not daily_lesson.return_mode_applied:
                async with session_factory() as follow_up_session:
                    user = await load_user_by_telegram_id(follow_up_session, callback.from_user.id)
                    if user is not None and await has_extra_practice_available(follow_up_session, user.id):
                        await callback.message.answer(
                            extra_practice_prompt(),
                            reply_markup=extra_practice_markup(),
                        )
        else:
            await callback.message.answer(
                format_item_card(next_card),
                reply_markup=practice_markup(next_card),
            )
        await callback.answer()

    return router
