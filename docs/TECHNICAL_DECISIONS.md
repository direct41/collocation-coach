# Collocation Coach Technical Decisions

## Default Stack

- Language: Python 3.13
- Bot framework: aiogram
- Database: PostgreSQL
- Content storage: YAML files in repository
- Packaging: Docker and Docker Compose
- Migrations: lightweight SQL or Alembic

## Why This Stack

- Python is fast to generate and review with AI.
- aiogram fits Telegram bot flows well.
- PostgreSQL is better than SQLite for public self-hosting guidance and future growth.
- YAML makes lesson content editable without code changes.
- Docker lowers setup friction for outside contributors.

## Architectural Boundaries

- `transport`: Telegram handlers and message formatting
- `application`: lesson flow and review logic
- `content`: lesson parsing and validation
- `storage`: users, progress, deliveries, review queue
- `jobs`: scheduled lesson delivery

## MVP Runtime Assumptions

- Start with polling for simplicity.
- Keep admin operations file-based, not web-based.
- Ship sample starter content in the repo.
- Require only essential environment variables for first run.

## Required Secrets And Settings

- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL`
- `APP_ENV`
- `DEFAULT_LOCALE`
- `DEFAULT_TIMEZONE`

## Open-Source Requirement

No secrets may be committed. The repository must run from `.env` or container environment variables only.
