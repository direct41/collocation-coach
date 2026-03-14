from pathlib import Path

from collocation_coach.content.loader import load_all_lessons, load_lesson_file


def test_load_lesson_file_parses_sample_content() -> None:
    lesson = load_lesson_file(
        Path("content/lessons/a2_b1/day-001.yaml")
    )

    assert lesson.lesson_unit.key == "a2-b1-day-001"
    assert len(lesson.items) == 3
    assert lesson.items[0].phrase == "make a decision"


def test_load_all_lessons_discovers_sample_content(tmp_path: Path) -> None:
    lesson_dir = tmp_path / "lessons" / "a2_b1"
    lesson_dir.mkdir(parents=True)
    sample = Path("content/lessons/a2_b1/day-001.yaml").read_text(encoding="utf-8")
    (lesson_dir / "day-001.yaml").write_text(sample, encoding="utf-8")

    lessons = load_all_lessons(tmp_path / "lessons")

    assert len(lessons) == 1
    assert lessons[0][1].lesson_unit.day_number == 1
