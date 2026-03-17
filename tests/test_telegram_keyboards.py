from collocation_coach.application.onboarding import DELIVERY_TIME_OPTIONS, TIMEZONE_OPTIONS
from collocation_coach.transport.telegram.keyboards import (
    delivery_time_keyboard,
    practice_start_keyboard,
    timezone_keyboard,
)


def test_timezone_keyboard_contains_all_supported_timezones() -> None:
    keyboard = timezone_keyboard()
    rows = keyboard.inline_keyboard
    labels = [button.text for row in rows for button in row]

    assert len(rows) == len(TIMEZONE_OPTIONS)
    assert labels == [label for _, label in TIMEZONE_OPTIONS]


def test_delivery_time_keyboard_contains_all_supported_times_in_compact_grid() -> None:
    keyboard = delivery_time_keyboard()
    rows = keyboard.inline_keyboard
    labels = [button.text for row in rows for button in row]

    assert labels == list(DELIVERY_TIME_OPTIONS)
    assert all(1 <= len(row) <= 4 for row in rows)


def test_practice_keyboard_includes_one_tap_feedback_actions() -> None:
    keyboard = practice_start_keyboard("daily", 1, 2)
    rows = keyboard.inline_keyboard

    assert rows[0][0].text == "Practice"
    assert [button.text for button in rows[1]] == ["Broken", "Too hard", "Unnatural"]
