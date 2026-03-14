from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
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
    timezone: Mapped[str | None] = mapped_column(String(64))
    daily_delivery_time: Mapped[str | None] = mapped_column(String(5))
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
    correct_option: Mapped[str] = mapped_column(Text)
    wrong_option_1: Mapped[str] = mapped_column(Text)
    wrong_option_2: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
