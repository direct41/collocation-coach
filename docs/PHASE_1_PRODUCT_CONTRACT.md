# Collocation Coach Phase 1 Product Contract

## Status

Frozen for MVP implementation.

This document defines the behavior that Phase 2 code generation must follow.

## Product One-Liner

`Collocation Coach` is a Telegram bot that helps Russian-speaking English learners sound more natural by sending a short daily collocation lesson with review.

## Primary User

- Russian-speaking learner
- English level A2-B2
- studies regularly but struggles with natural word combinations
- wants a 2-3 minute daily habit, not a long study session

## MVP Promise

Each day the bot sends:
- 3 new collocations from the next lesson unit
- up to 2 review collocations from prior weak items
- short explanation in Russian
- one correct example
- one common mistake
- one quick multiple-choice practice step

## Product Scope

### In MVP

- Telegram bot
- onboarding
- daily lesson scheduling
- one active lesson per day
- self-rating after each item
- simple spaced repetition
- `/today`, `/review`, `/settings`
- file-based lesson content in YAML
- self-hostable open-source setup

### Out of MVP

- AI chat
- audio or voice
- free-text answer checking
- admin web panel
- gamification system
- streak economy
- mobile app
- collaborative or social features

## Lesson Structure

### Daily Lesson Composition

1. Intro message
2. Review block with up to 2 items
3. New block with exactly 3 items
4. Completion message with short summary

If the review queue is empty, the lesson still runs with only 3 new items.

### Single Item Flow

Each item is shown in this order:

1. Collocation card
   - target phrase
   - Russian translation
   - short explanation
   - correct example
   - common mistake or contrast
2. Practice prompt
   - one multiple-choice question
   - 3 answer options
   - exactly 1 correct option
3. Feedback
   - correct answer
   - short reason
4. Self-rating
   - `Know`
   - `Unsure`
   - `Repeat`

## Required Commands

- `/start`
- `/today`
- `/review`
- `/settings`
- `/help`

## Interaction Contracts

### `/start`

For a new user:
1. Welcome message
2. Level choice:
   - `A2-B1`
   - `B1-B2`
3. Timezone choice
   - default from Telegram locale when available
   - fallback to `DEFAULT_TIMEZONE`
4. Daily delivery time choice
   - fixed buttons: `09:00`, `13:00`, `19:00`, `21:00`
5. Confirmation message

For an existing user:
- shows current settings and suggests `/today` or `/settings`

### `/today`

- returns the current day's lesson if it exists
- if already completed, returns the lesson summary
- if today's lesson has not yet been generated, generates it

### `/review`

- starts a short review-only session
- pulls up to 5 due review items
- if no items are due, explains that review queue is empty

### `/settings`

Allows updating:
- level band
- timezone
- delivery time

### `/help`

Explains:
- what the bot does
- what `Know`, `Unsure`, and `Repeat` mean
- available commands

## Review Logic Contract

MVP review scheduling is intentionally simple.

### Self-Rating Effects

- `Know`
  - mark item successful
  - next due interval grows
- `Unsure`
  - mark item weak
  - next due tomorrow
- `Repeat`
  - mark item difficult
  - next due in the next review session

### Default Intervals

- first successful review: `+3 days`
- second successful review: `+7 days`
- third and later successful review: `+14 days`
- `Unsure`: `+1 day`
- `Repeat`: same day if there is remaining review capacity, otherwise `+1 day`

The bot must keep the algorithm configurable in code, but Phase 3 should start with these exact defaults.

## Content Contract

Lesson content is stored as YAML lesson units.

Each lesson unit contains:
- metadata
- exactly 3 new collocation items

Review items are not authored inside the lesson unit. They are selected dynamically from user progress.

The canonical content example for Phase 2 is:
- [day-001.yaml](../content/lessons/a2_b1/day-001.yaml)

## Data Model Contract

Phase 2 storage must support these entities.

### `users`

- `id`
- `telegram_user_id`
- `username`
- `first_name`
- `language_code`
- `level_band`
- `timezone`
- `daily_delivery_time`
- `is_active`
- `created_at`
- `updated_at`

### `lesson_units`

- `id`
- `external_key`
- `level_band`
- `day_number`
- `topic`
- `source_path`
- `created_at`

### `collocation_items`

- `id`
- `lesson_unit_id`
- `external_key`
- `phrase`
- `translation_ru`
- `explanation_ru`
- `correct_example`
- `common_mistake`
- `practice_prompt`
- `correct_option`
- `wrong_option_1`
- `wrong_option_2`
- `tags`

### `daily_lessons`

- `id`
- `user_id`
- `lesson_date`
- `lesson_unit_id`
- `status`
- `created_at`
- `completed_at`

### `daily_lesson_items`

- `id`
- `daily_lesson_id`
- `collocation_item_id`
- `item_type` (`new` or `review`)
- `position`
- `answer_selected`
- `answered_correctly`
- `self_rating`
- `answered_at`

### `user_collocation_progress`

- `id`
- `user_id`
- `collocation_item_id`
- `times_seen`
- `times_correct`
- `last_seen_at`
- `last_rating`
- `stability_stage`
- `due_at`
- `created_at`
- `updated_at`

### `delivery_jobs`

- `id`
- `user_id`
- `scheduled_for`
- `status`
- `attempt_count`
- `last_error`
- `created_at`
- `updated_at`

## Event Contract

The bot must emit or log these events:
- `user_started`
- `onboarding_completed`
- `daily_lesson_generated`
- `daily_lesson_started`
- `item_answered`
- `item_rated`
- `daily_lesson_completed`
- `review_session_started`
- `review_session_completed`
- `settings_updated`
- `delivery_attempted`
- `delivery_succeeded`
- `delivery_failed`

## Environment Contract

Required:
- `APP_ENV`
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`
- `DEFAULT_LOCALE`
- `DEFAULT_TIMEZONE`

Optional for MVP:
- `LOG_LEVEL`
- `CONTENT_DIR`
- `DELIVERY_BATCH_SIZE`

## Open-Source Contract

The public repository must include:
- sample lesson files
- `.env.example`
- Docker-based local run path
- no committed secrets
- clear setup docs

## Acceptance Criteria For Phase 1 Completion

Phase 1 is complete when:
- lesson flow is explicit
- commands are fixed
- review algorithm defaults are fixed
- storage entities are defined
- content file structure is defined
- required environment variables are defined
- there are no blocking product ambiguities for Phase 2

## Decisions Made By Default

- stack: Python + aiogram + PostgreSQL
- runtime mode: polling first
- launch locale: Russian explanations for all lesson content
- level bands at launch: `A2-B1` and `B1-B2`
- daily delivery options at launch: fixed times, not free-form input
