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

## Repository Status

Planning stage. No production code yet.
