import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from collocation_coach.application.events import record_product_event
from collocation_coach.storage.models import CollocationItem, ContentFeedback

FEEDBACK_TYPES = (
    "wrong_or_broken",
    "too_hard",
    "unnatural_example",
)
FEEDBACK_TYPE_LABELS = (
    ("wrong_or_broken", "Broken"),
    ("too_hard", "Too hard"),
    ("unnatural_example", "Unnatural"),
)


@dataclass(frozen=True, slots=True)
class FeedbackExportRow:
    created_at: datetime
    feedback_type: str
    user_id: int
    collocation_item_id: int
    collocation_external_key: str
    phrase: str
    session_type: str | None
    session_id: int | None
    session_item_id: int | None


def validate_feedback_type(value: str) -> str:
    if value not in FEEDBACK_TYPES:
        raise ValueError("Invalid feedback type")
    return value


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
    validate_feedback_type(feedback_type)

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
                select(ContentFeedback, CollocationItem)
                .join(CollocationItem, CollocationItem.id == ContentFeedback.collocation_item_id)
                .order_by(ContentFeedback.created_at.desc(), ContentFeedback.id.desc())
            )
        ).all()
    )
    return tuple(
        FeedbackExportRow(
            created_at=feedback.created_at if feedback.created_at.tzinfo is not None else feedback.created_at.replace(tzinfo=UTC),
            feedback_type=feedback.feedback_type,
            user_id=feedback.user_id,
            collocation_item_id=feedback.collocation_item_id,
            collocation_external_key=item.external_key,
            phrase=item.phrase,
            session_type=feedback.session_type,
            session_id=feedback.session_id,
            session_item_id=feedback.session_item_id,
        )
        for feedback, item in rows
    )


async def summarize_feedback_types(session: AsyncSession) -> dict[str, int]:
    rows = list(
        (
            await session.execute(
                select(ContentFeedback.feedback_type, func.count(ContentFeedback.id))
                .group_by(ContentFeedback.feedback_type)
                .order_by(ContentFeedback.feedback_type.asc())
            )
        ).all()
    )
    return {feedback_type: count for feedback_type, count in rows}


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
                "session_type": row.session_type,
                "session_id": row.session_id,
                "session_item_id": row.session_item_id,
            },
            ensure_ascii=False,
        )
        for row in rows
    )
