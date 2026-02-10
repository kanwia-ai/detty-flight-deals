---
phase: 04-alert-state-machine
plan: 01
subsystem: alert
tags: [fsm, state-machine, alert-fatigue, tier-escalation, sqlite]

# Dependency graph
requires:
  - phase: 02-database-migration
    provides: TursoClient with alert_state table and CRUD methods
  - phase: 03-anomaly-detection
    provides: Deal tier classification (good/great/wow) from anomaly detection
provides:
  - AlertState Enum with 5 FSM states
  - RouteState dataclass for per-route state tracking
  - AlertStateMachine class with process() for tier-escalation logic
  - Database migration for last_alert_tier and last_alert_price_cents columns
  - Idempotent run_migrations() pattern for schema evolution
affects:
  - 04-02 (integration wiring will use AlertStateMachine in deal pipeline)
  - 05-freemium-infrastructure (tier routing: Great=free, WOW/MISTAKE=premium)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FSM transition table pattern: dict[(state, event)] -> (new_state, should_alert)"
    - "PRAGMA table_info migration pattern for SQLite column additions"
    - "Transient ALERTING -> stable ALERTED state pattern"
    - "In-memory fallback when db_client is None"

key-files:
  created:
    - alert/__init__.py
    - alert/state_machine.py
  modified:
    - db/schema.py
    - db/client.py

key-decisions:
  - "ALERTING states are transient: process() immediately transitions to ALERTED after alert"
  - "Unknown deal tiers treated as normal_price (safe default)"
  - "Reset clears last_alert_tier and last_alert_price_cents (full cycle reset)"
  - "Migration runs unconditionally in TursoClient.__init__ (idempotent, ensures columns exist)"

patterns-established:
  - "FSM transition table: static dict mapping (state, event) -> (new_state, should_alert)"
  - "PRAGMA table_info migration: check column existence before ALTER TABLE ADD COLUMN"
  - "RouteState dataclass: typed state representation with database round-trip via _dict_to_route_state"

# Metrics
duration: 3min
completed: 2026-02-10
---

# Phase 4 Plan 1: Core Alert State Machine Summary

**5-state FSM with transition table for tier-escalation alerts, eliminating re-alerts for same-tier price changes and supporting Great->WOW escalation override**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T21:44:38Z
- **Completed:** 2026-02-10T21:47:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- AlertState FSM with 5 states (NORMAL, GREAT_ALERTING, GREAT_ALERTED, WOW_ALERTING, WOW_ALERTED) and transition table covering all state/event pairs
- Same-tier suppression (no re-alert), escalation override (Great->WOW always alerts), and silent de-escalation (WOW->Great)
- Automatic reset to NORMAL after 3 consecutive normal prices, enabling fresh alert cycle
- Database migration pattern with PRAGMA table_info for idempotent column additions, wired into TursoClient.__init__

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Database Schema and Client** - `531923d` (feat)
2. **Task 2: Create Alert State Machine Module** - `2ba9b03` (feat)

**Plan metadata:** pending (docs: complete plan)

## Files Created/Modified
- `alert/__init__.py` - Package exports for AlertState, RouteState, AlertStateMachine
- `alert/state_machine.py` - Core FSM with 5 states, transition table, process() method, DB wiring (439 lines)
- `db/schema.py` - Added last_alert_tier and last_alert_price_cents to alert_state table, MIGRATION_COLUMNS constant, run_migrations() function
- `db/client.py` - Extended update_alert_state() and get_alert_state() for new columns, added _run_migrations() called in __init__

## Decisions Made
- ALERTING states are transient: process() immediately transitions to ALERTED after sending alert. This avoids needing external "ack" and keeps the FSM self-contained.
- Unknown deal tiers are treated as normal_price events (safe default, logged as warning)
- Reset clears both last_alert_tier and last_alert_price_cents so the next deal cycle starts completely fresh
- Migration runs unconditionally in TursoClient.__init__ -- idempotent via PRAGMA table_info check, ensures columns exist before any FSM operation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AlertStateMachine is ready for integration into the deal pipeline (Plan 04-02)
- The FSM works in-memory when no db_client is provided, enabling easy unit testing
- Plan 04-02 will wire AlertStateMachine into the existing deal_finder and monitoring workflows

---
*Phase: 04-alert-state-machine*
*Completed: 2026-02-10*
