# Collocation Coach AI MVP Plan

## Goal

Ship the smallest public MVP of a self-hostable Telegram bot that delivers daily collocation practice and basic review.

## Why 4 phases

Four phases are enough for MVP because they separate the work by dependency order without creating artificial management overhead:
- Phase 1 defines constraints and content contracts
- Phase 2 builds the runnable foundation
- Phase 3 implements the core learning loop
- Phase 4 hardens the project for public release

Fewer than 4 phases would mix product decisions with implementation and increase rework.
More than 4 phases would slow delivery without improving MVP quality.

## Phase 1: Product Contract

### Objective

Lock the MVP behavior before code generation starts.

### Inputs

- product scope
- target learner segment
- lesson format
- required bot commands
- initial content schema

### Tasks

1. Define the exact lesson flow:
   - onboarding
   - daily lesson
   - answer capture
   - review session
   - settings update
2. Define the content model:
   - collocation
   - translation
   - explanation
   - correct example
   - common mistake
   - practice prompt
   - answer options
   - tags
3. Define the data model:
   - users
   - lessons
   - collocations
   - progress
   - review queue
   - deliveries
4. Define the technical non-goals:
   - no AI chat
   - no audio
   - no admin web UI
   - no mobile app
5. Define public repo expectations:
   - local run
   - Docker run
   - environment variables documented
   - sample content included

### Output

- frozen MVP spec
- content schema
- database schema draft
- env var list draft

### Gate

Do not generate application code until the lesson flow and content schema are stable.

## Phase 2: Runtime Foundation

### Objective

Create the minimal runnable bot skeleton and deployment path.

### Tasks

1. Initialize project structure.
2. Choose stack and pin versions.
3. Implement configuration loading and validation.
4. Add Telegram webhook or polling runtime.
5. Add persistent storage.
6. Add migrations or schema bootstrap.
7. Add logging and basic error handling.
8. Add seed loader for lesson content.
9. Add Dockerfile and `.env.example`.
10. Add README setup instructions for self-hosting.

### Output

- project boots locally
- bot can connect to Telegram
- storage works
- sample content loads
- self-hosting instructions exist

### Gate

A new contributor must be able to run the bot with documented env vars and sample content.

## Phase 3: Learning Loop MVP

### Objective

Implement the actual user value.

### Tasks

1. Implement onboarding:
   - start command
   - level choice
   - timezone choice
   - delivery time choice
2. Implement daily lesson delivery:
   - 3 new items
   - 2 review items
3. Implement interaction model:
   - inline button answers
   - self-rating
   - next item progression
4. Implement review logic:
   - simple spaced repetition
   - requeue difficult items
5. Implement commands:
   - `/today`
   - `/review`
   - `/settings`
6. Track analytics events:
   - onboarding complete
   - lesson started
   - lesson completed
   - review opened

### Output

- end-to-end daily lesson flow
- working review cycle
- usable progress tracking

### Gate

One test user must be able to onboard, receive a lesson, complete it, and revisit review without operator help.

## Phase 4: Public MVP Release

### Objective

Make the repository publishable and safe for outside use.

### Tasks

1. Add at least 30 days of starter content.
2. Add tests for critical flows:
   - config validation
   - content loading
   - onboarding
   - review scheduling
3. Add health checks or startup validation.
4. Add license and contribution guidance.
5. Add issue templates if needed.
6. Validate fresh install from zero.
7. Prepare launch README:
   - what it does
   - how to run
   - how to add content
   - known limitations

### Output

- public-ready repository
- reproducible local setup
- minimal test coverage on critical paths
- starter content pack

### Gate

Someone outside the project should be able to fork the repo, set env vars, start the bot, and send themselves lessons.

## Execution Rules for AI Coding

- Generate code only after the current phase contract is explicit.
- Keep modules small and replaceable.
- Separate bot transport, lesson engine, content loader, and storage.
- Prefer plain data files for lesson content over embedded code constants.
- Do not add optional features unless they unblock MVP.
- Each phase ends with a runnable state and updated documentation.

## Suggested First Technical Slice

If starting implementation immediately, the first generated code should cover:
- config loader
- bot bootstrap
- storage bootstrap
- content schema
- `/start` handler

That is the smallest useful slice with low rework risk.
