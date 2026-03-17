# Content Guide

This guide defines the Phase 6 authoring contract for YAML lesson content.

## Before You Add Or Edit Content

1. Read one existing file from the target level band in `content/lessons/`.
2. Keep the current YAML shape unchanged.
3. Run:

```bash
uv run python -m collocation_coach.validation
```

Use `--strict-duplicates` when you want duplicate phrase and translation findings to fail the run.

## Required Structure

Each lesson file must:

- live under `content/lessons/<level_band>/`
- use the filename pattern `day-XXX.yaml`
- contain exactly one `lesson_unit`
- use `lesson_unit.key` in the pattern `{level-band}-day-{XXX}`
- contain exactly `3` items
- use unique `lesson_unit.key`
- use unique item `key` values
- use a `day_number` that is unique inside the same level band

Each item must include:

- `phrase`
- `translation_ru`
- `explanation_ru`
- `correct_example`
- `common_mistake`
- `mistake_explanation_ru`
- `practice.prompt_ru`
- exactly `3` practice options
- a valid `correct_option_index`
- an item key that starts with `{lesson_unit.key}-item-`

Blank strings are not allowed.

## Russian Explanation Style

Write `explanation_ru` and `mistake_explanation_ru` in simple, direct Russian.

Prefer:

- one concrete meaning per item
- short sentences over abstract definitions
- wording that helps the learner distinguish the correct collocation from the mistake

Avoid:

- dictionary-style overload
- grammar lectures
- vague wording such as "used in many situations"

## Correct Example Rules

A good `correct_example`:

- sounds natural in everyday or professional English
- uses the target collocation in a complete sentence
- is specific enough to feel real
- matches the correct option in `practice`

Avoid:

- fragments without context
- overly formal or literary sentences
- examples that are correct but too rare for the target level

## Common Mistake Rules

A good `common_mistake`:

- reflects a mistake a Russian-speaking learner could plausibly make
- stays close enough to the correct phrase to be instructional
- is clearly different from the correct example

Avoid:

- random wrong English with no teaching value
- mistakes that introduce several unrelated problems at once

## Level Consistency

Use the current launch bands only:

- `a2_b1`: high-frequency, concrete, daily-use collocations
- `b1_b2`: broader work, study, planning, communication, and abstract-reasoning collocations

For `a2_b1`, prefer:

- short familiar vocabulary
- concrete situations
- low ambiguity

For `b1_b2`, allow:

- more abstract contexts
- workplace or process vocabulary
- broader sentence structures

Do not move difficult `b1_b2` wording into `a2_b1` just to add volume.

## Duplicate And Overlap Rules

When adding new lessons:

- do not reuse an existing phrase unless you are intentionally replacing the old lesson
- avoid repeating the same Russian translation in the same level band unless the overlap is clearly justified
- avoid lessons whose three items repeat the same phrase family from a nearby lesson
- avoid topic clusters that feel like renamed copies of an earlier unit

Run the validator before merge and inspect duplicate warnings instead of ignoring them.

## Metadata And Tags

Use `lesson_unit.topic` as the shortest useful summary of the unit.

Use `tags` to describe:

- the core verb or phrase family
- the topic area
- a reusable grouping that helps future review

Keep tags short, explicit, and non-empty.

## Review Checklist

Before merge, confirm:

- structure still validates
- the correct option matches `correct_example`
- Russian explanations are concise and specific
- the lesson does not duplicate an earlier unit without intent
- the target level band still feels consistent
