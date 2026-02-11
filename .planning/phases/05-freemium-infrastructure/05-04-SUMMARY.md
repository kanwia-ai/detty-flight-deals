---
phase: 05-freemium-infrastructure
plan: 04
subsystem: email
tags: [digest, fomo, freemium, gmail-smtp, html-email, metro-filtering]

# Dependency graph
requires:
  - phase: 05-01
    provides: "Subscriber data foundation (digest_queue table, metro groups, TursoClient methods)"
  - phase: 05-02
    provides: "SubscriberManager CRUD, trial lifecycle (expire_all_trials)"
provides:
  - "Weekly digest generation pipeline (generate_digest, send_weekly_digests)"
  - "FOMO teaser template with urgency tone for conversion (FRML-01)"
  - "Historical price context helper for premium alerts (SUBS-04)"
  - "Weekly digest HTML/plain email templates matching Detty design system"
affects:
  - "05-05 (weekly_digest.yml workflow triggers send_weekly_digests)"
  - "06 (Business/First Class may need digest template extension)"
  - "07 (Email Delivery Scale will replace Gmail SMTP sender)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FOMO teaser urgency pattern: 'You MISSED $X Destination' with red/orange styling"
    - "Digest deal card reuses Detty design system (Pan-African colors, rounded cards)"
    - "Gmail safety cap pattern (90/day constant, checked before each send)"
    - "Metro-filtered content personalization per subscriber"

key-files:
  created:
    - "subscriber/digest.py"
  modified:
    - "alert/templates.py"
    - "subscriber/__init__.py"

key-decisions:
  - "FOMO teasers use random.sample() for variety across weekly digests"
  - "Expired deals (expired=1) treated as FOMO teaser candidates alongside WOW/mistake"
  - "All pending deals marked as sent after digest run (batch, not per-subscriber)"
  - "Digest deal cards use Great tier green styling only (no WOW/mistake cards in main section)"

patterns-established:
  - "FOMO urgency tone: 'You MISSED $X Dest from Origin' + tier-specific subtext"
  - "Digest HTML: gradient header + white greeting card + green deal cards + FOMO section + footer"
  - "Gmail safety limit: GMAIL_DAILY_LIMIT=90 constant checked in send loop"

# Metrics
duration: 3min
completed: 2026-02-10
---

# Phase 5 Plan 4: Weekly Digest Generation Summary

**Metro-filtered weekly digest with FOMO teasers (urgency tone) for free subscribers, capped at 15 deals + 3 teasers per email, sent via Gmail SMTP with 90/day safety limit**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-11T00:15:05Z
- **Completed:** 2026-02-11T00:18:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Weekly digest HTML email matching Detty design system (Pan-African gradient header, green deal cards, inline CSS)
- FOMO teasers with urgency language verified: "You MISSED $580 Lagos from JFK" + tier-specific messaging (FRML-01)
- Historical price context helper for premium instant alerts (z-score + drop percentage) (SUBS-04)
- Full send pipeline: trial expiry -> metro filtering -> personalization -> Gmail SMTP -> mark as sent
- Gmail 90/day safety cap prevents exceeding sending limits (SUBS-05)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend alert/templates.py with digest HTML template and premium context** - `744a818` (feat)
2. **Task 2: Create weekly digest generation and send pipeline** - `17e3693` (feat)

## Files Created/Modified
- `alert/templates.py` - Added 5 new functions: format_historical_context, build_fomo_teaser_html, build_weekly_digest_html, build_weekly_digest_plain, build_weekly_digest_subject, plus _build_digest_deal_card helper
- `subscriber/digest.py` - New file (292 lines): generate_digest() and send_weekly_digests() pipeline with constants MAX_DIGEST_DEALS=15, MAX_FOMO_TEASERS=3, MAX_AGE_DAYS=7
- `subscriber/__init__.py` - Added generate_digest, send_weekly_digests exports

## Decisions Made
- FOMO teasers use random.sample() for variety (different teasers each week)
- Expired deals treated as FOMO teaser candidates alongside WOW/mistake fares
- All pending deals marked as sent in batch after full digest run (not per-subscriber)
- Digest deal cards use Great tier green styling only; FOMO section has red/orange urgency styling
- build_weekly_digest_subject() handles 0, 1, and 2+ deal counts with different formats

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Digest generation pipeline complete and ready for Plan 05 (weekly_digest.yml GitHub Actions workflow)
- send_weekly_digests() is the entry point: `python -m subscriber.digest`
- Requires Turso database credentials (TURSO_DATABASE_URL, TURSO_AUTH_TOKEN) and Gmail SMTP credentials (SMTP_EMAIL, SMTP_PASSWORD) in environment

---
*Phase: 05-freemium-infrastructure*
*Completed: 2026-02-10*
