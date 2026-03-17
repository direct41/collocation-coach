from datetime import date, datetime
from zoneinfo import ZoneInfo


def local_now(now_utc: datetime, timezone_name: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(timezone_name))


def local_today(now_utc: datetime, timezone_name: str) -> date:
    return local_now(now_utc, timezone_name).date()
