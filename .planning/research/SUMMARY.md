# Research Summary: Detty Flight Deals Upgrade

**Project:** Detty Flight Deals - Flight Deal Monitoring Service Upgrade
**Synthesized:** 2026-01-27
**Overall Confidence:** MEDIUM-HIGH

---

## Executive Summary

Detty Flight Deals can build a production-grade flight deal monitoring service for the African diaspora within a $50-100/month budget by leveraging a hybrid approach: Amadeus API for priority routes, Google Flights scraping for broad coverage, and statistical anomaly detection for deal classification. The competitive advantage comes not from superior technology (competitors like Going and Secret Flying use similar approaches) but from **focus** - continuous monitoring of 77+ Africa routes that general-purpose services only check sporadically.

The recommended architecture evolves the working MVP from stateless GitHub Actions scripts with JSON files into a multi-frequency monitoring pipeline with persistent state (Turso database), tier-escalation alerts, and freemium subscriber segmentation - all while staying serverless. The critical insight: this is a data pipeline, not a web application. No always-on services needed, keeping costs near zero.

Three critical risks must be addressed immediately: (1) Gmail SMTP will fail hard at 100+ subscribers - switch to transactional email before reaching 50 subscribers, (2) Amadeus Self-Service API excludes Delta, American, British Airways, and all low-cost carriers - keep Google Flights scraping as primary data source, not backup, and (3) false deal alerts from ghost fares and cached prices destroy trust - implement cross-validation between data sources before alerting.

---

## Critical Findings

### From STACK.md: Hybrid Data Strategy Required

**Key decision:** Use Amadeus API for priority routes (6 routes every 2 hours = 2,160 calls/month, fits free tier) AND keep fast-flights Google Flights scraping for broad coverage (remaining 71 routes daily). This is not redundancy - it is necessity. Amadeus Self-Service explicitly excludes Delta, American Airlines, British Airways, and all low-cost carriers. For US-to-Africa routes, these missing carriers often have the best prices.

**Budget validated:** Total infrastructure cost is $0-40/month, well within target:
- Amadeus: $0-15/month (free tier covers priority routes)
- Turso database: $0-5/month (500M reads, 10M writes free)
- Resend email: $0-20/month (3,000 emails free, then $20/50K)
- GitHub Actions: $0/month (public repo = unlimited minutes)
- Supabase subscriber mgmt: $0/month (50K MAU free)

**Rejected alternatives:** SerpAPI ($75/month minimum), Skyscanner API (requires partner approval), Kiwi Tequila (restricted access), full GDS ($100K+/month), self-hosted PostgreSQL (operational burden).

### From FEATURES.md: Deal Detection Is Human + Tools, Not Magic

**Industry reality:** Even Going ($10.8M revenue, ~100 employees) relies on humans using ITA Matrix and Google Flights to find deals, supplemented by automated monitoring. True GDS/ATPCO raw data access costs $100K+/month - prohibitive for deal services. The competitive edge for Detty is **speed** (detect before general services pick it up) and **focus** (77 Africa routes continuously vs. 2-3 Africa deals/month from competitors).

**Conversion insight:** Going's freemium funnel works via FOMO - free users see that deals exist but don't get the best ones. The trigger is "Last week, Premium members saved $800 on JFK-London. Here's what you missed." At $10.8M revenue with ~2M members, roughly 10% convert at $49/year = strong conversion rate. Detty can follow this playbook at lower price point ($4-5/month).

**Differentiators that matter:**
1. **Africa-first coverage** (77 routes vs. competitors' 2-3 Africa deals/month) - THE wedge
2. **Own mistake fare detection** via anomaly-based monitoring (beat RSS blogs by hours)
3. **Detty December early warning** starting March-June (culturally intelligent, no competitor does this)
4. **Business/First class Africa deals** (Going charges $199/year for this; Detty can do $5-10/month)
5. **Pidgin tier names** ("Na Wa!", "E Sweet!", "No Wahala") - cultural identity, not just features

**Anti-features:** No OTA/booking integration (complexity, liability), no price prediction (requires 5+ years of data Detty doesn't have), no mobile app until $10M+ revenue (Going built theirs after 9 years), no points/miles tracking (different product entirely).

### From ARCHITECTURE.md: Serverless Pipeline, Not Always-On Service

**Core pattern:** Data flows one direction: price sources → ingestion → storage → anomaly detection → alert generation → email delivery. Every component is a batch job triggered on schedule. No containers, no message queues, no persistent services except Turso database (accessed via HTTPS).

**Alert state machine (tier-escalation FSM):**
```
NORMAL → GOOD → GREAT → WOW → back to NORMAL resets cycle
```
Rules:
- Enter new tier → ALERT (unless in cooldown)
- Stay in same tier → NO ALERT
- Escalate to better tier → ALERT IMMEDIATELY (overrides cooldown)
- Return to NORMAL for 3 consecutive checks → RESET (next drop alerts again)

This eliminates alert fatigue from $5 price wiggles while capturing meaningful tier transitions.

**Database schema (Turso/SQLite):**
- `price_observations` - append-only history, every price from every source
- `price_cache` - materialized view of current route states (replaces seen_deals.json)
- `alert_state` - FSM state per route (tier, cooldown, reset counter)
- `subscribers` - replaces Google Sheets, adds tier and preferences

**Build order driven by dependencies:**
1. Amadeus integration (adds 2-hour monitoring, no DB changes needed)
2. Database migration (JSON → Turso, enables historical queries)
3. Anomaly detection (requires DB historical data)
4. Alert state machine (requires DB alert_state table)
5. Subscriber segmentation (requires DB subscribers table)
6. Business/First class monitoring (premium feature)
7. Email delivery upgrade (Gmail → SendGrid/Resend at scale)

### From PITFALLS.md: Three Critical Failure Modes

**Pitfall 1 - Amadeus content gap (CRITICAL):** Amadeus Self-Service excludes Delta, American Airlines, British Airways, all LCCs. For US-Africa routes, these carriers often have best prices. Subscribers will see "WOW" alerts for $700 but find $580 on Delta via Google Flights, destroying trust. **Prevention:** Keep fast-flights as primary; Amadeus supplements for cheapest-date-search capability.

**Pitfall 2 - Gmail SMTP hard limit (CRITICAL):** Gmail free accounts limit SMTP to 100 emails/day (not 500 like web interface). At 100+ subscribers, half get no emails. Gmail may suspend account. November 2025 enforcement requires SPF/DKIM/DMARC + one-click unsubscribe. **Prevention:** Switch to transactional email (Resend, SendGrid, SES) before 50 subscribers. Current unsubscribe (mailto:) is non-compliant.

**Pitfall 3 - False alerts from ghost fares (CRITICAL):** Google Flights cache shows prices that disappeared hours ago. Users have reported discrepancies up to $670 between displayed and actual prices. OTA communication lags with airlines cause cache staleness. **Prevention:** Cross-validate between Amadeus and Google Flights before alerting. Only alert if deal seen in 2+ consecutive checks. Add "Price verified as of [timestamp]" disclaimer.

**Moderate risks:**
- Alert fatigue (cap at 3 emails/week for free tier, batch into digests)
- Insufficient historical data for anomaly detection (use static thresholds for 6+ months while collecting data)
- fast-flights scraping breaks (Google updates HTML) - have SerpAPI as backup plan ($75/month)
- Detty December pricing explosion (2-3x normal) - implement seasonal threshold adjustments before December 2026
- Freemium conversion stalls - wait for 200+ subscribers before building freemium infrastructure

---

## Recommended Approach

### Phase Strategy

Build in 7 sequential phases where each phase is independently valuable - stopping after any phase leaves the system better than before.

**Phase 1: Amadeus Integration** (already designed in `docs/plans/2026-01-19-amadeus-continuous-monitoring-design.md`)
- Add Amadeus API for 6 priority routes every 2 hours
- Keep fast-flights for remaining 71 routes daily
- No database changes needed - integrate alongside existing system
- **Value:** 2-hour monitoring on highest-value routes, beat competitors on speed
- **Cost:** $0-15/month (within Amadeus free tier)

**Phase 2: Database Migration (JSON → Turso)**
- Migrate seen_deals.json, price_history.jsonl to Turso SQLite database
- Dual-write for 1 week validation period
- Eliminates git merge conflicts from state files
- **Value:** Enables historical queries, unblocks anomaly detection
- **Cost:** $0/month (free tier: 5GB, 500M reads)

**Phase 3: Anomaly Detection**
- Implement rolling z-score with scipy/numpy
- Use data-driven baselines when 30+ observations exist per route/season
- Fall back to manual thresholds (current approach) when data insufficient
- Add ADTK level shift detection for mistake fare discovery
- **Value:** Data-driven deal classification, own mistake fare detection (beat RSS blogs)
- **Cost:** $0/month (compute only)

**Phase 4: Alert State Machine**
- Implement tier-escalation FSM with cooldown management
- Only alert on tier transitions (Good→Great→WOW), not minor fluctuations
- Price-normalized reset: 3 consecutive "normal" prices resets alert cycle
- **Value:** Eliminates alert fatigue, smarter than competitors' simple "price dropped" logic
- **Cost:** $0/month

**Phase 5: Subscriber Segmentation**
- Migrate Google Sheets → Supabase/Turso subscribers table
- Add tier (free/premium), preferences (origin_region, dest_region)
- Implement preference-based routing in alert_engine
- **Value:** Foundation for freemium model, regional personalization
- **Cost:** $0/month (Supabase free: 50K MAU)

**Phase 6: Business/First Class Monitoring**
- Add fare_class parameter to Amadeus queries (priority routes only)
- Premium-only routing for business/first class deals
- **Value:** Premium differentiator (Going charges $199/year for this)
- **Cost:** +$5-10/month in Amadeus calls

**Phase 7: Email Delivery Upgrade**
- Replace Gmail SMTP with Resend (or SendGrid/SES)
- Implement SPF/DKIM/DMARC, one-click unsubscribe
- **Value:** Scale beyond 100 subscribers, Gmail compliance, delivery analytics
- **Cost:** $0-20/month (3,000 emails free, then $20/50K)

### Technology Stack

**Flight Data (Hybrid):**
- Amadeus Self-Service API (priority routes, cheapest-date-search) - `amadeus` Python SDK
- fast-flights 1.0+ (Google Flights scraping, broad coverage) - keep as primary
- Backup: SerpAPI ($75/month) if scraping becomes unreliable

**Storage:**
- Turso (libSQL) for price history, state, subscribers - `libsql-experimental` Python SDK
- Supabase alternative for subscriber management if auth needed

**Email:**
- Resend (3K free/month, then $20/50K) - `resend` Python SDK
- Alternatives: SendGrid ($20/50K), SES ($0.10/1K at scale)

**Anomaly Detection:**
- scipy/numpy for z-score calculations (rolling 90-day windows)
- ADTK for level shift detection (mistake fares)

**Scheduling:**
- GitHub Actions (free for public repos, unlimited minutes)
- Budget optimization: reduce fast-flights runtime to ~20 min weekday (skip Amadeus-covered routes)

### Patterns to Follow

1. **Source-agnostic ingestion:** Every data source produces same `PriceObservation` dataclass; downstream never knows where price came from
2. **Idempotent pipeline stages:** Re-running any stage is safe (upsert semantics)
3. **Graceful degradation:** Turso unreachable → fall back to JSON; Amadeus fails → rely on daily fast-flights
4. **Cross-validation before alerting:** Never alert on single data source; verify between Amadeus and Google Flights

### Anti-Patterns to Avoid

1. **Always-on server:** No VPS, no containers - stay serverless on GitHub Actions
2. **Event-driven architecture:** No Kafka/RabbitMQ for <100 events per run - overkill
3. **Committing state to git:** Use Turso for mutable state, not git commits
4. **Per-date alert tracking:** Track per-route (JFK-LOS) not per-departure-date (explosion of state)

---

## Risk Matrix

| Risk | Severity | Likelihood | Phase | Mitigation |
|------|----------|-----------|-------|------------|
| **Amadeus missing carriers (Delta/AA/BA)** | HIGH | Certain | Phase 1 | Keep fast-flights as primary; Amadeus supplements only |
| **Gmail SMTP hard limit at 100 subscribers** | HIGH | Certain | Before Phase 5 | Switch to Resend/SendGrid before 50 subs |
| **False alerts from ghost fares** | HIGH | High | Phase 3 | Cross-validate sources; alert only if seen 2+ times |
| **API cost escalation beyond free tier** | HIGH | Medium | Phase 1 expansion | Budget per-call costs; use Cheapest Date Search (1 call/route vs. 26) |
| **fast-flights scraping breaks** | MEDIUM | Medium | Ongoing | Use fetch_mode="fallback"; have SerpAPI backup ($75/mo) |
| **Alert fatigue from over-emailing** | MEDIUM | Medium | Phase 5 | Cap 3 emails/week for free; batch into digests |
| **Insufficient data for anomaly detection** | MEDIUM | Low | Phase 3 | Use static thresholds for 6+ months while collecting history |
| **Detty December threshold mismatch** | MEDIUM | Certain | Before Dec 2026 | Seasonal threshold adjustments (+50% for Dec-Jan) |
| **Freemium conversion <2%** | LOW | Medium | Phase 5+ | Wait for 200+ engaged subscribers before building |
| **GitHub Actions minute limits** | LOW | Low | Future scale | Optimize runtime; buy minutes ($0.008/min overage) if needed |

**Top 3 actions by risk x likelihood:**
1. Switch email delivery from Gmail SMTP now (before subscriber growth)
2. Design Amadeus as supplement to fast-flights, not replacement
3. Build cross-validation step before any alert fires

---

## Build Order

### Phase 1: Amadeus Integration (Weeks 1-2)
**Dependencies:** Amadeus API credentials (signup at developers.amadeus.com)
**Delivers:**
- `amadeus_client.py` - OAuth2 + Cheapest Date Search wrapper
- `amadeus_monitor.py` - Priority route monitoring (6 routes)
- `priority_monitor.yml` - GitHub Actions workflow (every 2 hours)
- Cross-validation logic: verify Amadeus prices against Google Flights before alerting

**Success criteria:**
- 6 priority routes checked every 2 hours
- API call count stays under 2,160/month (free tier)
- Zero alerts sent on Amadeus-only data (must be verified by fast-flights)

**Cost:** $0-15/month

---

### Phase 2: Database Migration (Weeks 3-4)
**Dependencies:** Phase 1 validates multiple write sources work
**Delivers:**
- Turso database setup (5GB free tier)
- Schema: price_observations, price_cache, alert_state, subscribers
- `db.py` module for database access
- Dual-write migration: JSON + Turso for 1 week, then Turso primary
- Google Sheets subscriber export to Turso subscribers table

**Success criteria:**
- All state lives in Turso (no more seen_deals.json commits)
- Historical queries work (SELECT last 90 days for JFK-LOS)
- Zero data loss during migration (validated via dual-write comparison)

**Cost:** $0/month

---

### Phase 3: Anomaly Detection (Weeks 5-6)
**Dependencies:** Phase 2 (needs queryable price history)
**Delivers:**
- `anomaly_detector.py` with rolling z-score calculations
- Hybrid baseline logic: data-driven when 30+ observations exist, manual fallback
- ADTK level shift detection for mistake fare discovery
- Seasonal adjustment factors (Dec-Jan +50%, Jun-Aug +25%)

**Success criteria:**
- Z-score < -2.5 flags deals correctly on routes with historical data
- Manual thresholds still used for new routes (graceful degradation)
- Own mistake fare detection finds at least 1 deal per month not in RSS feeds

**Cost:** $0/month

---

### Phase 4: Alert State Machine (Week 7)
**Dependencies:** Phase 2 (needs alert_state table), Phase 3 (needs scored deals)
**Delivers:**
- `alert_engine.py` with tier-escalation FSM
- Cooldown management (48h for Good, 24h for Great, 12h for WOW)
- Price-normalized reset (3 consecutive normals → reset alert cycle)
- Escalation overrides cooldown (Great→WOW alerts immediately)

**Success criteria:**
- No re-alerts for same-tier price wiggles
- Tier escalations (Good→Great→WOW) fire immediately
- Return to normal resets cycle correctly

**Cost:** $0/month

---

### Phase 5: Freemium Infrastructure (Week 8-9)
**Dependencies:** Phase 2 (subscribers table), 200+ engaged free subscribers
**Delivers:**
- Free tier: Daily digest of Good/Great deals (all routes, economy)
- Premium tier: Instant WOW alerts, mistake fares, business/first class
- Expired deal teasers: "Yesterday, Premium members got $580 JFK-LOS" (FOMO conversion)
- Preference-based routing: origin_region, dest_region filtering

**Success criteria:**
- Free-to-paid conversion rate 2-5%
- Time-to-conversion tracked
- Expired deal teaser sent to free tier daily with yesterday's WOW/mistake deals

**Cost:** $0/month (manual payment via Venmo until 50+ paying subscribers)

---

### Phase 6: Business/First Class (Week 10)
**Dependencies:** Phase 1 (Amadeus supports cabin class), Phase 5 (premium routing)
**Delivers:**
- `fare_class` parameter in Amadeus monitoring (priority routes only)
- Premium-only routing for business/first class deals
- Separate thresholds for business class (40-50% below baseline vs. 30% for economy)

**Success criteria:**
- Business class deals found 2-4x/month on priority routes
- Only premium subscribers receive business/first class alerts

**Cost:** +$5-10/month (additional Amadeus calls)

---

### Phase 7: Email Delivery Scale (Week 11)
**Dependencies:** Phase 5 (subscriber count approaching 100)
**Delivers:**
- Resend integration replacing Gmail SMTP
- SPF/DKIM/DMARC setup for dettyflightdeals.com
- One-click unsubscribe (List-Unsubscribe header)
- Delivery tracking and analytics

**Success criteria:**
- Send to 200+ subscribers without failures
- Deliverability rate >95%
- Spam complaint rate <0.1%

**Cost:** $0-20/month (3K emails free, then $20/50K)

---

## Cost Projection

### MVP (Current)
**Monthly:** $0
- GitHub Actions: Free (public repo)
- Gmail SMTP: Free (under 100/day)
- Google Sheets: Free
- fast-flights: Free

**Limitations:** Cannot scale beyond 100 subscribers, no anomaly detection, daily-only monitoring

---

### Phase 1-2: Amadeus + Database (Target: Q1 2026)
**Monthly:** $0-20
- Amadeus: $0-15 (free tier covers 6 priority routes)
- Turso: $0-5 (free tier likely sufficient)
- GitHub Actions: $0
- Gmail SMTP: $0
- fast-flights: $0

**Capabilities:** 2-hour priority monitoring, historical data collection, up to 100 subscribers

---

### Phase 3-5: Anomaly Detection + Freemium (Target: Q2 2026)
**Monthly:** $0-25
- Amadeus: $0-15
- Turso: $0-5
- Resend: $0 (free tier covers <750 subscribers at 4 emails/month)
- GitHub Actions: $0
- fast-flights: $0

**Capabilities:** Own mistake fare detection, freemium conversion funnel, regional preferences, up to 750 subscribers

---

### Phase 6-7: Premium Features + Scale (Target: Q3 2026)
**Monthly:** $5-45
- Amadeus: $5-25 (business class monitoring + expanded routes)
- Turso: $0-5
- Resend: $0-20 (Pro plan if >750 subscribers)
- GitHub Actions: $0
- fast-flights: $0

**Capabilities:** Business/first class deals, 1,000+ subscribers, delivery analytics

---

### Scale Milestones

| Subscribers | Monthly Cost | Revenue (5% convert @ $5/mo) | Margin |
|-------------|-------------|------------------------------|--------|
| 200 | $0-25 | $50 | +$25-50 |
| 500 | $0-30 | $125 | +$95-125 |
| 1,000 | $20-45 | $250 | +$205-230 |
| 5,000 | $40-80 | $1,250 | +$1,170-1,210 |

**Healthy margins at every scale.** The architecture stays within budget through Phase 7 and beyond.

---

## Confidence Assessment

| Area | Confidence | Source Quality | Gaps |
|------|------------|----------------|------|
| **Technology stack** | HIGH | Verified via official Amadeus/Turso/Resend pricing pages; community validation on fast-flights | Exact Amadeus free tier quota per API requires login (claimed 2K/month is plausible but unconfirmed) |
| **Architecture approach** | HIGH | Brownfield evolution of working MVP; serverless pipeline pattern well-understood | Turso Python SDK maturity (relatively new, needs testing in GitHub Actions) |
| **Feature strategy** | MEDIUM-HIGH | Competitor analysis via official sites + independent reviews; freemium benchmarks from Lenny's Newsletter | Going/Secret Flying internal deal detection methods are proprietary (inferred from public statements) |
| **Domain pitfalls** | MEDIUM-HIGH | Gmail limits, Amadeus gaps confirmed in official docs; ghost fares documented by multiple sources | fast-flights reliability over 12+ months (library is newer, less battle-tested) |

**Overall confidence: MEDIUM-HIGH**

Most critical decisions (Amadeus as supplement not primary, Gmail SMTP must be replaced, cross-validation required) are backed by official documentation or well-documented industry patterns. The main uncertainties are operational (how often will fast-flights break? what's the actual Amadeus per-call cost in production?) rather than architectural.

---

## Open Questions

These require validation during implementation:

1. **Amadeus test vs. production pricing:** Design doc claims test environment returns "real prices" within 2,000 call/month quota. Need to validate whether test prices are accurate enough for baseline calculations or if production upgrade is required earlier than expected.

2. **fast-flights reliability at scale:** Library is newer and scraping-based. If Google tightens anti-scraping (CAPTCHA, IP blocking), what is the actual failure rate? SerpAPI backup ($75/month) is budgeted but triggers cost increase.

3. **Turso connection handling in GitHub Actions:** Ephemeral runners mean new connections per workflow run. Does the `libsql` Python SDK handle connection pooling, retries, timeouts correctly in this environment?

4. **Cross-validation threshold:** What percentage agreement between Amadeus and Google Flights is acceptable? If Amadeus shows $700 and fast-flights shows $730, is that close enough to alert (4% difference) or is it a data quality issue?

5. **Seasonal threshold adjustment magnitude:** Research suggests +50% for Detty December, +25% for summer peak. Are these percentages correct for all routes or do Lagos/Accra need different adjustments than Addis Ababa/Nairobi?

6. **Freemium conversion rate for diaspora audience:** General newsletter benchmarks are 2-5%. African diaspora travelers are deal-seeking by nature (why they want this service) - does this increase or decrease willingness to pay $5/month for better deals?

7. **Business class demand:** How many diaspora travelers actually fly business/first class? Is this a 5% niche or 20% of the addressable market? Determines priority of Phase 6.

---

## Research Flags

### Phases that NEED additional research:

**Phase 5 (Freemium Launch):**
- `/gsd:research-phase` on "freemium conversion optimization for price-sensitive audiences"
- Need: Pricing psychology, trial period duration, conversion triggers beyond FOMO
- Reason: Generic freemium playbooks may not translate to diaspora traveler behavior

**Phase 6 (Business Class):**
- `/gsd:research-phase` on "business class pricing dynamics for Africa routes"
- Need: Separate threshold definitions, demand validation, routing strategy
- Reason: Business class is a different product with different buyers and pricing patterns

### Phases with STANDARD patterns (skip research):

**Phase 1 (Amadeus Integration):** Already designed in detail in `docs/plans/2026-01-19-amadeus-continuous-monitoring-design.md`

**Phase 2 (Database Migration):** Standard JSONL → SQLite migration, well-documented pattern

**Phase 3 (Anomaly Detection):** Statistical methods (z-score, percentile) are textbook; seasonal adjustment is domain-specific but researched in PITFALLS.md

**Phase 4 (Alert State Machine):** Finite state machine pattern is standard CS; tier-escalation logic is unique but fully specified

**Phase 7 (Email Delivery):** Transactional email integration is commodity; SPF/DKIM/DMARC setup is documented

---

## Sources

### Technology Stack
- [Amadeus Self-Service Pricing](https://developers.amadeus.com/pricing)
- [Amadeus API Rate Limits](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/api-rate-limits/)
- [Amadeus Flight Cheapest Date Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search)
- [Turso Pricing](https://turso.tech/pricing)
- [Resend Pricing](https://resend.com/pricing)
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage)
- [Supabase Pricing](https://supabase.com/)
- [fast-flights on PyPI](https://pypi.org/project/fast-flights/)
- [SerpAPI Pricing](https://serpapi.com/pricing)

### Competitive Landscape
- [Going.com Membership Guide](https://www.going.com/guides/membership-guide)
- [Going Revenue Data](https://getlatka.com/companies/app.going.com)
- [Secret Flying Wikipedia](https://en.wikipedia.org/wiki/Secret_Flying)
- [Hopper Statistics](https://www.businessofapps.com/data/hopper-statistics/)
- [Thrifty Traveler 2025 Wrapped](https://thriftytraveler.com/deals/flights/year-in-flight-deals/)
- [Matt's Flights Review](https://www.pilotplans.com/blog/matts-flights-review)

### Domain Pitfalls
- [Gmail Sending Limits](https://support.google.com/mail/answer/22839?hl=en)
- [Gmail November 2025 Enforcement](https://www.proofpoint.com/us/blog/email-and-cloud-threats/clock-ticking-stricter-email-authentication-enforcements-google-start)
- [Google Flights Price Discrepancies](https://www.mightytravels.com/2024/11/google-flights-price-discrepancies-7-common-booking-issues-and-their-technical-causes/)
- [Detty December CNN Coverage](https://edition.cnn.com/2025/12/19/travel/detty-december-nigeria-party-problems)
- [Nigeria Airfare Analysis](https://businessday.ng/aviation/article/explainer-why-airfares-from-nigeria-are-higher-than-african-peers/)
- [Freemium Conversion Benchmarks](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)

### Architecture Patterns
- [Turso Python SDK](https://docs.turso.tech/sdk/python/quickstart)
- [ADTK Documentation](https://adtk.readthedocs.io/en/stable/)
- [SciPy zscore](https://pythonguides.com/scipy-stats-zscore/)
- [GitHub Actions Database Persistence](https://github.com/karlhorky/github-actions-database-persistence)

---

## Ready for Requirements

SUMMARY.md synthesized. The orchestrator can proceed to requirements definition with:

**Clear technology decisions:** Hybrid Amadeus + fast-flights, Turso database, Resend email, GitHub Actions scheduling

**Validated architecture:** Serverless pipeline with tier-escalation FSM, cross-validation, graceful degradation

**Sequenced roadmap:** 7 phases from Amadeus integration through email scale, each independently valuable

**Known risks:** Gmail SMTP limit, Amadeus carrier gaps, false alerts from ghost fares - all with documented mitigations

**Budget confidence:** $0-45/month through Phase 7, healthy margins at every subscriber count

All research files committed (next step).
