from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.storage.models import User


async def ensure_user(
    session: AsyncSession,
    telegram_user: TelegramUser,
    default_timezone: str,
) -> tuple[User, bool]:
    user = await session.scalar(
        select(User).where(User.telegram_user_id == telegram_user.id)
    )
    created = False
    if user is None:
        user = User(
            telegram_user_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            language_code=telegram_user.language_code,
            timezone=default_timezone,
        )
        session.add(user)
        created = True
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.language_code = telegram_user.language_code

    await session.commit()
    await session.refresh(user)
    return user, created
