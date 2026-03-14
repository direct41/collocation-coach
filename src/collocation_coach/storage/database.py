from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from collocation_coach.storage.models import Base


class Database:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url, future=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await self._run_startup_upgrades(connection)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def _run_startup_upgrades(self, connection) -> None:
        user_columns = await connection.run_sync(
            lambda sync_connection: {
                column["name"] for column in inspect(sync_connection).get_columns("users")
            }
        )
        if "pace_mode" not in user_columns:
            await connection.execute(
                text("ALTER TABLE users ADD COLUMN pace_mode VARCHAR(16) DEFAULT 'standard'")
            )
            await connection.execute(
                text("UPDATE users SET pace_mode = 'standard' WHERE pace_mode IS NULL")
            )
