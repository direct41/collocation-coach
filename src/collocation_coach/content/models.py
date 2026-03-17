from pydantic import BaseModel, Field, field_validator, model_validator


def _normalize_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Field cannot be blank")
    return normalized


def _normalize_unique_text(value: str) -> str:
    return " ".join(value.casefold().split())


class PracticeQuestion(BaseModel):
    prompt_ru: str
    options: list[str]
    correct_option_index: int

    @field_validator("prompt_ru")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        if len(value) != 3:
            raise ValueError("Practice question must contain exactly 3 options")
        normalized_options = [_normalize_required_text(option) for option in value]
        if len({_normalize_unique_text(option) for option in normalized_options}) != len(
            normalized_options
        ):
            raise ValueError("Practice question options must be unique")
        return normalized_options

    @model_validator(mode="after")
    def validate_correct_option_index(self) -> "PracticeQuestion":
        if not 0 <= self.correct_option_index < len(self.options):
            raise ValueError("correct_option_index must point to an existing option")
        return self


class LessonItem(BaseModel):
    key: str
    phrase: str
    translation_ru: str
    explanation_ru: str
    correct_example: str
    common_mistake: str
    mistake_explanation_ru: str
    practice: PracticeQuestion
    tags: list[str] = Field(default_factory=list)

    @field_validator(
        "key",
        "phrase",
        "translation_ru",
        "explanation_ru",
        "correct_example",
        "common_mistake",
        "mistake_explanation_ru",
    )
    @classmethod
    def validate_required_text_fields(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized_tags = [_normalize_required_text(tag) for tag in value]
        if len({_normalize_unique_text(tag) for tag in normalized_tags}) != len(normalized_tags):
            raise ValueError("Lesson item tags must be unique")
        return normalized_tags

    @model_validator(mode="after")
    def validate_practice_alignment(self) -> "LessonItem":
        correct_option = self.practice.options[self.practice.correct_option_index]
        if correct_option != self.correct_example:
            raise ValueError("correct_example must match the correct practice option")
        if _normalize_unique_text(self.common_mistake) == _normalize_unique_text(self.correct_example):
            raise ValueError("common_mistake must differ from correct_example")
        return self


class LessonUnitMeta(BaseModel):
    key: str
    level_band: str
    day_number: int
    topic: str
    locale: str
    tags: list[str] = Field(default_factory=list)

    @field_validator("key", "level_band", "topic", "locale")
    @classmethod
    def validate_required_text_fields(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        normalized_tags = [_normalize_required_text(tag) for tag in value]
        if len({_normalize_unique_text(tag) for tag in normalized_tags}) != len(normalized_tags):
            raise ValueError("Lesson unit tags must be unique")
        return normalized_tags

    @field_validator("day_number")
    @classmethod
    def validate_day_number(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("day_number must be positive")
        return value


class LessonUnitFile(BaseModel):
    version: int = Field(ge=1)
    lesson_unit: LessonUnitMeta
    items: list[LessonItem]

    @field_validator("items")
    @classmethod
    def validate_item_count(cls, value: list[LessonItem]) -> list[LessonItem]:
        if len(value) != 3:
            raise ValueError("Lesson unit must contain exactly 3 items")
        return value

    @model_validator(mode="after")
    def validate_item_keys(self) -> "LessonUnitFile":
        item_keys = [item.key for item in self.items]
        if len({_normalize_unique_text(item_key) for item_key in item_keys}) != len(item_keys):
            raise ValueError("Lesson unit item keys must be unique")

        expected_prefix = f"{self.lesson_unit.key}-item-"
        for item in self.items:
            if not item.key.startswith(expected_prefix):
                raise ValueError("Lesson item key must start with the lesson unit key")
        return self
