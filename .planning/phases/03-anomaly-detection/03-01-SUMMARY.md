---
phase: 03-anomaly-detection
plan: 01
subsystem: anomaly
tags: [scipy, numpy, pandas, z-score, statistical-analysis, price-detection]

# Dependency graph
requires:
  - phase: 02-database-migration
    provides: TursoClient for price history storage
provides:
  - AnomalyDetector class with rolling z-score calculations
  - SeasonalAdjuster for Dec-Jan and Jun-Aug threshold adjustments
  - Static threshold fallbacks for cold-start routes
  - EXCEPTIONAL_FLOORS for mistake fare detection
affects: [03-02, 03-03, deal_finder integration]

# Tech tracking
tech-stack:
  added: [scipy>=1.11.0, numpy>=1.24.0, pandas>=2.0.0]
  patterns: [rolling z-score anomaly detection, seasonal multipliers, tier-based classification]

key-files:
  created:
    - anomaly/__init__.py
    - anomaly/anomaly_detector.py
    - anomaly/seasonal_adjustments.py
    - anomaly/static_thresholds.py
  modified:
    - requirements.txt

key-decisions:
  - "Rolling z-score with z < -2.5 threshold for anomaly detection (bottom ~0.6% of distribution)"
  - "Seasonal multipliers: Dec-Jan +50%, Jun-Aug +25%, others 1.0"
  - "Zero std replaced with NaN (no z-score for constant prices)"
  - "Static thresholds stored in dollars, runtime conversion to cents"

patterns-established:
  - "AnomalyDetector: window=90, min_periods=30, z_threshold=-2.5 defaults"
  - "All prices in CENTS (INTEGER) per Phase 2 decision"
  - "classify_with_static supports route parsing (JFK-LOS -> LOS)"

# Metrics
duration: 12min
completed: 2026-01-28
---

# Phase 3 Plan 1: Core Detection Classes Summary

**Rolling z-score anomaly detector with seasonal adjustments and static threshold fallbacks for data-driven deal classification**

## Performance

- **Duration:** 12 min
- **Started:** 2026-01-28T16:22:03Z
- **Completed:** 2026-01-28T16:34:00Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- AnomalyDetector with rolling z-score detects anomalously cheap fares (z < -2.5)
- SeasonalAdjuster applies research-backed multipliers for peak travel periods
- Static threshold fallbacks enable classification for routes with <30 observations
- EXCEPTIONAL_FLOORS identify potential mistake fares below historical lows

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AnomalyDetector with rolling z-score** - `3829dbe` (feat)
2. **Task 2: Create SeasonalAdjuster with research-backed multipliers** - `cb50c7e` (feat)
3. **Task 3: Create static_thresholds with fallback classification** - `5068a61` (feat)

## Files Created/Modified

- `anomaly/__init__.py` - Package exports for AnomalyDetector, SeasonalAdjuster, static thresholds
- `anomaly/anomaly_detector.py` - Rolling z-score calculations (detect(), calculate_rolling_zscore(), is_anomaly())
- `anomaly/seasonal_adjustments.py` - SEASONAL_MULTIPLIERS dict, adjust_threshold(), normalize_price()
- `anomaly/static_thresholds.py` - STATIC_THRESHOLDS, EXCEPTIONAL_FLOORS, classify_with_static()
- `requirements.txt` - Added scipy, numpy, pandas dependencies

## Decisions Made

1. **Rolling z-score approach** - Adapts to recent price trends rather than global statistics, capturing seasonality
2. **z < -2.5 threshold** - Catches bottom ~0.6% of price distribution (approximately 50%+ savings)
3. **Seasonal multipliers from research** - Dec-Jan 1.50 (Detty December ~2x prices), Jun-Aug 1.25 (summer vacation)
4. **Zero std handling** - Replace with NaN instead of error, marks as insufficient variance for z-score
5. **Thresholds in dollars, runtime cents** - Match pm-docs/pricing-tiers.md format, convert in classify_with_static()

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan test case had incorrect expected tier**
- **Found during:** Task 3 verification
- **Issue:** Plan expected "$650 LOS should be great" but LOS thresholds have wow=700 and great=700 (same value), so $650 < $700 is "wow" not "great"
- **Fix:** Implemented correct tier logic; classify_with_static returns "wow" for $650 LOS
- **Files modified:** None (code was correct, test expectation was wrong)
- **Verification:** Updated test to expect "wow" for $650 LOS, all assertions pass
- **Committed in:** 5068a61 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug in plan test case)
**Impact on plan:** Minor test case correction. Tier classification logic is correct per pm-docs/pricing-tiers.md.

## Issues Encountered

- Interleaved commits from parallel 03-02 execution appeared in git log, but did not affect 03-01 task execution

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Core detection classes ready for 03-02 (Level Shift Detection) integration
- AnomalyDetector can be called by LevelShiftDetector for hybrid detection
- SeasonalAdjuster available for threshold adjustments across detection methods
- classify_with_static provides cold-start fallback for any detection method

---
*Phase: 03-anomaly-detection*
*Completed: 2026-01-28*
