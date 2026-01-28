---
phase: 03-anomaly-detection
plan: 03
subsystem: anomaly-detection
tags: [hybrid-detection, z-score, level-shift, static-thresholds, deal-finder]

# Dependency graph
requires:
  - phase: 03-01
    provides: AnomalyDetector, SeasonalAdjuster, static_thresholds
  - phase: 03-02
    provides: LevelShiftDetector, get_price_history
provides:
  - BaselineCalculator for hybrid classification
  - classify_deal convenience function
  - deal_finder integration with anomaly detection
affects: [04-alert-state-machine, email-templates]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Hybrid detection: level shift -> z-score -> static fallback
    - Classification method tracking in deal metadata
    - Graceful degradation when database unavailable

key-files:
  created:
    - anomaly/baseline_calculator.py
  modified:
    - anomaly/__init__.py
    - deal_finder.py

key-decisions:
  - "Level shift checked first (sudden 40%+ drops are immediately exceptional)"
  - "Z-score classification when 30+ observations: z<-2.5=exceptional, z<-2.0=great, z<-1.5=good"
  - "Static threshold fallback for cold start (<30 observations)"
  - "14-observation silent monitoring period for new routes"
  - "classification_method tracked in all deal output for observability"

patterns-established:
  - "BaselineCalculator(db_client) with optional database injection"
  - "Standalone classify_deal() convenience function"
  - "deal_finder.classify_deal() tries anomaly first, falls back to static_legacy"

# Metrics
duration: 3min
completed: 2026-01-28
---

# Phase 3 Plan 3: Hybrid Detection Summary

**BaselineCalculator combining z-score, level shift, and static threshold detection, fully integrated into deal_finder.py for data-driven deal classification**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-28T16:30:22Z
- **Completed:** 2026-01-28T16:33:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created BaselineCalculator that orchestrates all Phase 3 detection methods
- Implemented hybrid classification flow: level shift -> z-score -> static
- Integrated anomaly detection into deal_finder.py with graceful fallback
- Added classification_method, z_score, drop_pct, observation_count to deal output
- Preserved backward compatibility with existing DESTINATIONS thresholds

## Task Commits

Each task was committed atomically:

1. **Task 1: Create BaselineCalculator with hybrid classification** - `1c34538` (feat)
2. **Task 2: Integrate anomaly detection into deal_finder.py** - `9cf45cc` (feat)

## Files Created/Modified

- `anomaly/baseline_calculator.py` - BaselineCalculator class, classify_deal convenience function
- `anomaly/__init__.py` - Added BaselineCalculator, classify_deal exports
- `deal_finder.py` - Integrated anomaly detection, added classification_method to deal output

## Decisions Made

1. **Level shift checked first** - Sudden 40%+ price drops immediately classify as "exceptional" regardless of z-score, as they indicate potential mistake fares
2. **Z-score tier mapping** - z < -2.5: exceptional (with floor check), z < -2.0: great, z < -1.5: good
3. **Silent monitoring period** - Routes with 14-29 observations use static fallback while gathering data
4. **Classification method tracking** - All deals include method (zscore, level_shift, static, static_legacy) for observability
5. **Graceful database fallback** - When Turso unavailable, falls back to static thresholds seamlessly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required beyond existing Turso setup.

## Next Phase Readiness

- Phase 3 (Anomaly Detection) is now COMPLETE
- All DISC requirements implemented:
  - DISC-04: Rolling z-score anomaly detection
  - DISC-05: Level shift detection for mistake fares
  - DISC-06: Cold-start handling with static thresholds
  - DISC-07: Seasonal adjustments for Dec-Jan and Jun-Aug
- deal_finder.py ready for Phase 4 (Alert State Machine) integration
- Classification method tracking enables future analysis of detection accuracy

---
*Phase: 03-anomaly-detection*
*Completed: 2026-01-28*
