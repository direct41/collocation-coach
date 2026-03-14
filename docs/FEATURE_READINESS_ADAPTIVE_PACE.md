# Feature Readiness Brief: Adaptive Pace And Extra Practice

## Goal

Replace the rigid "same number of collocations for everyone" daily flow with a lightweight adaptive model:
- user-selectable pace
- new-item selection based on unseen collocations, not lesson-day count
- optional extra practice after the main daily session is done

## Non-Goals

- no full content format migration away from YAML lesson files
- no admin panel
- no advanced adaptive algorithm
- no streaks, badges, or gamification
- no migration to Alembic in this change

## Product Rules

- Each level keeps its own independent learning track.
- Main daily session stays finite.
- Pace controls the number of new items in the main daily session.
- Review remains prioritized before new items.
- After the main daily session is complete, the user can optionally continue with extra practice.
- Extra practice must not block the next daily session.

## Pace Modes

- `light`: 2 new items, up to 2 review items
- `standard`: 3 new items, up to 2 review items
- `intensive`: 5 new items, up to 3 review items

## Content Model Decision

Current YAML lesson files remain in place.

Implementation decision:
- treat each existing `LessonUnit` as a content pack
- use `day_number` only as stable ordering inside a level
- select unseen collocation items across packs in order

This avoids a disruptive content migration while removing the "one pack per calendar day" learning constraint.

## Data Model Changes

- add `users.pace_mode`

Default:
- existing users: `standard`
- new users: `standard`

## Runtime And Migration Constraints

- existing databases must continue to work without manual migration steps
- startup must add `pace_mode` if the column is missing
- keep changes compatible with SQLite tests and local Postgres runtime

## Acceptance Criteria

- User can set and change pace in Telegram.
- `/today` builds a main session using pace-based new/review counts.
- New-item selection is based on unseen collocation items in the current level.
- `/review` still returns due items for the current level only.
- Completed daily sessions expose optional extra practice.
- Extra practice can start even when the due review queue is empty.
- Existing tests still pass and new tests cover the new behavior.

## Integration Points

- storage: `src/collocation_coach/storage/models.py`, `src/collocation_coach/storage/database.py`
- study logic: `src/collocation_coach/application/study.py`
- onboarding/settings: `src/collocation_coach/application/onboarding.py`
- Telegram sink: `src/collocation_coach/transport/telegram/*`
- docs: `README.md`, `RUN.md`

## Assumptions

- A simple pace selector is enough for this phase; no auto-adaptation yet.
- Extra practice can reuse the review session model.
- Existing lesson files already provide enough ordered content to support item-based progression.
