import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from collocation_coach.config import load_settings
from collocation_coach.content.loader import load_all_lessons
from collocation_coach.content.seeder import seed_lessons
from collocation_coach.logging import configure_logging
from collocation_coach.runtime import delivery_loop, stop_background_task
from collocation_coach.storage.database import Database
from collocation_coach.transport.telegram.handlers import create_router
from collocation_coach.validation import collect_content_lint_warnings, validate_startup_content


async def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    lessons = load_all_lessons(settings.content_dir)
    validate_startup_content(lessons)
    lint_warnings = collect_content_lint_warnings(lessons)
    logger.info(
        "Loaded lesson files",
        extra={
            "lesson_file_count": len(lessons),
            "content_validation_warning_count": len(lint_warnings),
        },
    )

    database = Database(settings.database_url)
    await database.initialize()
    await seed_lessons(database.session_factory, lessons)

    bot = Bot(
        token=settings.telegram_bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(settings, database.session_factory))
    delivery_task = asyncio.create_task(delivery_loop(bot, database.session_factory))

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Register and open the bot"),
            BotCommand(command="today", description="Open today's lesson"),
            BotCommand(command="review", description="Start a review session"),
            BotCommand(command="progress", description="Show current learning progress"),
            BotCommand(command="settings", description="Change preferences"),
            BotCommand(command="help", description="Show current commands"),
        ]
    )

    try:
        logger.info("Starting polling")
        await dispatcher.start_polling(bot)
    finally:
        await stop_background_task(delivery_task)
        await bot.session.close()
        await database.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
