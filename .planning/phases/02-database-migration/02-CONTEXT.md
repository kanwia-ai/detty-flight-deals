# Phase 2: Database Migration - Context

**Gathered:** 2026-01-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace JSON files (seen_deals.json, price_history.jsonl) with Turso database for price storage, cache lookups, and alert state persistence. Enables historical queries for Phase 3 anomaly detection and eliminates git merge conflicts from concurrent workflow runs.

**Out of scope:** Subscriber migration (stays in Google Sheets until Phase 5), anomaly detection logic (Phase 3), alert routing (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Schema Design
- **price_observations** table: append-only, stores every price check (route, date_checked, travel_date, price, source, cabin_class, tier_at_time)
- **price_cache** materialized view: current lowest price per route (replaces seen_deals.json lookups)
- **alert_state** table: FSM state per route (current_tier, cooldown_expiry, consecutive_normal_count)
- Indexes on: (route, date_checked), (route, travel_date) for efficient historical queries
- Use SQLite-compatible types (Turso is libSQL): TEXT for routes, INTEGER for prices (cents), TEXT for ISO timestamps

### Migration Strategy
- **Dual-write period: 1 week** — both JSON and Turso receive writes, JSON remains source of truth
- Validation: compare JSON vs Turso state daily, log discrepancies
- Cutover criteria: zero discrepancies for 3 consecutive days
- Post-cutover: JSON files become read-only backup (not deleted), git commits stop

### Fallback Behavior
- If Turso unreachable: fall back to JSON silently, log failure, continue monitoring
- Partial failure handling: if write fails mid-batch, retry 3x then fall back
- Cache staleness: price_cache view refreshed on each write (not scheduled)
- Rationale: monitoring continuity > database consistency for a flight deals service

### Data Retention
- **Append-only, forever** — no automatic pruning
- Turso free tier (5GB) handles ~2+ years of observations at current route/frequency
- All historical data needed for Phase 3 anomaly detection baselines

### Subscriber Storage
- **Keep Google Sheets primary** for subscribers until Phase 5
- Phase 2 creates empty subscribers table schema (ready for Phase 5 migration)
- No sync between Sheets and Turso in this phase

### Claude's Discretion
- Connection pooling strategy (if any for serverless)
- Exact retry timing and backoff
- Logging verbosity levels
- Migration script execution approach (one-time vs idempotent)

</decisions>

<specifics>
## Specific Ideas

- Turso selected for: SQLite compatibility, serverless-friendly HTTPS access, generous free tier (5GB, 500M reads)
- libSQL means standard SQLite tooling works locally for testing
- No persistent connections needed — fits GitHub Actions ephemeral environment

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-database-migration*
*Context gathered: 2026-01-28*
