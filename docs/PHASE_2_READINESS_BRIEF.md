# Collocation Coach Phase 2 Readiness Brief

## Goal

Build the smallest runnable foundation for the Telegram bot without leaking Phase 3 lesson logic into the codebase.

## Scope

This phase includes:
- Python project initialization
- environment configuration loading and validation
- module structure aligned with repository architecture
- PostgreSQL connection and schema bootstrap
- YAML lesson content loading and validation
- idempotent content seeding into the database
- Telegram polling runtime
- `/start` and `/help` handlers
- Docker-based local run path
- minimal tests for config and content loading

## Non-Goals

This phase does not include:
- daily lesson generation
- review scheduling
- `/today`, `/review`, `/settings`
- analytics dashboards
- delivery jobs execution
- complete onboarding flow

## Inputs

- [Phase 1 product contract](./PHASE_1_PRODUCT_CONTRACT.md)
- [Technical decisions](./TECHNICAL_DECISIONS.md)
- sample content under `content/`

## Acceptance Criteria

- application starts with valid env vars
- database schema is created automatically
- sample lesson content is loaded and seeded
- Telegram bot can start polling
- `/start` replies and creates or updates a user record
- `/help` replies with available current commands
- Docker Compose can start app plus PostgreSQL
- config and content loader tests pass

## Integration Points

- ingress: Telegram updates
- content source: YAML files from `CONTENT_DIR`
- persistence: PostgreSQL via SQLAlchemy async engine
- process runtime: single polling worker

## Risks

- content schema drift between YAML and database
- startup failures due to missing env vars
- bot startup blocked by invalid content files

## Decisions

- startup must fail fast on invalid config
- startup must fail fast on invalid lesson content
- content seeding must be idempotent
- transport logic must not contain lesson selection logic yet
