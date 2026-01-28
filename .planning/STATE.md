# Project State: Detty Flight Deals

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-27)

**Core value:** Find genuinely great flight deals to Africa before anyone else — and make them actionable.
**Current focus:** Phase 1 — Amadeus Integration

## Milestone 1: Beta Launch

**Status:** In Progress
**Phases:** 7 total, 0 complete

| Phase | Status | Requirements |
|-------|--------|-------------|
| 1 - Amadeus Integration | **In Progress** (Plan 1/3 complete) | DISC-01, DISC-02, DISC-03 |
| 2 - Database Migration | ○ Pending | DATA-01 through DATA-05 |
| 3 - Anomaly Detection | ○ Pending | DISC-04 through DISC-07 |
| 4 - Alert State Machine | ○ Pending | ALRT-01 through ALRT-05 |
| 5 - Freemium Infrastructure | ○ Pending | SUBS-01 through SUBS-05, FRML-01 through FRML-04 |
| 6 - Business/First Class | ○ Pending | BUSN-01 through BUSN-03 |
| 7 - Email Delivery Scale | ○ Pending | MAIL-01 through MAIL-04 |

Progress: █░░░░░░░░░ ~5%

## Blockers

- **Phase 1 blocker:** Amadeus API credentials needed (developers.amadeus.com -> Create app -> Get API Key & Secret)
- **Phase 7 early trigger:** Must start if subscriber count approaches 50 (Gmail SMTP hard limit = 100/day)

## Key Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-01-27 | Amadeus supplements fast-flights (not replaces) | Amadeus missing Delta, AA, BA, LCCs |
| 2026-01-27 | Turso for price DB (not Postgres/Supabase) | Free tier fits budget, SQLite compatible |
| 2026-01-27 | Resend for email delivery (not SendGrid/SES) | 3K free/month, good DX, DKIM built-in |
| 2026-01-27 | 7-phase sequential build order | Each phase independently valuable |
| 2026-01-28 | Use amadeus SDK (not raw requests) for OAuth2 | SDK handles token management automatically |
| 2026-01-28 | 12 sampled dates for Offers Search fallback | African routes often missing from Cheapest Date cache |
| 2026-01-28 | 24-hour flat cooldown for all tiers (Phase 1) | Phase 4 will implement tier-specific FSM |
| 2026-01-28 | Route-level cache keys (not date-level) | Amadeus returns many dates per route |

## Session Continuity

Last session: 2026-01-28T02:40:32Z
Stopped at: Completed 01-01-PLAN.md (Amadeus Client & Price Tracker)
Resume file: .planning/phases/01-amadeus-integration/01-02-PLAN.md

---
*Last updated: 2026-01-28 after completing 01-01 plan*
