import csv
import io
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.application.events import record_product_event
from collocation_coach.storage.models import CollocationItem, ContentFeedback, LessonUnit

FEEDBACK_TYPES = (
    "wrong_or_broken",
    "unclear",
    "not_my_level",
)
LEGACY_FEEDBACK_TYPE_MAP = {
    "wrong_or_broken": "wrong_or_broken",
    "too_hard": "not_my_level",
    "unnatural_example": "unclear",
    "unclear": "unclear",
    "not_my_level": "not_my_level",
}
DEFAULT_CONTENT_FEEDBACK_TYPE = "wrong_or_broken"
REPORT_PROBLEM_LABEL = "Report a problem"


@dataclass(frozen=True, slots=True)
class FeedbackExportRow:
    created_at: datetime
    feedback_type: str
    user_id: int
    collocation_item_id: int
    collocation_external_key: str
    phrase: str
    level_band: str
    lesson_unit_key: str
    lesson_topic: str
    session_type: str | None
    session_id: int | None
    session_item_id: int | None


@dataclass(frozen=True, slots=True)
class MostReportedContentIssue:
    collocation_item_id: int
    collocation_external_key: str
    phrase: str
    level_band: str
    lesson_unit_key: str
    lesson_topic: str
    report_count: int


@dataclass(frozen=True, slots=True)
class ContentIssueSummary:
    total_reports: int
    counts_by_type: dict[str, int]
    most_reported_items: tuple[MostReportedContentIssue, ...]


def normalize_feedback_type(value: str | None) -> str:
    candidate = value or DEFAULT_CONTENT_FEEDBACK_TYPE
    normalized = LEGACY_FEEDBACK_TYPE_MAP.get(candidate, candidate)
    if normalized not in FEEDBACK_TYPES:
        raise ValueError("Invalid feedback type")
    return normalized


def validate_feedback_type(value: str) -> str:
    return normalize_feedback_type(value)


def default_feedback_type() -> str:
    return DEFAULT_CONTENT_FEEDBACK_TYPE


def feedback_key_for_submission(
    *,
    user_id: int,
    collocation_item_id: int,
    feedback_type: str,
    session_type: str | None,
    session_id: int | None,
    session_item_id: int | None,
) -> str:
    return (
        f"{user_id}:{collocation_item_id}:{feedback_type}:"
        f"{session_type or 'unknown'}:{session_id or 0}:{session_item_id or 0}"
    )


async def submit_content_feedback(
    session: AsyncSession,
    *,
    user_id: int,
    collocation_item_id: int,
    feedback_type: str,
    session_type: str | None = None,
    session_id: int | None = None,
    session_item_id: int | None = None,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(UTC)
    feedback_type = normalize_feedback_type(feedback_type)

    item = await session.get(CollocationItem, collocation_item_id)
    if item is None:
        raise ValueError("Collocation item not found")

    feedback_key = feedback_key_for_submission(
        user_id=user_id,
        collocation_item_id=collocation_item_id,
        feedback_type=feedback_type,
        session_type=session_type,
        session_id=session_id,
        session_item_id=session_item_id,
    )
    existing = await session.scalar(
        select(ContentFeedback).where(ContentFeedback.feedback_key == feedback_key)
    )
    if existing is not None:
        return False

    session.add(
        ContentFeedback(
            feedback_key=feedback_key,
            user_id=user_id,
            collocation_item_id=collocation_item_id,
            feedback_type=feedback_type,
            session_type=session_type,
            session_id=session_id,
            session_item_id=session_item_id,
            created_at=now,
        )
    )
    await record_product_event(
        session,
        user_id,
        "content_feedback_submitted",
        occurred_at=now,
        metadata={
            "feedback_type": feedback_type,
            "collocation_item_id": collocation_item_id,
            "session_type": session_type or "",
            "session_id": session_id or 0,
            "session_item_id": session_item_id or 0,
        },
        event_key=f"content-feedback:{feedback_key}",
    )
    return True


async def load_feedback_export_rows(session: AsyncSession) -> tuple[FeedbackExportRow, ...]:
    rows = list(
        (
            await session.execute(
                select(ContentFeedback, CollocationItem, LessonUnit)
                .join(CollocationItem, CollocationItem.id == ContentFeedback.collocation_item_id)
                .join(LessonUnit, LessonUnit.id == CollocationItem.lesson_unit_id)
                .order_by(ContentFeedback.created_at.desc(), ContentFeedback.id.desc())
            )
        ).all()
    )
    return tuple(
        FeedbackExportRow(
            created_at=feedback.created_at if feedback.created_at.tzinfo is not None else feedback.created_at.replace(tzinfo=UTC),
            feedback_type=normalize_feedback_type(feedback.feedback_type),
            user_id=feedback.user_id,
            collocation_item_id=feedback.collocation_item_id,
            collocation_external_key=item.external_key,
            phrase=item.phrase,
            level_band=lesson_unit.level_band,
            lesson_unit_key=lesson_unit.external_key,
            lesson_topic=lesson_unit.topic,
            session_type=feedback.session_type,
            session_id=feedback.session_id,
            session_item_id=feedback.session_item_id,
        )
        for feedback, item, lesson_unit in rows
    )


async def summarize_feedback_types(session: AsyncSession) -> dict[str, int]:
    rows = await load_feedback_export_rows(session)
    counts = Counter(row.feedback_type for row in rows)
    return {
        feedback_type: counts[feedback_type]
        for feedback_type in FEEDBACK_TYPES
        if counts[feedback_type] > 0
    }


async def summarize_content_issues(
    session: AsyncSession,
    *,
    top_n: int = 5,
) -> ContentIssueSummary:
    rows = await load_feedback_export_rows(session)
    counts_by_type = await summarize_feedback_types(session)
    issue_counts: dict[int, MostReportedContentIssue] = {}

    for row in rows:
        existing = issue_counts.get(row.collocation_item_id)
        if existing is None:
            issue_counts[row.collocation_item_id] = MostReportedContentIssue(
                collocation_item_id=row.collocation_item_id,
                collocation_external_key=row.collocation_external_key,
                phrase=row.phrase,
                level_band=row.level_band,
                lesson_unit_key=row.lesson_unit_key,
                lesson_topic=row.lesson_topic,
                report_count=1,
            )
            continue
        issue_counts[row.collocation_item_id] = MostReportedContentIssue(
            collocation_item_id=existing.collocation_item_id,
            collocation_external_key=existing.collocation_external_key,
            phrase=existing.phrase,
            level_band=existing.level_band,
            lesson_unit_key=existing.lesson_unit_key,
            lesson_topic=existing.lesson_topic,
            report_count=existing.report_count + 1,
        )

    most_reported_items = tuple(
        sorted(
            issue_counts.values(),
            key=lambda item: (-item.report_count, item.level_band, item.phrase),
        )[:top_n]
    )
    return ContentIssueSummary(
        total_reports=len(rows),
        counts_by_type=counts_by_type,
        most_reported_items=most_reported_items,
    )


def feedback_rows_to_csv(rows: tuple[FeedbackExportRow, ...]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "created_at",
            "feedback_type",
            "user_id",
            "collocation_item_id",
            "collocation_external_key",
            "phrase",
            "level_band",
            "lesson_unit_key",
            "lesson_topic",
            "session_type",
            "session_id",
            "session_item_id",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.created_at.isoformat(),
                row.feedback_type,
                row.user_id,
                row.collocation_item_id,
                row.collocation_external_key,
                row.phrase,
                row.level_band,
                row.lesson_unit_key,
                row.lesson_topic,
                row.session_type or "",
                row.session_id or "",
                row.session_item_id or "",
            ]
        )
    return output.getvalue()


def feedback_rows_to_jsonl(rows: tuple[FeedbackExportRow, ...]) -> str:
    return "\n".join(
        json.dumps(
            {
                "created_at": row.created_at.isoformat(),
                "feedback_type": row.feedback_type,
                "user_id": row.user_id,
                "collocation_item_id": row.collocation_item_id,
                "collocation_external_key": row.collocation_external_key,
                "phrase": row.phrase,
                "level_band": row.level_band,
                "lesson_unit_key": row.lesson_unit_key,
                "lesson_topic": row.lesson_topic,
                "session_type": row.session_type,
                "session_id": row.session_id,
                "session_item_id": row.session_item_id,
            },
            ensure_ascii=False,
        )
        for row in rows
    )
