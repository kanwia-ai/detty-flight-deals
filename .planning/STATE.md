# Project State: Detty Flight Deals

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-27)

**Core value:** Find genuinely great flight deals to Africa before anyone else -- and make them actionable.
**Current focus:** Phase 5 (Freemium Infrastructure) - Plan 1 of N complete

## Milestone 1: Beta Launch

**Status:** In Progress
**Phases:** 7 total, 4 complete

| Phase | Status | Requirements |
|-------|--------|-------------|
| 1 - Amadeus Integration | **Complete** (Plan 3/3 done) | DISC-01, DISC-02, DISC-03 |
| 2 - Database Migration | **Complete** (Plan 3/3 done) | DATA-01 through DATA-05 |
| 3 - Anomaly Detection | **Complete** (Plan 3/3 done) | DISC-04 through DISC-07 |
| 4 - Alert State Machine | **Complete** (Plan 2/2 done) | ALRT-01 through ALRT-05 |
| 5 - Freemium Infrastructure | **In Progress** (Plan 1 done) | SUBS-01 through SUBS-05, FRML-01 through FRML-04 |
| 6 - Business/First Class | Pending | BUSN-01 through BUSN-03 |
| 7 - Email Delivery Scale | Pending | MAIL-01 through MAIL-04 |

Progress: █████████░ ~62% (4/7 phases complete, 13/21 plans total)

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
| 2026-01-28 | Turso connection check as separate step with continue-on-error | Fallback-first workflow pattern |
| 2026-01-28 | Validation exit codes: 0=ok, 1=discrepancies, 2=error | CI/CD integration convention |
| 2026-01-28 | Daily validation at 6 AM UTC during migration | Monitors dual-write consistency |
| 2026-01-28 | Custom level shift detection over ADTK | ADTK unmaintained since 2020, Python 3.11+ uncertain |
| 2026-01-28 | 3/14 window ratio for level shift | 3 recent vs 14 baseline observations |
| 2026-01-28 | 40% drop threshold for exceptional deals | Based on mistake fare research |
| 2026-01-28 | Rolling z-score with z < -2.5 for anomaly detection | Bottom ~0.6% of distribution |
| 2026-01-28 | Seasonal multipliers: Dec-Jan +50%, Jun-Aug +25% | Research-backed Detty December and summer adjustments |
| 2026-01-28 | Zero std replaced with NaN in z-score | No z-score for constant prices (insufficient variance) |
| 2026-01-28 | Hybrid detection: level shift -> z-score -> static | Priority order for deal classification |
| 2026-01-28 | classification_method tracked in deal output | Enables observability and future accuracy analysis |
| 2026-01-28 | Two tiers only: Great (free) + WOW (premium) | No "Good" tier - if it's just good, Google Alerts can find it |
| 2026-01-28 | Mistake fares = premium content | Always routes to premium regardless of tier |
| 2026-01-28 | Once per deal window cooldown | Alert once when deal appears, no re-alerts for same tier |
| 2026-01-28 | Escalation overrides cooldown | Great->WOW triggers immediate new alert |
| 2026-01-28 | De-escalation is silent | No alert when price goes back up |
| 2026-01-28 | Reset after 3 consecutive normal prices | Cycle resets, new deal can alert again |
| 2026-01-28 | Tier emoji: * Great, ** WOW, !! Mistake | Text-compatible indicators in email subjects |
| 2026-02-10 | ALERTING states are transient (auto-transition to ALERTED) | FSM self-contained, no external ack needed |
| 2026-02-10 | Unknown deal tiers treated as normal_price | Safe default, logged as warning |
| 2026-02-10 | Reset clears last_alert_tier and last_alert_price_cents | Full cycle reset for fresh alert window |
| 2026-02-10 | Migration runs unconditionally in TursoClient.__init__ | Idempotent via PRAGMA table_info, ensures columns exist |
| 2026-02-10 | FSM is primary alert gate, seen_deals.json maintained as backup | Allows rollback if FSM has issues |
| 2026-02-10 | Normal prices fed to FSM for reset tracking | check_route() calls _alert_fsm.process(None) when no deal |
| 2026-02-10 | Mistake fare detection via level_shift classification_method | 40%+ price drop heuristic from anomaly detection |
| 2026-02-10 | Tier emoji in HTML badge: combines emoji + label | "* Great" or "** WOW" in card badge |
| 2026-02-10 | Column whitelist in update_subscriber prevents SQL injection | Dynamic UPDATE from kwargs needs protection |
| 2026-02-10 | No-preference subscribers get all metros (not error) | metro_group=NULL means subscriber sees everything |
| 2026-02-10 | DEST_REGIONS includes future expansion regions | East/Southern/North Africa with placeholder airports |
| 2026-02-10 | _rows_to_dicts uses PRAGMA table_info for column names | Dynamic column discovery avoids hardcoding |

## Session Continuity

Last session: 2026-02-10
Stopped at: Completed 05-01-PLAN.md (Subscriber Data Foundation)
Resume file: None
Resume command: `/gsd:execute-phase 5` (continue Freemium Infrastructure, next plan 05-02)

---
*Last updated: 2026-02-10 after completing Phase 5 Plan 1 (Subscriber Data Foundation)*
