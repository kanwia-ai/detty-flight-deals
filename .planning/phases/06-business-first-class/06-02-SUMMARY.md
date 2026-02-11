---
phase: 06-business-first-class
plan: 02
subsystem: monitoring, anomaly-detection
tags: [premium-cabin, business-class, orchestrator, fsm, alert-routing, budget-enforcement]

# Dependency graph
requires:
  - phase: 06-business-first-class
    provides: search_offers_for_cabin(), PremiumBudget, classify_premium_cabin(), CABIN_CLASSES
  - phase: 03-anomaly-detection
    provides: BaselineCalculator with classify_deal()
  - phase: 04-alert-state-machine
    provides: AlertStateMachine with cabin-aware route keys
  - phase: 05-freemium-infrastructure
    provides: AlertRouter for premium-only deal routing
provides:
  - PremiumCabinMonitor class with run() entry point for GitHub Actions
  - Premium cabin classification path in BaselineCalculator (silent period + static fallback)
  - Cabin-class-aware FSM route keys (e.g., "JFK-LOS:BUSINESS")
  - End-to-end pipeline: fetch -> classify -> FSM -> route for premium cabins
affects: [06-03 premium cabin workflow and alert templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cabin-aware FSM route keys: 'ORIGIN-DEST:CABIN_CLASS' for state tracking"
    - "Premium silent monitoring: 28 observations before any alerts fire"
    - "All premium cabin deals routed as WOW tier for maximum urgency"
    - "Feature flag pattern: PREMIUM_CABIN_MONITORING_ENABLED env var"

key-files:
  created:
    - premium_cabin_monitor.py
  modified:
    - anomaly/baseline_calculator.py

key-decisions:
  - "All premium cabin deals routed as WOW tier (email + SMS to premium subscribers)"
  - "28-observation silent monitoring period for premium cabins (vs 14 for economy)"
  - "PREMIUM_CABIN_MONITORING_ENABLED feature flag defaults to true"
  - "Google Flights URL includes tfc= cabin class parameter (1=Econ, 2=PE, 3=Biz, 4=First)"

patterns-established:
  - "Premium cabin monitor is separate orchestrator (not added to economy pipeline)"
  - "BaselineCalculator routes premium cabins to classify_premium_cabin() in static fallback"
  - "Silent period returns None (not a result dict), letting FSM see normal prices"

# Metrics
duration: 3min
completed: 2026-02-11
---

# Phase 6 Plan 2: Premium Cabin Monitor Orchestrator Summary

**End-to-end premium cabin monitoring pipeline: Amadeus fetch with budget enforcement, BaselineCalculator with 28-observation silent period, cabin-aware FSM, and WOW-tier routing to premium subscribers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-11T04:15:32Z
- **Completed:** 2026-02-11T04:18:32Z
- **Tasks:** 2
- **Files modified:** 1 modified + 1 created

## Accomplishments
- Extended BaselineCalculator with premium cabin classification path: 28-observation silent monitoring, then premium static thresholds for deal/exceptional classification
- Created PremiumCabinMonitor orchestrator (409 lines) that runs the full pipeline end-to-end: fetch prices from Amadeus, classify deals, process through FSM with cabin-aware route keys, route to premium subscribers via AlertRouter
- Budget enforcement at two levels: before each run (exhaustion check) and before each route-cabin combo (remaining calls check)
- Feature flag (PREMIUM_CABIN_MONITORING_ENABLED) for safe rollout

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend BaselineCalculator for premium cabin classification** - `5057ca3` (feat)
2. **Task 2: Create premium cabin monitor orchestrator** - `e46dfc9` (feat)

## Files Created/Modified
- `anomaly/baseline_calculator.py` - Added classify_premium_cabin import, PREMIUM_SILENT_OBSERVATIONS constant, premium cabin branch in classify_deal() Step 4, dest_code extraction with cabin-aware key parsing
- `premium_cabin_monitor.py` - New PremiumCabinMonitor class with run(), _process_observation(), _build_google_flights_url(), and main() entry point

## Decisions Made
- **All premium cabin deals routed as WOW tier:** Per CONTEXT.md, premium cabin deals are rare, high-value events treated like mistake fares. Every premium deal gets instant email + SMS to premium subscribers with phone numbers. The email template (Plan 03) will add cabin class context.
- **28-observation silent monitoring for premium cabins:** Double the economy silent period (14 obs) because premium cabin static thresholds are LOW confidence estimates. Prevents false positive alerts during the first 4+ weeks of data collection.
- **Feature flag defaults to "true":** PREMIUM_CABIN_MONITORING_ENABLED env var allows disabling without code change. Default "true" means it runs automatically once the workflow is deployed.
- **Google Flights URL with tfc parameter:** Built cabin-class-aware Google Flights URLs using tfc=2 (Premium Economy), tfc=3 (Business), tfc=4 (First) so deal links open to the correct cabin class.
- **Silent period feeds normal prices to FSM:** When BaselineCalculator returns None during silent period, the monitor feeds the price as a "normal" observation to the FSM. This keeps the FSM reset counter accurate while suppressing alerts.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None - all imports and verifications passed on first attempt.

## User Setup Required
None - no external service configuration required. Premium cabin monitoring uses existing Amadeus credentials and Turso database.

## Next Phase Readiness
- Monitor orchestrator is complete: ready for GitHub Actions workflow (Plan 03)
- Alert templates need premium cabin context (cabin class badge, premium pricing)
- Existing economy monitoring is completely unaffected (amadeus_monitor.py untouched)
- All pipeline components verified: BaselineCalculator, FSM, AlertRouter integrations tested

---
*Phase: 06-business-first-class*
*Completed: 2026-02-11*
