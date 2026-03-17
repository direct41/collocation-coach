from pathlib import Path

import yaml

from collocation_coach.content.models import LessonUnitFile


def discover_lesson_files(content_dir: Path) -> list[Path]:
    return sorted(path for path in content_dir.rglob("*.yaml") if path.is_file())


def load_lesson_file(path: Path) -> LessonUnitFile:
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw_data is None:
        raise ValueError(f"Lesson file is empty: {path}")
    return LessonUnitFile.model_validate(raw_data)


def load_all_lessons(content_dir: Path) -> list[tuple[Path, LessonUnitFile]]:
    lesson_files = discover_lesson_files(content_dir)
    lessons: list[tuple[Path, LessonUnitFile]] = []
    errors: list[str] = []
    for path in lesson_files:
        try:
            lessons.append((path, load_lesson_file(path)))
        except (yaml.YAMLError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        raise ValueError("Invalid lesson files:\n- " + "\n- ".join(errors))
    return lessons
