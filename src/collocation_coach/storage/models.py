from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(32))
    level_band: Mapped[str | None] = mapped_column(String(32))
    pace_mode: Mapped[str] = mapped_column(String(16), default="standard", nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64))
    daily_delivery_time: Mapped[str | None] = mapped_column(String(5))
    return_mode_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_mode_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_mode_lessons_remaining: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LessonUnit(Base):
    __tablename__ = "lesson_units"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    level_band: Mapped[str] = mapped_column(String(32))
    day_number: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CollocationItem(Base):
    __tablename__ = "collocation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_unit_id: Mapped[int] = mapped_column(ForeignKey("lesson_units.id"), index=True)
    external_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phrase: Mapped[str] = mapped_column(String(255))
    translation_ru: Mapped[str] = mapped_column(Text)
    explanation_ru: Mapped[str] = mapped_column(Text)
    correct_example: Mapped[str] = mapped_column(Text)
    common_mistake: Mapped[str] = mapped_column(Text)
    mistake_explanation_ru: Mapped[str] = mapped_column(Text)
    practice_prompt: Mapped[str] = mapped_column(Text)
    option_a: Mapped[str] = mapped_column(Text)
    option_b: Mapped[str] = mapped_column(Text)
    option_c: Mapped[str] = mapped_column(Text)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DailyLesson(Base):
    __tablename__ = "daily_lessons"
    __table_args__ = (UniqueConstraint("user_id", "lesson_date", name="uq_daily_lesson_user_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    lesson_unit_id: Mapped[int] = mapped_column(ForeignKey("lesson_units.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    return_mode_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyLessonItem(Base):
    __tablename__ = "daily_lesson_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    daily_lesson_id: Mapped[int] = mapped_column(ForeignKey("daily_lessons.id"), index=True)
    collocation_item_id: Mapped[int] = mapped_column(ForeignKey("collocation_items.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(16), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_selected: Mapped[str | None] = mapped_column(Text)
    answered_correctly: Mapped[bool | None] = mapped_column(Boolean)
    self_rating: Mapped[str | None] = mapped_column(String(16))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserCollocationProgress(TimestampMixin, Base):
    __tablename__ = "user_collocation_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "collocation_item_id", name="uq_user_collocation_progress"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    collocation_item_id: Mapped[int] = mapped_column(ForeignKey("collocation_items.id"), index=True)
    times_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_rating: Mapped[str | None] = mapped_column(String(16))
    stability_stage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReviewSessionItem(Base):
    __tablename__ = "review_session_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_session_id: Mapped[int] = mapped_column(ForeignKey("review_sessions.id"), index=True)
    collocation_item_id: Mapped[int] = mapped_column(ForeignKey("collocation_items.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_selected: Mapped[str | None] = mapped_column(Text)
    answered_correctly: Mapped[bool | None] = mapped_column(Boolean)
    self_rating: Mapped[str | None] = mapped_column(String(16))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductEvent(Base):
    __tablename__ = "product_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(64), index=True)
    event_key: Mapped[str | None] = mapped_column(String(255), index=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContentFeedback(Base):
    __tablename__ = "content_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    collocation_item_id: Mapped[int] = mapped_column(ForeignKey("collocation_items.id"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    session_type: Mapped[str | None] = mapped_column(String(16))
    session_id: Mapped[int | None] = mapped_column(Integer)
    session_item_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
