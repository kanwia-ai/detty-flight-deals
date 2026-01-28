---
phase: 01-amadeus-integration
plan: 01
subsystem: api
tags: [amadeus, flight-search, price-tracking, sdk, oauth2, caching]

# Dependency graph
requires:
  - phase: none
    provides: "First plan in first phase -- builds on existing deal_finder.py patterns"
provides:
  - "amadeus_client.py: SDK wrapper with Cheapest Date Search + Offers Search fallback"
  - "price_tracker.py: PriceTracker class with JSON price cache, alert cooldown, API budget tracking"
  - "requirements.txt updated with amadeus>=12.0.0"
  - "deal_finder.py log_price_search() now accepts optional source parameter"
affects: [01-amadeus-integration plan 02 (monitor coordinator), 02-database-migration, 03-anomaly-detection]

# Tech tracking
tech-stack:
  added: [amadeus>=12.0.0]
  patterns: [SDK wrapper with fallback strategy, JSON-based state persistence, alert cooldown dedup]

key-files:
  created: [amadeus_client.py, price_tracker.py]
  modified: [requirements.txt, deal_finder.py]

key-decisions:
  - "Use amadeus SDK (not raw requests) for automatic OAuth2 token management"
  - "12 sampled dates every 2 weeks for Offers Search fallback (best-effort coverage for cache-missing African routes)"
  - "24-hour flat cooldown for all tiers in Phase 1 (Phase 4 implements tier-specific FSM)"
  - "Added optional source param to deal_finder.log_price_search() for multi-source price history tracking"
  - "Route-level cache keys (not date-level) since Amadeus returns many dates per route"

patterns-established:
  - "SDK wrapper pattern: thin wrapper around third-party SDK with fallback strategy"
  - "Price normalization: all prices converted to int immediately after retrieval"
  - "JSON state persistence: same Path(__file__).parent pattern as seen_deals.json"
  - "Alert dedup: cooldown-based approach to prevent duplicate alerts"

# Metrics
duration: 5min
completed: 2026-01-28
---

# Phase 1 Plan 01: Amadeus Client & Price Tracker Summary

**Amadeus SDK wrapper with Cheapest Date Search + Offers Search fallback for 6 priority US-Africa routes, plus PriceTracker with JSON-based price cache and 24-hour alert cooldown**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-28T02:35:17Z
- **Completed:** 2026-01-28T02:40:32Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created amadeus_client.py with SDK-based API communication (no hand-rolled OAuth2)
- Implemented dual search strategy: Cheapest Date Search (cached, fast) with Offers Search fallback (12 sampled dates for African routes)
- Built PriceTracker class with JSON-persisted price cache, alert cooldown (24h), and API budget tracking (2160 calls/month)
- Extended deal_finder.py log_price_search() to support multiple data sources (backward compatible)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create amadeus_client.py** - `b3fea7c` (feat)
2. **Task 2: Create price_tracker.py** - `325e8ca` (feat)

## Files Created/Modified
- `amadeus_client.py` - Amadeus SDK wrapper with create_amadeus_client(), get_prices_for_route(), PRIORITY_ROUTES (6 routes), generate_sample_dates() (12 dates)
- `price_tracker.py` - PriceTracker class with price cache, alert cooldown, deal detection via classify_deal(), API budget tracking
- `requirements.txt` - Added amadeus>=12.0.0 dependency
- `deal_finder.py` - Added optional `source` parameter to log_price_search() for multi-source tracking

## Decisions Made
- **SDK over raw requests:** The amadeus Python SDK handles OAuth2 token management automatically, eliminating manual token refresh logic and reducing error surface.
- **12 sampled dates (not 6):** African routes (JFK-LOS, EWR-ACC) are commonly NOT in the Amadeus Cheapest Date Search cache. 12 dates every 2 weeks provides better coverage for fallback, though still best-effort compared to cache's 30-60+ dates.
- **24-hour flat cooldown:** All deal tiers use the same 24-hour cooldown in Phase 1. Phase 4 will implement the full FSM with tier-specific cooldowns (e.g., shorter for WOW deals).
- **Route-level cache keys:** Cache key is `{origin}-{dest}` not `{origin}-{dest}-{date}` because Amadeus returns many dates per route and we track the route's best price.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added source parameter to deal_finder.log_price_search()**
- **Found during:** Task 2 (price_tracker.py creation)
- **Issue:** Plan specified calling log_price_search() with a source parameter ("amadeus_cheapest_date" or "amadeus_offers_search"), but the existing function had hardcoded `"source": "fast_flights"` with no parameter to override it.
- **Fix:** Added optional `source` parameter with default `"fast_flights"` for backward compatibility. Existing callers unchanged; price_tracker.py passes the Amadeus source tag.
- **Files modified:** deal_finder.py
- **Verification:** Both old-style (no source arg) and new-style (with source arg) calls work correctly
- **Committed in:** 325e8ca (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Backward-compatible enhancement to existing function. No scope creep. Required for correct multi-source price history tracking.

## Issues Encountered
None

## User Setup Required

**External services require manual configuration.** Amadeus API credentials needed before live usage:

1. Go to developers.amadeus.com -> My Self-Service Workspace -> Create New App
2. Get API Key and API Secret
3. Set environment variables:
   - `AMADEUS_CLIENT_ID` (API Key)
   - `AMADEUS_CLIENT_SECRET` (API Secret)
4. Optionally set `AMADEUS_HOSTNAME=production` for real data (default: `test`)

**Note:** The modules import and function correctly without credentials (structural correctness verified). Credentials are only needed for actual API calls.

## Next Phase Readiness
- amadeus_client.py and price_tracker.py are ready for the monitor coordinator (Plan 02)
- Plan 02 will create amadeus_monitor.py that ties these together into a full monitoring run
- Amadeus API credentials are a blocker for live testing but NOT for Plan 02 development

---
*Phase: 01-amadeus-integration*
*Completed: 2026-01-28*
