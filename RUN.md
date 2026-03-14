# Run Collocation Coach

This file is the practical self-hosting guide.

## 1. Prerequisites

You need:
- Python `3.13`
- PostgreSQL `14+`
- `uv` for the local Python workflow

Optional:
- Docker and Docker Compose

## 2. Create a Telegram Bot

1. Open `@BotFather` in Telegram
2. Run `/newbot`
3. Copy the bot token
4. Put the token into `.env`

If your token was exposed before, rotate it in `@BotFather` before launch.

## 3. Configure Environment

```bash
cp .env.example .env
```

Set at least:

```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/collocation_coach
```

## 4. Prepare PostgreSQL

Create a database:

```bash
psql -U postgres -c "CREATE DATABASE collocation_coach;"
```

If you also need a local user:

```bash
psql -U postgres -c "CREATE USER collocation WITH PASSWORD 'collocation';"
psql -U postgres -c "ALTER USER collocation CREATEDB;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE collocation_coach TO collocation;"
```

Then update `DATABASE_URL` if you do not use the default `postgres` user.

## 5. Run With uv

```bash
uv sync
uv run python -m collocation_coach.main
```

What happens on startup:
- config is loaded from `.env`
- lesson files are validated
- database tables are created if missing
- lesson content is seeded into Postgres
- Telegram polling starts

## 6. Run With Docker Compose

```bash
docker compose up --build
```

This is the easiest way to run the bot with Postgres if Docker is already installed.

## 7. First Product Check

After the bot starts:

1. Open the bot in Telegram
2. Send `/start`
3. Choose level, timezone, and delivery time
4. Send `/today`
5. Finish one lesson
6. Send `/review`

If these commands work, your instance is ready.

## 8. How Content Works

Lessons are stored as YAML files:
- `content/lessons/a2_b1`
- `content/lessons/b1_b2`

Each lesson file contains:
- lesson metadata
- `3` collocation items
- Russian explanation
- correct example
- common mistake
- multiple-choice practice

After changing lesson files, restart the bot to reseed content.

## 9. Common Issues

`Bot does not start`
- check `TELEGRAM_BOT_TOKEN`
- check `DATABASE_URL`
- make sure Postgres is running

`Polling starts but bot does not answer`
- make sure no other process is running the same bot token

`Content fails to load`
- run `uv run pytest`
- inspect the last edited YAML file for invalid structure

## 10. Useful Commands

```bash
uv run pytest
uv run python -m compileall src
docker compose config
```

## 11. Open-Source Usage

Anyone should be able to fork this repository, set `.env`, and run their own copy of the bot.
