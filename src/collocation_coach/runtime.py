import asyncio
import logging
from contextlib import suppress

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.application.delivery import run_delivery_tick

logger = logging.getLogger(__name__)


async def delivery_loop(
    bot: Bot,
    session_factory: async_sessionmaker,
    interval_seconds: int = 60,
) -> None:
    while True:
        delivered_count = await run_delivery_tick(bot, session_factory)
        if delivered_count:
            logger.info("Delivery tick completed", extra={"delivered_count": delivered_count})
        await asyncio.sleep(interval_seconds)


async def stop_background_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
