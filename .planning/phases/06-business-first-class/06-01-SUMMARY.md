---
phase: 06-business-first-class
plan: 01
subsystem: api, anomaly-detection
tags: [amadeus, travelClass, premium-cabin, business-class, budget-tracking, cache-keys]

# Dependency graph
requires:
  - phase: 01-amadeus-integration
    provides: amadeus_client.py with Flight Offers Search
  - phase: 03-anomaly-detection
    provides: static_thresholds.py with classify_with_static and EXCEPTIONAL_FLOORS
provides:
  - search_offers_for_cabin() function with travelClass parameter
  - CABIN_CLASSES constant for premium cabin monitoring
  - PREMIUM_STATIC_THRESHOLDS dict for cold-start classification
  - classify_premium_cabin() for single-tier deal/exceptional detection
  - PremiumBudget class for API call tracking with monthly rollover
  - Cabin-class-aware cache keys in PriceTracker
affects: [06-02 premium cabin monitor orchestrator, 06-03 premium cabin workflow/alerts]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cabin-class-aware cache keys: economy='JFK-LOS', premium='JFK-LOS:BUSINESS'"
    - "Single-tier premium classification: deal/exceptional (no Good/Great/WOW)"
    - "JSON-based API budget persistence with monthly rollover"
    - "Separate function for premium cabin search (not modifying economy path)"

key-files:
  created:
    - premium_budget.py
  modified:
    - amadeus_client.py
    - price_tracker.py
    - anomaly/static_thresholds.py
    - anomaly/__init__.py
    - .gitignore

key-decisions:
  - "Separate search_offers_for_cabin() function (not modifying search_offers_fallback())"
  - "5,000 calls/month conservative budget start (not 6,250 theoretical max)"
  - "Single-tier premium classification: deal if below threshold, exceptional if below 60% of deal threshold"
  - "Economy cache keys unchanged for backward compatibility"
  - "Mistake fare threshold = 60% of deal threshold (75%+ off normal price)"

patterns-established:
  - "Cache key format: 'ORIGIN-DEST:CABIN_CLASS' for premium, 'ORIGIN-DEST' for economy"
  - "Premium static thresholds structure: {cabin_class: {dest: {normal, deal}}}"
  - "PremiumBudget pattern: load, check, record, save per monitoring run"

# Metrics
duration: 7min
completed: 2026-02-10
---

# Phase 6 Plan 1: Premium Cabin Data Layer Summary

**Cabin-class-aware Amadeus search with travelClass parameter, premium static thresholds for BUSINESS/FIRST/PREMIUM_ECONOMY, API budget tracker with $25/month hard cap, and backward-compatible cache keys**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-11T04:04:54Z
- **Completed:** 2026-02-11T04:11:49Z
- **Tasks:** 2
- **Files modified:** 5 (+ 1 created)

## Accomplishments
- Extended Amadeus client with search_offers_for_cabin() supporting travelClass parameter for premium cabin queries
- Added PREMIUM_STATIC_THRESHOLDS with per-cabin per-destination pricing for cold-start classification
- Created PremiumBudget class with JSON persistence, monthly rollover, and budget exhaustion detection
- Made cache keys cabin-class-aware while maintaining full backward compatibility with economy monitoring

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Amadeus client + premium static thresholds** - `21088f4` (feat)
2. **Task 2: API budget tracker + cabin-class-aware cache keys** - `6ee37ac` (feat)
3. **Gitignore premium_budget.json** - `4382d17` (chore)

## Files Created/Modified
- `amadeus_client.py` - Added search_offers_for_cabin() with travelClass parameter and CABIN_CLASSES constant
- `anomaly/static_thresholds.py` - Added PREMIUM_STATIC_THRESHOLDS dict and classify_premium_cabin() function
- `anomaly/__init__.py` - Exported new PREMIUM_STATIC_THRESHOLDS and classify_premium_cabin symbols
- `price_tracker.py` - Extended make_cache_key() with optional cabin_class parameter
- `premium_budget.py` - New PremiumBudget class for API call tracking with monthly rollover
- `.gitignore` - Added premium_budget.json to prevent runtime state from being committed

## Decisions Made
- **Separate function for premium cabin search:** Created search_offers_for_cabin() rather than modifying search_offers_fallback(). This keeps economy monitoring completely unchanged and avoids regression risk.
- **Conservative 5,000 calls/month budget:** Started below the theoretical max of 6,250 calls (~$25 at $0.004/call). Can be increased by editing MAX_CALLS_PER_MONTH constant after seeing first production invoice.
- **Single-tier classification for premium cabins:** Per CONTEXT.md, no Good/Great/WOW distinction. A premium cabin price is either a "deal" (below threshold) or "exceptional" (potential mistake fare, below 60% of deal threshold).
- **Mistake fare threshold at 60% of deal threshold:** This means a price must be 75%+ off the normal price to be flagged as a potential mistake fare. Conservative to avoid false positives.
- **Economy cache keys unchanged:** `make_cache_key("JFK", "LOS")` still returns `"JFK-LOS"` (no cabin suffix). Only premium cabins get the `:CABIN_CLASS` suffix. This prevents any breakage in existing economy monitoring.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added premium_budget.json to .gitignore**
- **Found during:** Task 2 (PremiumBudget class creation)
- **Issue:** The PremiumBudget class creates premium_budget.json at runtime for state persistence. Without gitignoring it, the file would be committed to the repo and conflict between environments.
- **Fix:** Added `premium_budget.json` to .gitignore
- **Files modified:** .gitignore
- **Verification:** `git check-ignore premium_budget.json` confirms it is ignored
- **Committed in:** 4382d17

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for correct operation in CI/CD. No scope creep.

## Issues Encountered
None - plan executed smoothly. All imports and verifications passed on first attempt.

## User Setup Required
None - no external service configuration required. Premium cabin monitoring will use existing Amadeus credentials.

## Next Phase Readiness
- Data layer is complete: search function, thresholds, budget tracker, cache keys all in place
- Plan 02 (Premium Cabin Monitor Orchestrator) can now build on these primitives
- Plan 03 (Workflow + Alert Templates) can use PREMIUM_STATIC_THRESHOLDS and classify_premium_cabin()
- Existing economy monitoring is completely unaffected (all changes are additive)

---
*Phase: 06-business-first-class*
*Completed: 2026-02-10*
