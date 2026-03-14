# Collocation Coach Phase 4 Readiness Brief

## Goal

Make the MVP easier for real people to run and actually receive lessons automatically.

## Scope

This phase includes:
- simple built-in daily delivery loop
- basic startup validation
- clearer self-hosting README
- a little more starter content

## Non-Goals

This phase does not include:
- job queues
- cron integrations
- web admin
- advanced analytics
- production migrations framework

## Acceptance Criteria

- onboarded users can receive a lesson automatically at the selected time
- delivery does not repeat within the same day
- startup fails fast on invalid content or invalid user-facing configuration
- README explains the simplest local and Docker run path

## Simplicity Rule

Prefer one in-process background loop over extra infrastructure.
