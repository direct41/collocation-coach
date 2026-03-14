import pytest

from collocation_coach.application.onboarding import decode_delivery_time, encode_delivery_time


def test_encode_and_decode_delivery_time() -> None:
    assert encode_delivery_time("09:00") == "0900"
    assert decode_delivery_time("0900") == "09:00"


def test_decode_delivery_time_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Invalid delivery time value"):
        decode_delivery_time("09:00")
