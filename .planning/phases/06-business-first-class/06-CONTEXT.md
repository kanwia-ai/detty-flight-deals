# Phase 6: Business/First Class Monitoring - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Add premium cabin fare monitoring (Business, First, Premium Economy) on the 6 priority routes via Amadeus cabin class parameter. All premium cabin deals route exclusively to premium subscribers. Economy monitoring is unchanged.

</domain>

<decisions>
## Implementation Decisions

### Cabin class scope
- Monitor three premium cabin classes: Business, First, Premium Economy
- All three are premium-only content (no free tier access)
- Priority routes only (JFK-LOS, EWR-ACC, ATL-LOS, IAD-ACC, DFW-LOS, IAH-ACC) via Amadeus
- Start with 6 routes, expand later based on demand and API budget
- Daily routes (fast-flights) do NOT get premium cabin monitoring in this phase

### Tier thresholds
- Single tier for premium cabins — no Great/WOW distinction. Any deal meeting threshold = a deal
- Different thresholds per cabin class (Claude's discretion on exact percentages based on typical pricing patterns)
- Longer silent monitoring period (4+ weeks) before premium cabin alerts fire — build reliable baselines first
- Static thresholds as fallback during cold start, then z-score when enough data accumulates

### Mistake fare detection
- Claude's discretion on threshold for premium cabin mistake fares
- Mistake fare logic applies to premium cabins (level shift detection)

### Alert presentation
- Treat premium cabin deals like mistake fares: rare, high-value, each gets its own dedicated instant alert
- Email + SMS for premium subscribers with phone numbers (same urgency treatment as mistake fares)
- No batching or digesting of premium cabin deals

### Monitoring cadence & API budget
- Less frequent than economy: every 4-6 hours (not every 2 hours)
- $25/month hard budget cap for premium cabin API calls — stop checks when budget hit, resume next month
- Separate from economy monitoring schedule (different cadence)

### Claude's Discretion
- Exact percentage thresholds per cabin class (Premium Economy, Business, First)
- Mistake fare detection thresholds for premium cabins
- Whether to use separate GitHub Actions workflow or add to existing priority monitor
- Whether to use a feature flag for toggling premium cabin monitoring
- Premium cabin deal alert card design (cabin class badge, price comparison, etc.)
- Whether premium cabin deals appear as FOMO teasers in free tier weekly digest
- Silent monitoring period length (4+ weeks minimum, Claude decides exact duration)

</decisions>

<specifics>
## Specific Ideas

- "Treat them like mistake fares" — user expects premium cabin deals to be rare, high-value events deserving instant dedicated alerts with SMS
- Points/miles monitoring is of interest but deferred to a future phase
- User chose $25/month budget cap — conservative approach, expand if ROI justified
- "Fewer of them" — user expects low deal volume for premium cabins, which informed the single-tier decision

</specifics>

<deferred>
## Deferred Ideas

- Points/miles deal monitoring — user explicitly interested, belongs in its own phase
- Expanding premium cabin monitoring to all 77 routes (via fast-flights or Amadeus) — revisit based on demand and budget
- Premium cabin monitoring on daily routes (fast-flights) — could add later without Amadeus cost

</deferred>

---

*Phase: 06-business-first-class*
*Context gathered: 2026-02-10*
