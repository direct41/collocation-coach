from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from collocation_coach.content.models import LessonUnitFile
from collocation_coach.storage.models import CollocationItem, LessonUnit


async def seed_lessons(
    session_factory: async_sessionmaker,
    lessons: list[tuple[Path, LessonUnitFile]],
) -> None:
    async with session_factory() as session:
        for source_path, lesson in lessons:
            lesson_unit = await session.scalar(
                select(LessonUnit).where(
                    LessonUnit.external_key == lesson.lesson_unit.key
                )
            )
            if lesson_unit is None:
                lesson_unit = LessonUnit(
                    external_key=lesson.lesson_unit.key,
                    level_band=lesson.lesson_unit.level_band,
                    day_number=lesson.lesson_unit.day_number,
                    topic=lesson.lesson_unit.topic,
                    source_path=str(source_path),
                )
                session.add(lesson_unit)
                await session.flush()
            else:
                lesson_unit.level_band = lesson.lesson_unit.level_band
                lesson_unit.day_number = lesson.lesson_unit.day_number
                lesson_unit.topic = lesson.lesson_unit.topic
                lesson_unit.source_path = str(source_path)

            for item in lesson.items:
                collocation_item = await session.scalar(
                    select(CollocationItem).where(CollocationItem.external_key == item.key)
                )
                if collocation_item is None:
                    collocation_item = CollocationItem(
                        lesson_unit_id=lesson_unit.id,
                        external_key=item.key,
                        phrase=item.phrase,
                        translation_ru=item.translation_ru,
                        explanation_ru=item.explanation_ru,
                        correct_example=item.correct_example,
                        common_mistake=item.common_mistake,
                        mistake_explanation_ru=item.mistake_explanation_ru,
                        practice_prompt=item.practice.prompt_ru,
                        option_a=item.practice.options[0],
                        option_b=item.practice.options[1],
                        option_c=item.practice.options[2],
                        correct_option_index=item.practice.correct_option_index,
                        tags=item.tags,
                    )
                    session.add(collocation_item)
                    continue

                collocation_item.lesson_unit_id = lesson_unit.id
                collocation_item.phrase = item.phrase
                collocation_item.translation_ru = item.translation_ru
                collocation_item.explanation_ru = item.explanation_ru
                collocation_item.correct_example = item.correct_example
                collocation_item.common_mistake = item.common_mistake
                collocation_item.mistake_explanation_ru = item.mistake_explanation_ru
                collocation_item.practice_prompt = item.practice.prompt_ru
                collocation_item.option_a = item.practice.options[0]
                collocation_item.option_b = item.practice.options[1]
                collocation_item.option_c = item.practice.options[2]
                collocation_item.correct_option_index = item.practice.correct_option_index
                collocation_item.tags = item.tags

        await session.commit()
