from html import escape

from aiogram.types import InlineKeyboardMarkup

from collocation_coach.application.study import SessionSummary, StudyItemCard
from collocation_coach.transport.telegram.keyboards import practice_start_keyboard


def format_settings(level_band: str | None, timezone: str | None, delivery_time: str | None) -> str:
    return (
        "Current settings:\n"
        f"- Level: {level_band or 'not set'}\n"
        f"- Timezone: {timezone or 'not set'}\n"
        f"- Delivery time: {delivery_time or 'not set'}"
    )


def format_item_card(card: StudyItemCard) -> str:
    item_label = "Review" if card.item_type == "review" else "New"
    return (
        f"{item_label} item {card.position}/{card.total_items}\n\n"
        f"<b>{escape(card.phrase)}</b>\n"
        f"{escape(card.translation_ru)}\n\n"
        f"{escape(card.explanation_ru)}\n\n"
        f"Example: <i>{escape(card.correct_example)}</i>\n"
        f"Common mistake: <code>{escape(card.common_mistake)}</code>\n"
        f"{escape(card.mistake_explanation_ru)}"
    )


def format_practice(card: StudyItemCard) -> str:
    return (
        f"Item {card.position}/{card.total_items}\n\n"
        f"<b>{escape(card.phrase)}</b>\n\n"
        f"{escape(card.practice_prompt)}"
    )


def format_feedback(card: StudyItemCard, selected_index: int) -> str:
    is_correct = selected_index == card.correct_option_index
    result = "Correct" if is_correct else "Not quite"
    return (
        f"{result}.\n\n"
        f"Correct answer:\n<i>{escape(card.options[card.correct_option_index])}</i>\n\n"
        f"{escape(card.mistake_explanation_ru)}\n\n"
        "How did this feel?"
    )


def format_summary(summary: SessionSummary) -> str:
    if summary.session_type == "daily":
        return (
            "Daily lesson complete.\n\n"
            f"Correct answers: {summary.correct_answers}/{summary.total_items}\n"
            f"New items: {summary.new_items}\n"
            f"Review items: {summary.review_items}"
        )
    return (
        "Review session complete.\n\n"
        f"Correct answers: {summary.correct_answers}/{summary.total_items}"
    )


def daily_intro_text(summary: SessionSummary) -> str:
    return (
        "Today's lesson is ready.\n\n"
        f"New items: {summary.new_items}\n"
        f"Review items: {summary.review_items}"
    )


def practice_markup(card: StudyItemCard) -> InlineKeyboardMarkup:
    return practice_start_keyboard(card.session_type, card.session_id, card.session_item_id)
