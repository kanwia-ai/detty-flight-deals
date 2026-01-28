---
phase: 01-amadeus-integration
plan: 02
subsystem: monitoring
tags: [cross-validation, monitoring, pipeline, fast-flights, google-flights, email-alerts]

# Dependency graph
requires:
  - phase: 01-01
    provides: "amadeus_client.py (SDK wrapper) and price_tracker.py (cache + cooldown)"
provides:
  - "cross_validator.py: Amadeus vs Google Flights price verification with 15% tolerance"
  - "amadeus_monitor.py: Priority route monitoring coordinator (fetch -> detect -> validate -> alert)"
  - "DISC-02 satisfied: Zero alerts sent on Amadeus-only data"
affects: [01-amadeus-integration plan 03 (GitHub workflow), 04-alert-state-machine]

# Tech tracking
tech-stack:
  added: []
  patterns: [Cross-validation pipeline, Google Flights URL builder, failed-validation logging]

key-files:
  created: [cross_validator.py, amadeus_monitor.py]
  modified: []

key-decisions:
  - "15% tolerance for cross-validation (Amadeus within 15% of Google min = validated)"
  - "Failed validation: price cache updated, no alert cooldown recorded, logged with source=amadeus_FAILED_VALIDATION"
  - "monitor_priority_routes() returns (deals, summary) tuple for accurate run reporting"
  - "google_url always included in validation result (built from inputs, not fast-flights results)"
  - "Single Amadeus observation: lowest_found = highest_found = price, weeks_searched = 1"

patterns-established:
  - "Cross-validation pattern: never alert on single-source data"
  - "Failed-validation logging: source tag distinguishes validated vs unvalidated observations"
  - "Email format bridge: explicit field mapping between Amadeus deal dict and deal_finder email format"
  - "Graceful credential handling: clear error message on missing API credentials, not crash"

# Metrics
duration: 8min
completed: 2026-01-28
---

# Phase 1 Plan 02: Cross-Validation & Monitor Coordinator Summary

**Amadeus-to-Google Flights cross-validation with 15% tolerance, plus priority route monitor that orchestrates the full fetch-detect-validate-alert pipeline -- enforcing DISC-02 (zero single-source alerts)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-28T02:44:46Z
- **Completed:** 2026-01-28T02:52:43Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Created cross_validator.py that verifies Amadeus prices against Google Flights via fast-flights with 15% tolerance
- Built amadeus_monitor.py as the main entry point: orchestrates amadeus_client -> price_tracker -> cross_validator -> deal_finder.send_email
- Enforced DISC-02: `send_email()` is ONLY called with deals that passed `cross_validate_deal()` returning `validated=True`
- Failed validations are logged with `source="amadeus_FAILED_VALIDATION"` for debugging while cache is still updated (observation valid)
- Google Flights URL always available in validation results (built from inputs, not from fast-flights output)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cross_validator.py** - `f7124ce` (feat)
2. **Task 2: Create amadeus_monitor.py** - `1e704e9` (feat)
3. **Cleanup: Remove unused import** - `6fe98f8` (style)

## Files Created/Modified
- `cross_validator.py` - Cross-validation module: cross_validate_deal(), build_google_flights_url(), CROSS_VALIDATION_TOLERANCE=0.15
- `amadeus_monitor.py` - Monitor coordinator: monitor_priority_routes(), format_deals_for_email(), main() entry point

## Decisions Made
- **15% cross-validation tolerance:** Amadeus price must be within 15% of Google Flights minimum to be considered validated. If Amadeus is cheaper, that also validates (better deal found). Tolerance accounts for normal price variance between aggregators.
- **Failed validation behavior:** When cross-validation fails, the price cache IS updated (Amadeus observation is still valid data), but alert cooldown is NOT recorded (no alert was sent, so the deal remains eligible for re-check next run). This is logged with `source="amadeus_FAILED_VALIDATION"` so the price history file distinguishes validated from unvalidated observations.
- **Return tuple from monitor_priority_routes():** Originally, `main()` created a new PriceTracker for the run summary (which would show zeros). Fixed to return `(validated_deals, run_summary)` tuple so the actual tracker's counters are reported.
- **google_url always present:** The Google Flights URL is built from route inputs (origin, dest, dates), not from fast-flights results. This means it's available even when fast-flights fails, so it's always included in the return dict.
- **Single-observation field mapping:** Amadeus returns one price per date, so `lowest_found = highest_found = price` and `weeks_searched = 1`. deal_finder.py's email template uses these for context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed run summary using fresh PriceTracker instead of actual tracker**
- **Found during:** Task 2 (amadeus_monitor.py creation)
- **Issue:** `main()` created a new `PriceTracker()` instance for the run summary, which would have all counters at zero since it was never used for actual monitoring.
- **Fix:** Changed `monitor_priority_routes()` to return `(validated_deals, run_summary)` tuple. `main()` now uses the summary from the actual tracker that performed the monitoring.
- **Files modified:** amadeus_monitor.py
- **Committed in:** 1e704e9 (Task 2 commit)

**2. [Rule 1 - Bug] Removed unused `json` import from amadeus_monitor.py**
- **Found during:** Post-task review
- **Issue:** `import json` was included but never used.
- **Fix:** Removed the unused import.
- **Files modified:** amadeus_monitor.py
- **Committed in:** 6fe98f8 (style commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes improve correctness. No scope creep. Run summary now accurately reports monitoring results; unused import removed for cleanliness.

## Issues Encountered
None

## Safety Guarantees (DISC-02)

The cross-validation safety layer ensures:

1. **Every deal candidate** from `tracker.check_route()` is passed through `cross_validate_deal()`
2. **Only validated deals** (where `validation_result["validated"] == True`) are added to `validated_deals`
3. **`send_email()` is called exclusively** with `format_deals_for_email(validated_deals)` -- deals that were NOT validated never reach this function
4. **Failed validations are logged** with `source="amadeus_FAILED_VALIDATION"` for debugging but do NOT trigger alerts
5. **No cooldown recorded** for failed validations, so the deal is eligible for re-check in the next monitoring run

## Next Phase Readiness
- cross_validator.py and amadeus_monitor.py are ready for the GitHub workflow (Plan 03)
- Plan 03 will create priority_monitor.yml that runs amadeus_monitor.py every 2 hours
- Amadeus API credentials remain a blocker for live testing but NOT for Plan 03 development
- The full import chain works: `python -c "import amadeus_monitor"` succeeds

---
*Phase: 01-amadeus-integration*
*Completed: 2026-01-28*
