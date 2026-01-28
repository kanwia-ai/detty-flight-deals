# Phase 3: Anomaly Detection - Context

**Gathered:** 2026-01-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace manual percentage thresholds with data-driven baselines to discover exceptional deals. Includes z-score anomaly detection, seasonal adjustments, cold start handling, and sudden price drop detection. Route expansion (monitoring more routes) is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Threshold Sensitivity
- Use balanced z-score threshold: z < -2.5
- Recalculate baselines **weekly** (user believes prices won't move that much day-to-day)

### Seasonal Adjustments
- **Research-first approach** — Don't use arbitrary Dec-Jan +50%, Jun-Aug +25% multipliers
- Research needed: actual price seasonality patterns for Africa routes, diaspora travel events beyond Detty December
- Tier downgrades from seasonal adjustments: **no explanation** in emails (just show the tier)

### Cold Start Handling
- New routes get **2-week silent monitoring period** before alerting (avoid false positives from bad baseline)
- Static threshold values: **research competitor thresholds** (Going, Secret Flying) rather than guessing

### Exceptional Deal Detection
- Renamed from "mistake fare" — single "Exceptional Deal" category
- Framing: "This price may not last — book now if interested" (covers both mistake fares and just great deals)
- **Urgent formatting** in emails for exceptional deals
- During beta: free for everyone. After beta: premium-only
- Run detection on **all monitored routes** (not just priority) — effectiveness depends on data density
- Route-dependent absolute thresholds: **research typical bottom prices** per route

### Claude's Discretion
- Tiered z-score thresholds (single vs. Good/Great/WOW separate thresholds)
- High-volatility route handling (tighter thresholds or same)
- Reference price for static thresholds (median vs. mean)
- Cross-route learning for cold start (JFK-LOS informing EWR-LOS)
- ADTK level shift sensitivity tuning
- Exceptional deal detection frequency (30 min vs. hourly)
- Cross-validation failure handling for unverified deals

</decisions>

<specifics>
## Specific Ideas

- User example: "If I saw a random $200 flight to Libreville I'd take it" — exceptional deals matter on any route, not just priority routes
- The distinction that matters: incredible deals vs. true mistake fares (pricing errors that might not be honored). User doesn't care about the distinction — just wants to know about exceptional prices.
- Threshold intuition: "If JFK-LOS is usually $900-1200 and suddenly it's $500, that's exceptional regardless of how we got there"
- ADTK doesn't need 90 days of history — yesterday $1000, today $200 only needs recent data to flag

</specifics>

<research_required>
## Research Tasks for Phase Researcher

These questions must be answered before planning:

1. **Seasonality patterns** — What are actual price patterns by month for Africa routes? When do prices spike and by how much? Is it uniform across destinations or destination-specific?

2. **Diaspora travel events** — Beyond Detty December (Dec-Jan), what events drive diaspora travel? Easter? Independence Day celebrations? Wedding seasons? Summer vacations?

3. **Competitor thresholds** — What does Going/Secret Flying consider a "good" vs "great" vs "wow" deal? What percentage off baseline?

4. **Typical bottom prices** — What are historical lows for each major route? What absolute price triggers "exceptional" status? (May vary: Lagos vs. Kenya vs. South Africa)

5. **Mistake fare definition** — How does the industry distinguish mistake fares from flash sales? What signals indicate a pricing error vs. intentional sale?

</research_required>

<deferred>
## Deferred Ideas

- **Route expansion** — Monitoring every US city to every African international airport. Currently limited to 77 routes due to free tier constraints. Could be its own phase or Phase 1 extension.

</deferred>

---

*Phase: 03-anomaly-detection*
*Context gathered: 2026-01-28*
