from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from collocation_coach.application.onboarding import (
    DELIVERY_TIME_OPTIONS,
    LEVEL_BANDS,
    PACE_MODES,
    TIMEZONE_OPTIONS,
    encode_delivery_time,
)
from collocation_coach.transport.telegram.callbacks import (
    DeliveryTimeSelectionCallback,
    LevelSelectionCallback,
    PaceSelectionCallback,
    PracticeMenuCallback,
    SettingsActionCallback,
    StudyActionCallback,
    TimezoneSelectionCallback,
)


def level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=LevelSelectionCallback(level_band=value).pack(),
                )
            ]
            for value, label in LEVEL_BANDS
        ]
    )


def timezone_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=TimezoneSelectionCallback(timezone=value).pack(),
                )
            ]
            for value, label in TIMEZONE_OPTIONS
        ]
    )


def pace_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=PaceSelectionCallback(pace_mode=value).pack(),
                )
            ]
            for value, label in PACE_MODES
        ]
    )


def delivery_time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=value,
                    callback_data=DeliveryTimeSelectionCallback(
                        delivery_time=encode_delivery_time(value)
                    ).pack(),
                )
                for value in DELIVERY_TIME_OPTIONS[:2]
            ],
            [
                InlineKeyboardButton(
                    text=value,
                    callback_data=DeliveryTimeSelectionCallback(
                        delivery_time=encode_delivery_time(value)
                    ).pack(),
                )
                for value in DELIVERY_TIME_OPTIONS[2:]
            ],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Change level",
                    callback_data=SettingsActionCallback(action="level").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Change pace",
                    callback_data=SettingsActionCallback(action="pace").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Change timezone",
                    callback_data=SettingsActionCallback(action="timezone").pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="Change delivery time",
                    callback_data=SettingsActionCallback(action="delivery_time").pack(),
                )
            ],
        ]
    )


def practice_start_keyboard(session_type: str, session_id: int, item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Practice",
                    callback_data=StudyActionCallback(
                        session_type=session_type,
                        session_id=session_id,
                        item_id=item_id,
                        action="practice",
                    ).pack(),
                )
            ]
        ]
    )


def answer_keyboard(
    session_type: str,
    session_id: int,
    item_id: int,
    options: tuple[str, str, str],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=option,
                    callback_data=StudyActionCallback(
                        session_type=session_type,
                        session_id=session_id,
                        item_id=item_id,
                        action="answer",
                        value=str(index),
                    ).pack(),
                )
            ]
            for index, option in enumerate(options)
        ]
    )


def rating_keyboard(session_type: str, session_id: int, item_id: int) -> InlineKeyboardMarkup:
    labels = (
        ("know", "Know"),
        ("unsure", "Unsure"),
        ("repeat", "Repeat"),
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=StudyActionCallback(
                        session_type=session_type,
                        session_id=session_id,
                        item_id=item_id,
                        action="rate",
                        value=value,
                    ).pack(),
                )
                for value, label in labels
            ]
        ]
    )


def extra_practice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Extra practice",
                    callback_data=PracticeMenuCallback(action="extra").pack(),
                )
            ]
        ]
    )
