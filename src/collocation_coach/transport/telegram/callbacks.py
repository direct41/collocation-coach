from aiogram.filters.callback_data import CallbackData


class LevelSelectionCallback(CallbackData, prefix="level"):
    level_band: str


class TimezoneSelectionCallback(CallbackData, prefix="tz"):
    timezone: str


class PaceSelectionCallback(CallbackData, prefix="pace"):
    pace_mode: str


class DeliveryTimeSelectionCallback(CallbackData, prefix="time"):
    delivery_time: str


class SettingsActionCallback(CallbackData, prefix="settings"):
    action: str


class StudyActionCallback(CallbackData, prefix="study"):
    session_type: str
    session_id: int
    item_id: int
    action: str
    value: str = ""


class PracticeMenuCallback(CallbackData, prefix="practice_menu"):
    action: str
