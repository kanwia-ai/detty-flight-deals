# Project State: Detty Flight Deals

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-27)

**Core value:** Find genuinely great flight deals to Africa before anyone else -- and make them actionable.
**Current focus:** Phase 2 (Database Migration) - Plan 2/3 complete

## Milestone 1: Beta Launch

**Status:** In Progress
**Phases:** 7 total, 1 complete

| Phase | Status | Requirements |
|-------|--------|-------------|
| 1 - Amadeus Integration | **Complete** (Plan 3/3 done) | DISC-01, DISC-02, DISC-03 |
| 2 - Database Migration | **In Progress** (Plan 2/3 done) | DATA-01 through DATA-05 |
| 3 - Anomaly Detection | Pending | DISC-04 through DISC-07 |
| 4 - Alert State Machine | Pending | ALRT-01 through ALRT-05 |
| 5 - Freemium Infrastructure | Pending | SUBS-01 through SUBS-05, FRML-01 through FRML-04 |
| 6 - Business/First Class | Pending | BUSN-01 through BUSN-03 |
| 7 - Email Delivery Scale | Pending | MAIL-01 through MAIL-04 |

Progress: ███░░░░░░░ ~25% (1/7 phases, 5 plans total complete)

## Blockers

- **Phase 1 action item:** Amadeus API credentials needed to go live (developers.amadeus.com -> Create app -> Get API Key & Secret -> `gh secret set AMADEUS_CLIENT_ID` / `gh secret set AMADEUS_CLIENT_SECRET`)
- **Phase 2 action item:** Turso credentials needed for database (see .planning/phases/02-database-migration/02-USER-SETUP.md)
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
| 2026-01-28 | 15% cross-validation tolerance | Accounts for normal price variance between Amadeus and Google Flights |
| 2026-01-28 | Failed validation: cache updated, no cooldown, logged | Observation is valid data; no alert sent so no cooldown recorded |
| 2026-01-28 | Cron at :15 past hour for priority monitor | Avoids GitHub Actions top-of-hour congestion |
| 2026-01-28 | Shared "detty-state-commit" concurrency group | Prevents git push conflicts between priority + daily workflows |
| 2026-01-28 | cancel-in-progress: false for monitoring workflows | Queue runs instead of dropping monitoring windows |
| 2026-01-28 | AMADEUS_HOSTNAME=test initially | Switch to production after validating with test data |
| 2026-01-28 | INTEGER for prices (cents) not float | Avoid rounding issues in database |
| 2026-01-28 | sync() after every commit for Turso | GitHub Actions ephemeral env needs immediate push to cloud |
| 2026-01-28 | TursoClient fallback returns False/None | Callers handle JSON fallback, not the client |
| 2026-01-28 | Instance-level TursoClient for PriceTracker | Class-based module uses instance in __init__ |
| 2026-01-28 | Module-level TursoClient for deal_finder | Module-level functions use singleton pattern |
| 2026-01-28 | Turso writes in try/except, logged on failure | Matches existing error handling pattern in both files |

## Session Continuity

Last session: 2026-01-28T14:15:54Z
Stopped at: Completed 02-02-PLAN.md (Dual-Write Integration)
Resume file: None

---
*Last updated: 2026-01-28 after completing Phase 2 Plan 2 (Dual-Write Integration)*
