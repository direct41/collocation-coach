from collections.abc import Sequence


LEVEL_BANDS: Sequence[tuple[str, str]] = (
    ("a2_b1", "A2-B1"),
    ("b1_b2", "B1-B2"),
)

PACE_MODES: Sequence[tuple[str, str]] = (
    ("light", "Light"),
    ("standard", "Standard"),
    ("intensive", "Intensive"),
)

DEFAULT_PACE_MODE = "standard"

TIMEZONE_OPTIONS: Sequence[tuple[str, str]] = (
    ("UTC", "UTC"),
    ("Europe/Berlin", "Berlin"),
    ("Europe/Moscow", "Moscow"),
    ("America/New_York", "New York"),
    ("Asia/Ho_Chi_Minh", "Ho Chi Minh"),
)

DELIVERY_TIME_OPTIONS: Sequence[str] = ("09:00", "13:00", "19:00", "21:00")


def encode_delivery_time(value: str) -> str:
    return value.replace(":", "")


def decode_delivery_time(value: str) -> str:
    if len(value) != 4 or not value.isdigit():
        raise ValueError("Invalid delivery time value")
    return f"{value[:2]}:{value[2:]}"


def onboarding_complete(user_level_band: str | None, user_timezone: str | None, delivery_time: str | None) -> bool:
    return bool(user_level_band and user_timezone and delivery_time)


def normalize_pace_mode(value: str | None) -> str:
    known_values = {item[0] for item in PACE_MODES}
    if value in known_values:
        return value
    return DEFAULT_PACE_MODE
