# Collocation Coach Phase 3 Readiness Brief

## Goal

Implement the first real learning loop on top of the runtime foundation.

## Scope

This phase includes:
- onboarding choices for level, timezone, and daily delivery time
- `/today`, `/review`, and `/settings`
- daily lesson generation with `3 new + up to 2 review`
- interactive item flow with practice and self-rating
- user progress tracking and simple spaced repetition
- tests for lesson generation and review scheduling

## Non-Goals

This phase does not include:
- automatic scheduled delivery worker
- analytics dashboards
- admin content tools
- 30-day content pack
- release hardening

## Acceptance Criteria

- a new user can complete onboarding
- `/today` generates a daily lesson for an onboarded user
- `/review` starts a due-items session when review items exist
- answering and rating items updates user progress
- completed sessions show a summary
- tests cover lesson creation and rating behavior

## Risks

- callback flow drift between Telegram UI and database state
- stale in-progress sessions
- insufficient lesson content for longer manual testing

## Decisions

- daily lesson and review session state live in PostgreSQL
- review items are selected from due progress rows
- daily delivery scheduling remains deferred to the next phase
