from pydantic import BaseModel, Field, field_validator, model_validator


class PracticeQuestion(BaseModel):
    prompt_ru: str
    options: list[str]
    correct_option_index: int

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        if len(value) != 3:
            raise ValueError("Practice question must contain exactly 3 options")
        return value

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


class LessonUnitMeta(BaseModel):
    key: str
    level_band: str
    day_number: int
    topic: str
    locale: str
    tags: list[str] = Field(default_factory=list)


class LessonUnitFile(BaseModel):
    version: int
    lesson_unit: LessonUnitMeta
    items: list[LessonItem]

    @field_validator("items")
    @classmethod
    def validate_item_count(cls, value: list[LessonItem]) -> list[LessonItem]:
        if len(value) != 3:
            raise ValueError("Lesson unit must contain exactly 3 items")
        return value
