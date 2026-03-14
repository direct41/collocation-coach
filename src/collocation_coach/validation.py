from collections import Counter

from collocation_coach.content.models import LessonUnitFile


def validate_startup_content(lessons: list[tuple[object, LessonUnitFile]]) -> None:
    if not lessons:
        raise ValueError("No lesson files were found")

    by_level = Counter(lesson.lesson_unit.level_band for _, lesson in lessons)
    required_levels = {"a2_b1", "b1_b2"}
    missing = sorted(level for level in required_levels if by_level[level] == 0)
    if missing:
        raise ValueError(f"Missing lesson content for levels: {', '.join(missing)}")
