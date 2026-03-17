import pytest

from collocation_coach.application.onboarding import (
    DELIVERY_TIME_OPTIONS,
    TIMEZONE_OPTIONS,
    decode_delivery_time,
    encode_delivery_time,
    validate_delivery_time_option,
    validate_timezone_option,
)


def test_encode_and_decode_delivery_time() -> None:
    assert encode_delivery_time("09:00") == "0900"
    assert decode_delivery_time("0900") == "09:00"


def test_decode_delivery_time_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid delivery time value"):
        decode_delivery_time("09:00")


def test_decode_delivery_time_rejects_unsupported_option() -> None:
    with pytest.raises(ValueError, match="Unsupported delivery time option"):
        decode_delivery_time("0030")


def test_validate_timezone_option_accepts_known_value() -> None:
    assert validate_timezone_option("Asia/Ho_Chi_Minh") == "Asia/Ho_Chi_Minh"


def test_validate_timezone_option_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unsupported timezone option"):
        validate_timezone_option("Mars/Olympus")


def test_timezone_options_are_materially_wider_than_previous_shortlist() -> None:
    assert len(TIMEZONE_OPTIONS) >= 20


def test_delivery_time_options_cover_full_day_hourly() -> None:
    assert len(DELIVERY_TIME_OPTIONS) == 24
    assert DELIVERY_TIME_OPTIONS[0] == "00:00"
    assert DELIVERY_TIME_OPTIONS[-1] == "23:00"
    assert validate_delivery_time_option("13:00") == "13:00"
