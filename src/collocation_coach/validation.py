import argparse
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

from collocation_coach.content.loader import load_all_lessons
from collocation_coach.content.models import LessonItem, LessonUnitFile


type LessonFile = tuple[Path, LessonUnitFile]

REQUIRED_LEVELS = ("a2_b1", "b1_b2")


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _format_issue_list(issues: Sequence[str], header: str) -> str:
    return f"{header}\n- " + "\n- ".join(issues)


def _format_item_occurrence(path: Path, item: LessonItem) -> str:
    return f"{path}#{item.key}"


def _expected_lesson_key(level_band: str, day_number: int) -> str:
    return f"{level_band.replace('_', '-')}-day-{day_number:03d}"


def _collect_duplicate_key_issues(lessons: Sequence[LessonFile]) -> list[str]:
    lesson_keys: defaultdict[str, list[str]] = defaultdict(list)
    item_keys: defaultdict[str, list[str]] = defaultdict(list)
    issues: list[str] = []

    for path, lesson in lessons:
        lesson_keys[_normalize_text(lesson.lesson_unit.key)].append(str(path))
        for item in lesson.items:
            item_keys[_normalize_text(item.key)].append(_format_item_occurrence(path, item))

    for normalized_key, paths in sorted(lesson_keys.items()):
        if len(paths) > 1:
            issues.append(
                f"Duplicate lesson key '{normalized_key}' found in: {', '.join(sorted(paths))}"
            )
    for normalized_key, occurrences in sorted(item_keys.items()):
        if len(occurrences) > 1:
            issues.append(
                f"Duplicate item key '{normalized_key}' found in: {', '.join(sorted(occurrences))}"
            )

    return issues


def _collect_duplicate_day_number_issues(lessons: Sequence[LessonFile]) -> list[str]:
    by_level_and_day: defaultdict[tuple[str, int], list[str]] = defaultdict(list)
    for path, lesson in lessons:
        key = (lesson.lesson_unit.level_band, lesson.lesson_unit.day_number)
        by_level_and_day[key].append(str(path))

    issues: list[str] = []
    for (level_band, day_number), paths in sorted(by_level_and_day.items()):
        if len(paths) > 1:
            issues.append(
                f"Duplicate day_number '{day_number}' for level '{level_band}' found in: "
                + ", ".join(sorted(paths))
            )
    return issues


def _collect_path_consistency_issues(lessons: Sequence[LessonFile]) -> list[str]:
    issues: list[str] = []

    for path, lesson in lessons:
        lesson_meta = lesson.lesson_unit
        expected_filename = f"day-{lesson_meta.day_number:03d}.yaml"
        expected_key = _expected_lesson_key(lesson_meta.level_band, lesson_meta.day_number)

        if path.parent.name != lesson_meta.level_band:
            issues.append(
                f"Level '{lesson_meta.level_band}' does not match lesson directory '{path.parent.name}' in {path}"
            )
        if path.name != expected_filename:
            issues.append(
                f"Filename '{path.name}' does not match day_number '{lesson_meta.day_number:03d}' in {path}"
            )
        if lesson_meta.key != expected_key:
            issues.append(
                f"Lesson key '{lesson_meta.key}' does not match expected key '{expected_key}' in {path}"
            )

    return issues


def _collect_duplicate_phrase_warnings(lessons: Sequence[LessonFile]) -> list[str]:
    by_phrase: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for path, lesson in lessons:
        level_band = lesson.lesson_unit.level_band
        for item in lesson.items:
            key = (level_band, _normalize_text(item.phrase))
            by_phrase[key].append(_format_item_occurrence(path, item))

    warnings: list[str] = []
    for (level_band, normalized_phrase), occurrences in sorted(by_phrase.items()):
        if len(occurrences) > 1:
            warnings.append(
                f"Duplicate phrase '{normalized_phrase}' for level '{level_band}' found in: "
                + ", ".join(sorted(occurrences))
            )
    return warnings


def _collect_duplicate_translation_warnings(lessons: Sequence[LessonFile]) -> list[str]:
    by_translation: defaultdict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for path, lesson in lessons:
        level_band = lesson.lesson_unit.level_band
        for item in lesson.items:
            key = (level_band, _normalize_text(item.translation_ru))
            by_translation[key].append((_format_item_occurrence(path, item), _normalize_text(item.phrase)))

    warnings: list[str] = []
    for (level_band, normalized_translation), occurrences in sorted(by_translation.items()):
        unique_phrases = {phrase for _, phrase in occurrences}
        if len(unique_phrases) > 1:
            warnings.append(
                f"Duplicate translation '{normalized_translation}' for level '{level_band}' found in: "
                + ", ".join(sorted(occurrence for occurrence, _ in occurrences))
            )
    return warnings


def _collect_duplicate_topic_warnings(lessons: Sequence[LessonFile]) -> list[str]:
    by_topic: defaultdict[tuple[str, str], list[str]] = defaultdict(list)
    for path, lesson in lessons:
        key = (lesson.lesson_unit.level_band, _normalize_text(lesson.lesson_unit.topic))
        by_topic[key].append(str(path))

    warnings: list[str] = []
    for (level_band, normalized_topic), paths in sorted(by_topic.items()):
        if len(paths) > 1:
            warnings.append(
                f"Duplicate topic '{normalized_topic}' for level '{level_band}' found in: "
                + ", ".join(sorted(paths))
            )
    return warnings


def collect_content_lint_warnings(lessons: Sequence[LessonFile]) -> tuple[str, ...]:
    warnings = [
        *_collect_duplicate_topic_warnings(lessons),
        *_collect_duplicate_phrase_warnings(lessons),
        *_collect_duplicate_translation_warnings(lessons),
    ]
    return tuple(warnings)


def validate_startup_content(lessons: Sequence[LessonFile]) -> None:
    if not lessons:
        raise ValueError("No lesson files were found")

    issues: list[str] = []
    by_level = Counter(lesson.lesson_unit.level_band for _, lesson in lessons)
    missing = sorted(level for level in REQUIRED_LEVELS if by_level[level] == 0)
    if missing:
        issues.append(f"Missing lesson content for levels: {', '.join(missing)}")

    issues.extend(_collect_path_consistency_issues(lessons))
    issues.extend(_collect_duplicate_key_issues(lessons))
    issues.extend(_collect_duplicate_day_number_issues(lessons))

    if issues:
        raise ValueError(_format_issue_list(issues, "Content validation failed:"))


def run_content_lint(content_dir: Path, *, strict_duplicates: bool = False) -> int:
    try:
        lessons = load_all_lessons(content_dir)
        validate_startup_content(lessons)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    warnings = collect_content_lint_warnings(lessons)
    if warnings:
        print(
            _format_issue_list(
                warnings,
                (
                    "Content lint warnings:"
                    if not strict_duplicates
                    else "Content lint failed due to duplicate warnings:"
                ),
            ),
            file=sys.stderr if strict_duplicates else sys.stdout,
        )
        if strict_duplicates:
            return 1

    print(f"Content validation passed for {len(lessons)} lesson files.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate lesson content and report duplicate phrases/translations."
    )
    parser.add_argument(
        "content_dir",
        nargs="?",
        default="content/lessons",
        help="Path to the lesson content directory.",
    )
    parser.add_argument(
        "--strict-duplicates",
        action="store_true",
        help="Treat duplicate phrase and translation findings as a failing lint result.",
    )
    args = parser.parse_args(argv)
    return run_content_lint(Path(args.content_dir), strict_duplicates=args.strict_duplicates)


if __name__ == "__main__":
    raise SystemExit(main())
