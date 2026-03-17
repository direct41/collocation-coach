from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from collocation_coach.content.loader import load_all_lessons
from collocation_coach.validation import (
    collect_content_lint_warnings,
    main as validation_main,
    validate_startup_content,
)


def _sample_lesson() -> dict:
    return yaml.safe_load(Path("content/lessons/a2_b1/day-001.yaml").read_text(encoding="utf-8"))


def _build_lesson(level_band: str, day_number: int) -> dict:
    lesson = deepcopy(_sample_lesson())
    lesson_key = f"{level_band.replace('_', '-')}-day-{day_number:03d}"
    lesson["lesson_unit"]["key"] = lesson_key
    lesson["lesson_unit"]["level_band"] = level_band
    lesson["lesson_unit"]["day_number"] = day_number
    lesson["lesson_unit"]["topic"] = f"{level_band} topic {day_number}"
    lesson["lesson_unit"]["tags"] = [level_band, f"day-{day_number:03d}"]
    for index, item in enumerate(lesson["items"], start=1):
        item["key"] = f"{lesson_key}-item-{index:02d}"
        item["phrase"] = f"{item['phrase']} {level_band} {day_number} {index}"
        item["translation_ru"] = f"{item['translation_ru']} {level_band} {day_number} {index}"
    return lesson


def _write_lesson(path: Path, lesson: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(lesson, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _write_minimal_valid_catalog(base_dir: Path) -> Path:
    lessons_dir = base_dir / "lessons"
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", _build_lesson("a2_b1", 1))
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))
    return lessons_dir


def test_existing_content_passes_startup_validation() -> None:
    lessons = load_all_lessons(Path("content/lessons"))

    validate_startup_content(lessons)


def test_validate_startup_content_accepts_minimal_valid_catalog(tmp_path: Path) -> None:
    lessons = load_all_lessons(_write_minimal_valid_catalog(tmp_path))

    validate_startup_content(lessons)


def test_validate_startup_content_rejects_duplicate_lesson_keys(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    second = _build_lesson("b1_b2", 1)
    second["lesson_unit"]["key"] = first["lesson_unit"]["key"]
    for index, item in enumerate(second["items"], start=1):
        item["key"] = f"{first['lesson_unit']['key']}-item-{index:02d}"
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", second)

    lessons = load_all_lessons(lessons_dir)

    with pytest.raises(ValueError, match="Duplicate lesson key"):
        validate_startup_content(lessons)


def test_load_all_lessons_rejects_duplicate_item_keys_inside_one_lesson(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    first["items"][1]["key"] = first["items"][0]["key"]
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    with pytest.raises(ValueError, match="Lesson unit item keys must be unique"):
        load_all_lessons(lessons_dir)


def test_validate_startup_content_rejects_duplicate_day_numbers_within_level(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    second = _build_lesson("a2_b1", 1)
    second["lesson_unit"]["key"] = "a2-b1-day-002"
    for index, item in enumerate(second["items"], start=1):
        item["key"] = f"a2-b1-day-002-item-{index:02d}"
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "a2_b1" / "day-002.yaml", second)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    lessons = load_all_lessons(lessons_dir)

    with pytest.raises(ValueError, match="Duplicate day_number"):
        validate_startup_content(lessons)


def test_load_all_lessons_reports_blank_required_field(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    broken = _build_lesson("a2_b1", 1)
    broken["items"][0]["phrase"] = "   "
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", broken)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    with pytest.raises(ValueError, match="Field cannot be blank"):
        load_all_lessons(lessons_dir)


def test_load_all_lessons_reports_invalid_practice_options(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    broken = _build_lesson("a2_b1", 1)
    broken["items"][0]["practice"]["options"] = ["Same option", "Same option", "Other option"]
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", broken)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    with pytest.raises(ValueError, match="Practice question options must be unique"):
        load_all_lessons(lessons_dir)


def test_validate_startup_content_rejects_path_consistency_mismatch(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    _write_lesson(lessons_dir / "b1_b2" / "day-099.yaml", _build_lesson("a2_b1", 1))
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    lessons = load_all_lessons(lessons_dir)

    with pytest.raises(ValueError, match="does not match lesson directory"):
        validate_startup_content(lessons)


def test_collect_content_lint_warnings_reports_duplicate_phrase_and_translation(
    tmp_path: Path,
) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    second = _build_lesson("a2_b1", 2)
    second["items"][0]["translation_ru"] = first["items"][0]["translation_ru"]
    second["items"][0]["phrase"] = f"{second['items'][0]['phrase']} duplicate"
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "a2_b1" / "day-002.yaml", second)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    lessons = load_all_lessons(lessons_dir)
    validate_startup_content(lessons)

    warnings = collect_content_lint_warnings(lessons)

    second["items"][1]["phrase"] = first["items"][1]["phrase"]
    _write_lesson(lessons_dir / "a2_b1" / "day-002.yaml", second)
    lessons = load_all_lessons(lessons_dir)
    warnings = collect_content_lint_warnings(lessons)

    assert any("Duplicate phrase" in warning for warning in warnings)
    assert any("Duplicate translation" in warning for warning in warnings)


def test_collect_content_lint_warnings_reports_duplicate_topic(tmp_path: Path) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    second = _build_lesson("a2_b1", 2)
    second["lesson_unit"]["topic"] = first["lesson_unit"]["topic"]
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "a2_b1" / "day-002.yaml", second)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    lessons = load_all_lessons(lessons_dir)
    validate_startup_content(lessons)

    warnings = collect_content_lint_warnings(lessons)

    assert any("Duplicate topic" in warning for warning in warnings)


def test_validation_main_returns_non_zero_for_strict_duplicate_warnings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lessons_dir = tmp_path / "lessons"
    first = _build_lesson("a2_b1", 1)
    second = _build_lesson("a2_b1", 2)
    second["items"][0]["phrase"] = first["items"][0]["phrase"]
    _write_lesson(lessons_dir / "a2_b1" / "day-001.yaml", first)
    _write_lesson(lessons_dir / "a2_b1" / "day-002.yaml", second)
    _write_lesson(lessons_dir / "b1_b2" / "day-001.yaml", _build_lesson("b1_b2", 1))

    exit_code = validation_main(["--strict-duplicates", str(lessons_dir)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Content lint failed due to duplicate warnings" in captured.err
