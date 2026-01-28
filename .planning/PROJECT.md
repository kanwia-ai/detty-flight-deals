# Detty Flight Deals

## What This Is

A freemium flight deal alert service for the African diaspora. Monitors flight prices from US cities to African destinations and sends email alerts when deals hit — tiered by how good the deal is. Think Scott's Cheap Flights, but built specifically for routes to Africa that existing services ignore.

"Detty" is Nigerian slang for exciting/lit. "Detty December" is when the diaspora floods Lagos for the holidays.

## Core Value

**Find genuinely great flight deals to Africa before anyone else — and make them actionable.** If a $650 JFK→Lagos fare appears at 2am, subscribers should know about it before it shows up on Secret Flying.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ Deal finder searches 77 routes (7 US origins × 11 West/Central African destinations) — existing
- ✓ Three-tier deal classification: Good (20-30% off), Great (35-50% off), WOW (50%+ off) — existing
- ✓ Mistake fare RSS monitoring from deal blogs (Secret Flying, The Flight Deal, Fly4Free, etc.) — existing
- ✓ HTML email alerts with Pan-African branding, grouped by tier then destination — existing
- ✓ Email delivery via Google Sheets subscriber list + Gmail SMTP — existing
- ✓ Landing page with signup flow (Google Forms → Sheets → Apps Script welcome email) — existing
- ✓ Deal deduplication to prevent repeated alerts — existing
- ✓ Price history logging to `price_history.jsonl` for future ML — existing
- ✓ GitHub Actions automation (deal finder daily, mistake fares every 30 min) — existing

### Active

<!-- Current scope. Building toward these. -->

**Deal Discovery (the core problem)**
- [ ] Higher-frequency monitoring for priority routes (beat deal blogs, not just daily scans)
- [ ] Full date-range scanning — find the actual cheapest dates, not sample specific weeks
- [ ] Anomaly detection — recognize when a fare is unusually cheap based on historical baselines
- [ ] Own mistake fare discovery — detect pricing errors from price data, not just RSS feeds
- [ ] Business/First class deal monitoring on the same route set

**Alert Intelligence**
- [ ] Tier-escalation alerts: notify on Good→Great→WOW transitions, not $5 price wiggles
- [ ] Price-normalized cycle: reset alert cycle when price returns to normal range
- [ ] Cooldown after WOW alert — don't re-alert until price returns to normal then drops again

**Freemium Model**
- [ ] Free tier: Good + Great economy deals, all routes, no customization
- [ ] Premium tier: WOW + Mistake fares, business/first class, regional personalization
- [ ] Expired deal teasers for free users — show what premium subscribers got last week
- [ ] Regional origin preferences (New England, Mid-Atlantic, South/Texas, Atlanta)
- [ ] Regional destination preferences (West, East, North, Southern Africa)
- [ ] 1-week free trial of premium

**Infrastructure**
- [ ] Move off Google Sheets for subscriber management (scale beyond 200)
- [ ] Proper price history database for baseline calculation
- [ ] Cost-optimized monitoring pipeline within $50-100/month budget

### Out of Scope

- **Web app for browsing deals** — email-first; web comes in a future version
- **Credit card points/miles deals** — interesting but classes/cabins more important first
- **Granular airport-level destination selection** — start with regional (West/East/North/South Africa), go granular later
- **UK/EU origins** — US-only for v1
- **Hotels or trip planning** — this is flights only
- **Mobile app** — email + responsive landing page is sufficient
- **North/East/Southern Africa destinations** — start with West/Central (Tier 1), expand later
- **Automated payment/billing** — beta is free or $5 manually collected; proper billing comes later

## Context

**Existing system**: Working MVP on GitHub Actions (free tier). Python scripts using `fast-flights` (Google Flights scraper) for daily route scanning and `feedparser` for RSS mistake fare monitoring. Email via Gmail SMTP to Google Sheets subscriber list. Landing page is static HTML.

**The deal quality gap**: Current search samples one departure week at a time across 26 weeks. This misses the actual cheapest dates. Services like Scott's/Going use fare filing databases (ITA Matrix, GDS access) to see when fares are *published* at unusual prices — fundamentally different from spot-checking.

**Subscriber base**: 4 early subscribers (all willing to pay). Pre-launch — building quality before public sharing.

**Market**: 28M+ Africans in US/UK/EU. ~5.6M diaspora trips annually at ~$1,500 average = $8.4B+ in airfare. No existing service is Africa-first.

**Detty December**: Peak season when diaspora returns home. Prices 20-30% higher. Best booking window: 90-240 days out. This is the wedge for premium conversion.

**Competitive landscape**: Going/Scott's publishes 2-3 Africa deals per month (afterthought). Secret Flying covers Africa occasionally. Nobody monitors 77+ Africa routes continuously.

**Origins covered**: JFK, EWR, IAD, ATL, DFW, IAH, BOS

**Destinations covered (Tier 1 — West/Central Africa)**: Lagos (LOS), Abuja (ABV), Accra (ACC), Dakar (DSS), Freetown (FNA), Abidjan (ABJ), Lome (LFW), Cotonou (COO), Douala (DLA), Yaounde (NSI), Kinshasa (FIH)

**Planned expansion**:
- Tier 2: East Africa (Nairobi, Addis Ababa, Dar es Salaam, Kampala, Kigali)
- Tier 3: Southern Africa (Johannesburg, Cape Town, Harare, Lusaka)
- Tier 4: North Africa (Cairo, Casablanca, Marrakech, Tunis)

## Constraints

- **Budget**: $50-100/month for infrastructure — must be cost-optimized. Currently $0/month (all free tiers).
- **Platform**: GitHub Actions for automation (2,000 free minutes/month). May need to supplement or move.
- **Data source**: `fast-flights` scrapes Google Flights but samples specific dates. Need broader fare visibility without breaking the budget.
- **Email delivery**: Gmail SMTP caps at ~500/day. Google Sheets caps at ~200 subscribers. Both need upgrading for beta.
- **Amadeus API**: Free tier = 2,000 calls/month. Useful for priority routes but not enough for full coverage.
- **Launch timing**: Want to run beta with ~200 people for ~3 months before going freemium. No hard deadline but building toward this.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Email-first, web later | Fastest path to value; deals are time-sensitive and email is push | — Pending |
| Free = Good/Great, Premium = WOW/Mistake/Business | Gives free users real value while reserving best deals for paid | — Pending |
| $5/month starting price | Covers infrastructure; low barrier during beta | — Pending |
| Regional personalization before airport-level | Simpler to implement, still useful for most users | — Pending |
| West/Central Africa first, expand later | Where diaspora demand is highest (Nigeria, Ghana) | ✓ Good |
| Tier-escalation alert model | Prevents alert fatigue while catching all meaningful price movements | — Pending |
| $50-100/month infrastructure budget | Enables real monitoring tools while staying lean pre-revenue | — Pending |

---
*Last updated: 2026-01-27 after initialization*
