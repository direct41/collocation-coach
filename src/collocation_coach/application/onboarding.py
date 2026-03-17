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
    ("Europe/London", "London"),
    ("Europe/Berlin", "Berlin"),
    ("Europe/Madrid", "Madrid"),
    ("Europe/Moscow", "Moscow"),
    ("Europe/Istanbul", "Istanbul"),
    ("Africa/Cairo", "Cairo"),
    ("Africa/Johannesburg", "Johannesburg"),
    ("America/New_York", "New York"),
    ("America/Chicago", "Chicago"),
    ("America/Denver", "Denver"),
    ("America/Los_Angeles", "Los Angeles"),
    ("America/Mexico_City", "Mexico City"),
    ("America/Bogota", "Bogota"),
    ("America/Sao_Paulo", "Sao Paulo"),
    ("Asia/Dubai", "Dubai"),
    ("Asia/Kolkata", "Kolkata"),
    ("Asia/Bangkok", "Bangkok"),
    ("Asia/Ho_Chi_Minh", "Ho Chi Minh"),
    ("Asia/Singapore", "Singapore"),
    ("Asia/Shanghai", "Shanghai"),
    ("Asia/Seoul", "Seoul"),
    ("Asia/Tokyo", "Tokyo"),
    ("Australia/Sydney", "Sydney"),
    ("Pacific/Auckland", "Auckland"),
)

DELIVERY_TIME_OPTIONS: Sequence[str] = tuple(f"{hour:02d}:00" for hour in range(24))

_KNOWN_TIMEZONES = {item[0] for item in TIMEZONE_OPTIONS}
_KNOWN_DELIVERY_TIMES = set(DELIVERY_TIME_OPTIONS)


def encode_delivery_time(value: str) -> str:
    return value.replace(":", "")


def decode_delivery_time(value: str) -> str:
    if len(value) != 4 or not value.isdigit():
        raise ValueError("Invalid delivery time value")
    decoded = f"{value[:2]}:{value[2:]}"
    return validate_delivery_time_option(decoded)


def validate_timezone_option(value: str) -> str:
    if value not in _KNOWN_TIMEZONES:
        raise ValueError("Unsupported timezone option")
    return value


def validate_delivery_time_option(value: str) -> str:
    if value not in _KNOWN_DELIVERY_TIMES:
        raise ValueError("Unsupported delivery time option")
    return value


def onboarding_complete(user_level_band: str | None, user_timezone: str | None, delivery_time: str | None) -> bool:
    return bool(user_level_band and user_timezone and delivery_time)


def normalize_pace_mode(value: str | None) -> str:
    known_values = {item[0] for item in PACE_MODES}
    if value in known_values:
        return value
    return DEFAULT_PACE_MODE
