import asyncio
import argparse
from datetime import UTC, datetime

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from collocation_coach.application.events import summarize_product_events
from collocation_coach.application.feedback import (
    feedback_rows_to_csv,
    feedback_rows_to_jsonl,
    load_feedback_export_rows,
    summarize_feedback_types,
)
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


def _print_feedback_export(output_format: str) -> None:
    asyncio.run(_run_feedback_export(output_format))


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


async def _run_feedback_export(output_format: str) -> None:
    settings = ReportingSettings()
    database = Database(settings.database_url)
    await database.initialize()
    try:
        async with database.session_factory() as session:
            rows = await load_feedback_export_rows(session)
            summary = await summarize_feedback_types(session)
    finally:
        await database.dispose()

    print("Feedback summary")
    if not summary:
        print("- total: 0")
    else:
        for feedback_type, count in summary.items():
            print(f"- {feedback_type}: {count}")
    print("")
    print("Feedback export")
    if output_format == "jsonl":
        print(feedback_rows_to_jsonl(rows))
    else:
        print(feedback_rows_to_csv(rows), end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local reporting for Collocation Coach")
    parser.add_argument(
        "command",
        nargs="?",
        default="summary",
        choices=("summary", "feedback-export"),
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("csv", "jsonl"),
        default="csv",
    )
    args = parser.parse_args()

    if args.command == "feedback-export":
        _print_feedback_export(args.output_format)
        return
    _print_summary()


if __name__ == "__main__":
    main()
