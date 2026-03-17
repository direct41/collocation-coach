import asyncio
from datetime import UTC, datetime

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from collocation_coach.application.events import summarize_product_events
from collocation_coach.storage.database import Database


class ReportingSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(alias="DATABASE_URL")


def _print_summary() -> None:
    asyncio.run(_run_summary())


async def _run_summary() -> None:
    settings = ReportingSettings()
    database = Database(settings.database_url)
    await database.initialize()
    try:
        async with database.session_factory() as session:
            summary = await summarize_product_events(session, now=datetime.now(UTC))
    finally:
        await database.dispose()

    print("Core event summary")
    for row in summary.counts:
        print(
            f"- {row.event_name}: total={row.total_count}, last_7_days={row.last_7_days_count}"
        )
    print(
        f"- return_prompt_conversions_within_72h: "
        f"{summary.return_completions_within_72h}/{summary.return_prompts}"
    )


def main() -> None:
    _print_summary()


if __name__ == "__main__":
    main()
