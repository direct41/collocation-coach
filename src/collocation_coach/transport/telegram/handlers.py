import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.config import Settings
from collocation_coach.storage.models import User

logger = logging.getLogger(__name__)


def create_router(
    settings: Settings,
    session_factory: async_sessionmaker,
) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def start_handler(message: Message) -> None:
        from_user = message.from_user
        if from_user is None:
            return

        async with session_factory() as session:
            user = await session.scalar(
                select(User).where(User.telegram_user_id == from_user.id)
            )
            if user is None:
                user = User(
                    telegram_user_id=from_user.id,
                    username=from_user.username,
                    first_name=from_user.first_name,
                    language_code=from_user.language_code,
                    timezone=settings.default_timezone,
                )
                session.add(user)
                created = True
            else:
                user.username = from_user.username
                user.first_name = from_user.first_name
                user.language_code = from_user.language_code
                created = False

            await session.commit()

        logger.info("Handled /start", extra={"telegram_user_id": from_user.id})

        if created:
            text = (
                "Welcome to Collocation Coach.\n\n"
                "The MVP foundation is live: content is loaded and your account is saved.\n"
                "Next phases will add onboarding, daily lessons, and review."
            )
        else:
            text = (
                "You are already registered in Collocation Coach.\n\n"
                "Current foundation commands:\n"
                "/start\n"
                "/help"
            )

        await message.answer(text)

    @router.message(Command("help"))
    async def help_handler(message: Message) -> None:
        await message.answer(
            "Collocation Coach is an open-source Telegram bot for daily collocation practice.\n\n"
            "Current available commands:\n"
            "/start - register or reopen the bot\n"
            "/help - show this help message"
        )

    return router
