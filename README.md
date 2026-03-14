# Collocation Coach

Open-source Telegram bot for learning English collocations through short daily lessons.

## What It Does

`Collocation Coach` helps learners build more natural English with a small daily loop:
- pace-based new collocations
- due review items first
- short explanations in Russian
- common mistake contrast
- simple spaced repetition
- optional extra practice after the main session

## Current MVP

Implemented now:
- Telegram bot with polling runtime
- onboarding flow
- `/today`, `/review`, `/settings`
- per-level learning tracks for `a2_b1` and `b1_b2`
- pace modes: `light`, `standard`, `intensive`
- YAML lesson content
- built-in daily delivery loop
- PostgreSQL persistence
- Docker and local `uv` run paths

## Quick Start

The shortest setup path is in [RUN.md](./RUN.md).

Fast local run:

```bash
cp .env.example .env
uv sync
uv run python -m collocation_coach.main
```

Then open your bot in Telegram and send `/start`.

## Environment

Required:
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`

Defaults live in [.env.example](./.env.example).

## Content

Lessons are plain YAML files in [content/lessons](./content/lessons).

Each level has its own track:
- [content/lessons/a2_b1](./content/lessons/a2_b1)
- [content/lessons/b1_b2](./content/lessons/b1_b2)

## Commands

- `/start`
- `/help`
- `/today`
- `/review`
- `/settings`

## Current Learning Model

- the main daily session is generated from the current level track
- review items come first
- new items are selected from unseen collocations in pack order
- pace controls how many new items appear in the main session
- after the main session, the user can continue with extra practice

## Self-Hosting Goal

The repository is intentionally simple:
- one bot process
- one Postgres database
- editable YAML content
- no external admin panel required

## Documents

- [RUN.md](./RUN.md)
- [AI MVP plan](./docs/AI_MVP_PLAN.md)
- [Product plan](./docs/PRODUCT_PLAN.md)
- [Technical decisions](./docs/TECHNICAL_DECISIONS.md)
- [Phase 1 product contract](./docs/PHASE_1_PRODUCT_CONTRACT.md)
- [Phase 2 readiness brief](./docs/PHASE_2_READINESS_BRIEF.md)
- [Phase 3 readiness brief](./docs/PHASE_3_READINESS_BRIEF.md)
- [Phase 4 readiness brief](./docs/PHASE_4_READINESS_BRIEF.md)
