# Collocation Coach

Open-source Telegram bot for learning English collocations through short daily lessons.

## Product Idea

`Collocation Coach` helps learners build natural English by practicing a few high-value collocations every day.

Initial MVP focus:
- Telegram bot first
- 3 new collocations + 2 reviews per daily lesson
- short explanations in Russian
- contrast with common mistakes
- simple spaced repetition

## Documents

- [AI MVP plan](./docs/AI_MVP_PLAN.md)
- [Product plan](./docs/PRODUCT_PLAN.md)
- [Technical decisions](./docs/TECHNICAL_DECISIONS.md)
- [Phase 1 product contract](./docs/PHASE_1_PRODUCT_CONTRACT.md)
- [Phase 2 readiness brief](./docs/PHASE_2_READINESS_BRIEF.md)
- [Phase 3 readiness brief](./docs/PHASE_3_READINESS_BRIEF.md)

## Planned Open-Source Goals

- anyone can self-host the bot
- setup should require only a small set of environment variables
- content should be editable without changing core bot logic

## Default Technical Direction

- language: Python 3.13
- Telegram framework: aiogram
- database: PostgreSQL for public MVP
- local development: Docker Compose
- content format: YAML files
- deployment: single container app plus Postgres

## Current Foundation

Implemented now:
- Python project scaffold
- config loading and validation
- YAML lesson parsing
- PostgreSQL schema bootstrap
- lesson content seeding
- Telegram polling runtime
- `/start` and `/help`
- Dockerfile and Docker Compose
- tests for config and content loading

## Local Run

1. Copy `.env.example` to `.env`
2. Set `TELEGRAM_BOT_TOKEN`
3. Start PostgreSQL
4. Run the bot

### With uv

```bash
cp .env.example .env
uv sync
uv run python -m collocation_coach.main
```

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

## Current Commands

- `/start`
- `/help`
- `/today`
- `/review`
- `/settings`

## Repository Status

Phase 3 learning loop is in progress.
