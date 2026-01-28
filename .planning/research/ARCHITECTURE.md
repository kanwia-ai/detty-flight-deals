# Architecture: Flight Deal Monitoring Pipeline

**Domain:** Flight price monitoring and deal alerting for African diaspora
**Researched:** 2026-01-27
**Overall confidence:** HIGH (brownfield evolution of working MVP with well-understood constraints)

---

## Executive Summary

Detty Flight Deals has a working MVP built as stateless Python scripts on GitHub Actions with JSON file-based state committed to the repo. The target architecture evolves this into a multi-frequency monitoring pipeline with anomaly detection, tier-escalation alerts, and freemium subscriber segmentation -- all within a $50-100/month budget.

The core insight driving this architecture: **the system is a data pipeline, not a web application.** There is no user-facing server. Data flows one direction: price sources --> ingestion --> storage --> anomaly detection --> alert generation --> email delivery. Every component is a batch job triggered on a schedule. This means the architecture can stay simple -- no containers, no always-on services, no message queues. GitHub Actions remains the orchestrator; what changes is where state lives and how intelligence is applied.

---

## Current Architecture (As-Is)

```
                    GitHub Actions (cron)
                    ____________________
                   |                    |
    Daily @ 10 UTC |   find_deals.yml   |  Every 30 min
                   |                    |  mistake_fares.yml
                   |____________________|
                          |    |
                __________|    |__________
               |                          |
        deal_finder.py           mistake_fare_monitor.py
        (fast-flights)           (RSS feeds)
               |                          |
               |   77 routes x 26 wks     |   5 RSS feeds
               |   ~2,000 searches        |   ~100 entries
               |__________________________|
                          |
                    mvp0_sender.py
                    (Gmail SMTP)
                          |
                  Google Sheets
                  (subscriber list)
                          |
                  Email to ~4 users

State files (committed to repo):
  - seen_deals.json         (~12 entries, deal dedup)
  - seen_mistake_fares.json (~0 entries, RSS dedup)
  - price_history.jsonl     (append-only, gitignored)
```

### Current Strengths
- Zero cost ($0/month)
- Works end-to-end (deals found, emails sent)
- Simple to understand and debug
- Price history already being collected

### Current Limitations
- **Speed**: Daily scan means deals found 12-24 hours late
- **State fragility**: JSON committed to repo causes merge conflicts on concurrent runs
- **No anomaly detection**: Fixed thresholds, no historical baseline comparison
- **No tier-escalation logic**: Alerts on first tier entry, but no Good-->Great-->WOW transitions
- **Subscriber cap**: Gmail SMTP at ~500/day, Google Sheets at 200 subscribers
- **Single fare class**: Economy only
- **No subscriber segmentation**: Everyone gets everything

---

## Target Architecture (To-Be)

```
                       GitHub Actions (cron orchestrator)
                    _________________________________________
                   |                                         |
    Every 2 hrs    |  priority_monitor.yml                   | Daily
    (6 routes)     |  (Amadeus priority)                     | find_deals.yml
                   |                                         | (fast-flights full scan)
    Every 30 min   |  mistake_fares.yml                      |
    (RSS feeds)    |  (RSS monitor)                          |
                   |_________________________________________|
                          |            |            |
                   amadeus_monitor  deal_finder  mistake_fare_monitor
                          |            |            |
                          |____________|____________|
                                    |
                            price_tracker.py
                            (compare, classify, log)
                                    |
                        +-----------+-----------+
                        |                       |
                   Turso DB                price_history
                   (price_cache,           (Turso: long-term
                    alert_state,            price records)
                    subscribers)
                        |
                  anomaly_detector.py
                  (baseline calc,
                   z-score / percentile)
                        |
                  alert_engine.py
                  (tier-escalation FSM,
                   subscriber routing,
                   cooldown management)
                        |
                  email_sender.py
                  (Gmail SMTP or
                   SendGrid at scale)
                        |
                  Subscribers
                  (free + premium)
```

---

## Component Boundaries

| Component | Responsibility | Inputs | Outputs | Communicates With |
|-----------|---------------|--------|---------|-------------------|
| **amadeus_monitor.py** | Fetch prices for 6 priority routes via Amadeus API | Amadeus API credentials, route config | Price observations (origin, dest, date, price, source) | price_tracker |
| **deal_finder.py** (existing) | Fetch prices for all 77 routes via fast-flights | Route config | Price observations | price_tracker |
| **mistake_fare_monitor.py** (existing) | Scan RSS feeds for mistake fares | RSS feed URLs | Mistake fare alerts (dest, price, URL, source) | alert_engine (direct, bypasses anomaly detection) |
| **price_tracker.py** | Accept price observations, store to DB, compare with cache | Price observations from any source | Price change events (route, old_price, new_price, tier) | Turso DB, anomaly_detector |
| **anomaly_detector.py** | Compute baselines, score prices against historical data | Price change events, historical price data from DB | Scored deals with confidence (price, baseline, z_score, percentile, tier) | Turso DB |
| **alert_engine.py** | Tier-escalation FSM, subscriber routing, cooldown | Scored deals, alert state from DB, subscriber list | Alert decisions (who gets what) | Turso DB, email_sender |
| **email_sender.py** (evolved from mvp0_sender.py) | Send emails to subscribers | Alert decisions, subscriber preferences | Sent emails | Gmail SMTP / SendGrid |
| **Turso DB** | Persistent state for everything | All components | All components | -- |

### Why These Boundaries

1. **price_tracker is source-agnostic**: It does not care if a price came from Amadeus, fast-flights, or a future SerpApi integration. This decouples data sources from intelligence.

2. **anomaly_detector is separate from alert_engine**: Detection ("is this price unusual?") is a different concern from alerting ("should we tell someone?"). Detection is stateless math. Alerting is stateful (cooldowns, escalation history, subscriber preferences).

3. **mistake_fare_monitor bypasses anomaly detection**: Mistake fares are already classified by the RSS source. They go directly to the alert engine with tier="mistake". No baseline needed.

4. **email_sender is just a delivery channel**: It takes "send this content to these people" instructions. It does not decide who gets what. This makes it easy to add SMS/push later.

---

## Data Flow

### Primary Flow: Price Check --> Alert

```
1. INGEST
   GitHub Actions triggers amadeus_monitor.py or deal_finder.py
   Script fetches prices from external source
   Each price observation: (origin, dest, travel_date, price, source, timestamp)

2. STORE + COMPARE
   price_tracker.py receives observation
   Writes to price_history table (append-only, all observations)
   Compares against price_cache (last known price for this route/date)
   If price changed: emits price_change_event
   Updates price_cache with new price

3. DETECT ANOMALY
   anomaly_detector.py receives price_change_event
   Queries price_history for this route's historical prices
   Calculates baseline (seasonal median from 30+ observations)
   Scores the price: percent_below_baseline, z_score
   Classifies tier: Normal / Good / Great / WOW
   If tier >= Good: emits scored_deal

4. DECIDE ALERT
   alert_engine.py receives scored_deal
   Checks alert_state: was this route/tier already alerted?
   Applies tier-escalation logic (see FSM below)
   Checks cooldown timers
   Routes deal to appropriate subscriber segments
   If alert warranted: emits alert_decision

5. DELIVER
   email_sender.py receives alert_decision
   Queries subscriber list (with preferences, tier)
   Builds HTML email (reuses existing template logic)
   Sends via Gmail SMTP (or SendGrid at scale)
   Logs delivery result
```

### Secondary Flow: Mistake Fare

```
1. mistake_fare_monitor.py scans RSS feeds
2. Finds Africa deal with explicit "mistake fare" label
3. Creates alert with tier="mistake", bypasses anomaly detection
4. Goes directly to alert_engine.py
5. alert_engine routes to premium subscribers only (or all, during beta)
6. email_sender delivers immediately
```

### Tertiary Flow: Baseline Learning

```
1. Every price observation is stored in price_history (step 2 above)
2. No immediate action -- this is background data collection
3. anomaly_detector queries this data during step 3
4. Over time, baselines become data-driven (replace manual thresholds)
5. For routes with <30 observations: fall back to manual seasonal baselines
```

---

## Data Model (Turso / SQLite)

### Tables

```sql
-- Every price observation from any source
CREATE TABLE price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    origin TEXT NOT NULL,           -- "JFK"
    destination TEXT NOT NULL,      -- "LOS"
    travel_date DATE NOT NULL,
    return_date DATE,
    price_cents INTEGER NOT NULL,   -- Store in cents to avoid float issues
    fare_class TEXT DEFAULT 'economy', -- 'economy', 'business', 'first'
    source TEXT NOT NULL,           -- 'fast_flights', 'amadeus', 'serpapi'
    days_until_travel INTEGER,
    season TEXT                     -- 'off_peak', 'jul_peak', 'dec_peak'
);

CREATE INDEX idx_route_date ON price_observations(origin, destination, travel_date);
CREATE INDEX idx_route_season ON price_observations(origin, destination, season);

-- Last known price per route (cache for fast comparison)
CREATE TABLE price_cache (
    route_key TEXT PRIMARY KEY,     -- "JFK-LOS:economy"
    last_price_cents INTEGER,
    last_tier TEXT,                 -- 'normal', 'good', 'great', 'wow'
    last_checked_at TIMESTAMP,
    last_alerted_at TIMESTAMP,
    last_alerted_tier TEXT
);

-- Alert state machine per route
CREATE TABLE alert_state (
    route_key TEXT PRIMARY KEY,     -- "JFK-LOS:economy"
    current_tier TEXT DEFAULT 'normal',
    tier_entered_at TIMESTAMP,
    last_alert_sent_at TIMESTAMP,
    last_alert_tier TEXT,
    cooldown_until TIMESTAMP,       -- No re-alert until this time
    consecutive_normal_count INTEGER DEFAULT 0  -- For reset detection
);

-- Subscribers with preferences
CREATE TABLE subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    tier TEXT DEFAULT 'free',       -- 'free', 'premium'
    status TEXT DEFAULT 'active',   -- 'active', 'unsubscribed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Preferences (nullable = "all")
    origin_region TEXT,             -- 'northeast', 'southeast', 'south', 'all'
    dest_region TEXT,               -- 'west_africa', 'east_africa', 'all'
    fare_classes TEXT DEFAULT 'economy', -- comma-separated: 'economy,business'
    -- Engagement tracking
    last_email_sent_at TIMESTAMP,
    emails_sent_count INTEGER DEFAULT 0,
    emails_opened_count INTEGER DEFAULT 0
);

CREATE INDEX idx_sub_status ON subscribers(status, tier);
```

### Why This Schema

- **price_observations** is append-only. Every observation is valuable for baseline calculation. Never delete, only truncate old data periodically (>12 months).
- **price_cache** is a materialized view of "what's the current state of this route?" Updated after every check. This is what `seen_deals.json` evolves into.
- **alert_state** tracks the FSM state per route. This is what `alert_cooldown.json` and the tier-tracking in `seen_deals.json` evolve into.
- **subscribers** replaces Google Sheets. Adds preferences and tier columns. Cap stays at 200 during beta (Gmail SMTP limit), scales with SendGrid.
- **price_cents** avoids floating-point comparison issues that plague price tracking systems.

---

## Alert State Machine (Tier-Escalation FSM)

### States

```
         NORMAL
           |
     price drops below Good threshold
           |
           v
         GOOD ---------> NORMAL (price returns to normal)
           |
     price drops below Great threshold
           |
           v
         GREAT --------> NORMAL (price returns to normal)
           |
     price drops below WOW threshold
           |
           v
          WOW ----------> NORMAL (price returns to normal)
```

### Rules

```python
class AlertFSM:
    """
    State machine for tier-escalation alerts.

    Rules:
    1. ENTER a new tier --> ALERT (if not in cooldown)
    2. STAY in same tier --> NO ALERT
    3. ESCALATE to better tier --> ALERT IMMEDIATELY (override cooldown)
    4. DE-ESCALATE (e.g., Great -> Good) --> NO ALERT
    5. RETURN TO NORMAL --> RESET (next drop into any tier will alert again)

    Cooldown timers:
    - After Good alert: 48 hours before re-alerting same tier
    - After Great alert: 24 hours
    - After WOW alert: 12 hours (but escalation always overrides)
    - Tier escalation: Always immediate, no cooldown
    """

    TIER_RANK = {"normal": 0, "good": 1, "great": 2, "wow": 3, "mistake": 4}
    COOLDOWN_HOURS = {"good": 48, "great": 24, "wow": 12}
    NORMAL_RESET_COUNT = 3  # Must see 3 consecutive "normal" prices to reset

    def should_alert(self, route_key, new_tier, current_state):
        old_tier = current_state.current_tier
        old_rank = self.TIER_RANK[old_tier]
        new_rank = self.TIER_RANK[new_tier]

        if new_tier == "normal":
            # Track consecutive normals for reset
            current_state.consecutive_normal_count += 1
            if current_state.consecutive_normal_count >= self.NORMAL_RESET_COUNT:
                self._reset_state(current_state)
            return False  # Never alert on normal

        # Reset the normal counter (price is not normal)
        current_state.consecutive_normal_count = 0

        if new_rank > old_rank:
            # ESCALATION: always alert immediately
            return True

        if new_rank == old_rank:
            # SAME TIER: check cooldown
            if current_state.cooldown_until and datetime.now() < current_state.cooldown_until:
                return False  # In cooldown
            return True  # Cooldown expired, re-alert

        # DE-ESCALATION (e.g., WOW -> Great): don't alert
        return False
```

### Reset Cycle

The "consecutive normal count" prevents premature resets. If a price bounces between $695 (WOW) and $710 (Great) for Lagos, we do not want to reset and re-alert every oscillation. The price must return to clearly normal territory (3 consecutive normal observations) before the cycle resets.

This directly addresses the requirement: "Price-normalized cycle: reset alert cycle when price returns to normal range."

---

## Baseline Calculation (Anomaly Detection)

### Phase 1: Manual Seasonal Baselines (Now)

Use the manually researched baselines from `pricing-tiers-design.md`. These are already validated and working.

```python
# Already defined in deal_finder.py DESTINATIONS config
MANUAL_BASELINES = {
    "LOS": {"off_peak": 900, "jul_peak": 1400, "dec_peak": 1800},
    "ACC": {"off_peak": 900, "jul_peak": 1150, "dec_peak": 1400},
    # ... etc
}
```

### Phase 2: Hybrid Baselines (After 3 months of data)

When a route/season has 30+ observations, compute a data-driven baseline:

```python
def get_baseline(origin, dest, season, fare_class="economy"):
    """
    Get price baseline for anomaly scoring.
    Uses data-driven baseline when available, falls back to manual.
    """
    observations = db.query("""
        SELECT price_cents FROM price_observations
        WHERE origin = ? AND destination = ? AND season = ?
          AND fare_class = ?
          AND observed_at > datetime('now', '-6 months')
        ORDER BY price_cents
    """, (origin, dest, season, fare_class))

    if len(observations) >= 30:
        # Data-driven: use median as baseline
        prices = [o.price_cents for o in observations]
        median_price = statistics.median(prices)
        return median_price, "data_driven"
    elif dest in MANUAL_BASELINES:
        baseline = MANUAL_BASELINES[dest].get(season)
        return baseline * 100, "manual"  # Convert to cents
    else:
        return None, "unknown"  # Learning mode -- don't classify


def score_deal(price_cents, baseline_cents, source_type):
    """
    Score a price against its baseline.
    Returns tier and confidence metrics.
    """
    if baseline_cents is None:
        return None  # Can't score without baseline

    percent_below = (baseline_cents - price_cents) / baseline_cents

    # Tier classification
    if percent_below >= 0.40:
        tier = "wow"
    elif percent_below >= 0.30:
        tier = "great"
    elif percent_below >= 0.20:
        tier = "good"
    else:
        tier = "normal"

    # Z-score for confidence (when data-driven)
    z_score = None
    if source_type == "data_driven":
        mean = statistics.mean(prices)
        stdev = statistics.stdev(prices)
        if stdev > 0:
            z_score = (price_cents - mean) / stdev
            # A z-score of -2.0 or below = very unusual (bottom ~2%)

    return {
        "tier": tier,
        "percent_below": round(percent_below * 100, 1),
        "baseline": baseline_cents,
        "baseline_source": source_type,
        "z_score": z_score,
    }
```

### Phase 3: Full Data-Driven (By August 2026)

When sufficient data exists, the system can also factor in:
- **Booking window bands**: Prices 120+ days out vs. 60-90 days vs. <30 days behave differently
- **Day-of-week effects**: Thursday departures ~10-15% cheaper than Sunday
- **Airline-specific patterns**: Direct routes (Delta JFK-LOS) price differently than connecting

This is described in detail in the existing `docs/plans/2026-01-19-pricing-tiers-design.md` and does not require architectural changes -- it is a logic upgrade within `anomaly_detector.py`.

---

## Subscriber Segmentation & Routing

### Routing Matrix

| Deal Tier | Free Subscribers | Premium Subscribers |
|-----------|-----------------|-------------------|
| Good | Yes (all routes, economy) | Yes (all routes, all classes) |
| Great | Yes (all routes, economy) | Yes (all routes, all classes) |
| WOW | Teaser only ("Premium subscribers got this deal") | Yes (full alert) |
| Mistake | No | Yes (immediate) |
| Business/First | No | Yes |

### Teaser Strategy for Free-to-Premium Conversion

When a WOW deal fires, free subscribers get a "you missed this" email the next day:

```
Subject: You missed a WOW deal to Lagos ($580)

"Yesterday, premium members got alerted to a $580 round-trip to Lagos.
It sold out in 4 hours. Upgrade to premium to never miss WOW deals."
```

This creates urgency and demonstrates the value gap. Implementation: a separate "teaser" workflow that runs daily, queries yesterday's WOW/Mistake deals, and sends to free subscribers.

### Preference Filtering

```python
def route_alert_to_subscribers(deal, subscribers):
    """
    Filter subscribers based on their preferences.
    Returns list of (subscriber, deal) pairs to send.
    """
    to_send = []
    for sub in subscribers:
        # Tier gating
        if deal.tier in ("wow", "mistake") and sub.tier == "free":
            continue  # Free users don't get WOW/Mistake (except teasers)
        if deal.fare_class != "economy" and sub.tier == "free":
            continue  # Free users only get economy

        # Origin region filtering (if subscriber has preference)
        if sub.origin_region and sub.origin_region != "all":
            if not origin_in_region(deal.origin, sub.origin_region):
                continue

        # Destination region filtering
        if sub.dest_region and sub.dest_region != "all":
            if not dest_in_region(deal.destination, sub.dest_region):
                continue

        to_send.append((sub, deal))

    return to_send
```

---

## What Stays on GitHub Actions vs. What Needs a Persistent Service

### Stays on GitHub Actions (Everything)

| Workflow | Schedule | Minutes/Run | Monthly Minutes |
|----------|----------|-------------|----------------|
| priority_monitor.yml (Amadeus) | Every 2 hours | ~2 min | ~720 min |
| find_deals.yml (fast-flights) | Daily | ~45 min | ~1,350 min |
| mistake_fares.yml (RSS) | Every 30 min | ~1 min | ~1,440 min |
| **Total** | | | **~3,510 min** |

**Problem**: Free tier = 2,000 min/month. This exceeds it.

### Budget Solution

| Option | Cost | Minutes |
|--------|------|---------|
| GitHub Free (current) | $0 | 2,000 min |
| GitHub Team | $4/user/month | 3,000 min |
| **Buy additional minutes** | ~$0.008/min overage | Pay for ~1,500 extra = ~$12/month |
| Move RSS to cheaper runner | -- | Save ~1,000 min |

**Recommendation**: Optimize first, then buy minutes if needed.

#### Optimization: Reduce fast-flights runtime

Current: 77 routes x 26 weeks = 2,002 searches, ~45 min.
Optimized: Search only routes NOT covered by Amadeus priority monitor. Skip routes already found as deals this week.

- Remove 6 priority routes from daily scan (Amadeus handles them): 71 routes
- Only search 4-6 weeks deep on first pass, full 26 weeks on weekend scan: ~20 min weekday, ~45 min weekend
- Estimated monthly: (20 x 5 + 45 x 2) x 4 = ~760 min

Revised total: 720 + 760 + 1440 = ~2,920 min. Still over, but closer.

#### Further optimization: RSS to 60 min instead of 30 min

Mistake fares from RSS are already hours old by the time they appear. Going from 30 min to 60 min loses almost nothing.

Revised total: 720 + 760 + 720 = **~2,200 min**. Very close to free tier. Overage cost: ~$1.60/month.

### Nothing needs a persistent service

The key architectural decision: **Turso is the persistent service.** GitHub Actions scripts connect to Turso DB over HTTPS, read/write state, and exit. There is no always-on server. Turso handles persistence, and GitHub Actions handles scheduling and compute.

This eliminates the need for any VPS, container service, or always-on process -- which is where costs spiral for small projects.

---

## Migration Path: JSON Files to Turso DB

### Phase 0: Turso Setup (1 hour)

1. Create Turso account (free tier: 500 DBs, 5 GB storage, 500M reads/month)
2. Create `detty-deals` database
3. Run schema migration SQL
4. Store `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` as GitHub secrets
5. Add `libsql` to `requirements.txt`

### Phase 1: Dual-Write (1-2 days)

Run both systems in parallel. JSON files remain the source of truth, but every write also goes to Turso.

```python
# price_tracker.py -- dual-write phase
def record_price(observation):
    # Existing: write to price_history.jsonl
    log_price_search(...)

    # New: also write to Turso
    db.execute("""
        INSERT INTO price_observations
        (origin, destination, travel_date, price_cents, source, ...)
        VALUES (?, ?, ?, ?, ?)
    """, ...)

def check_deal_state(route_key):
    # Existing: check seen_deals.json
    seen = load_seen_deals()
    if route_key in seen:
        return seen[route_key]

    # New: also check Turso (should match)
    row = db.execute("SELECT * FROM price_cache WHERE route_key = ?", (route_key,))
    return row
```

Validate for 1 week that Turso state matches JSON state. Fix any discrepancies.

### Phase 2: Turso Primary, JSON Backup (1 day)

Switch reads to Turso. Keep JSON writes as backup.

```python
def check_deal_state(route_key):
    # Primary: Turso
    row = db.execute("SELECT * FROM price_cache WHERE route_key = ?", (route_key,))
    if row:
        return row

    # Fallback: JSON (in case Turso is down)
    seen = load_seen_deals()
    return seen.get(route_key)
```

### Phase 3: Remove JSON (1 day)

Once validated:
- Remove `seen_deals.json` commit step from workflows
- Remove `seen_mistake_fares.json` commit step from workflows
- Remove JSON read/write functions
- Keep `price_history.jsonl` as a local backup (gitignored) until Turso is proven stable

### Migration of Google Sheets Subscribers

This is a one-time data copy:
1. Read all subscribers from Google Sheets via `get_subscribers()`
2. Insert into `subscribers` table in Turso
3. All new signups go directly to Turso (via a simple API endpoint or Google Forms -> Apps Script -> Turso HTTP API)
4. Keep Google Sheets as read-only backup for 30 days
5. Remove Google Sheets dependency from `mvp0_sender.py`

---

## Suggested Build Order

The order is driven by dependencies and risk. Each phase is independently valuable -- if you stop after any phase, the system is in a better state than before.

### Phase 1: Amadeus Integration (No DB change needed)
**Dependencies:** Amadeus API credentials
**Builds:** `amadeus_client.py`, `amadeus_monitor.py`, `priority_monitor.yml`
**Risk:** Low (adds new data source alongside existing, does not touch existing code)
**Value:** 2-hour monitoring on 6 highest-value routes

*This phase is already designed in detail in `docs/plans/2026-01-19-amadeus-continuous-monitoring-design.md`*

### Phase 2: Database Migration (JSON --> Turso)
**Dependencies:** Phase 1 (validates that multiple write sources work)
**Builds:** Turso schema, `db.py` module, dual-write in `price_tracker.py`
**Risk:** Medium (changing state management is always risky; dual-write mitigates)
**Value:** Eliminates merge conflicts, enables historical queries, unblocks anomaly detection

### Phase 3: Anomaly Detection
**Dependencies:** Phase 2 (needs historical price data in queryable DB)
**Builds:** `anomaly_detector.py`, seasonal baseline queries
**Risk:** Low (purely additive, does not change alerting behavior until enabled)
**Value:** Data-driven deal classification, replaces manual thresholds over time

### Phase 4: Alert State Machine
**Dependencies:** Phase 2 (needs `alert_state` table), Phase 3 (needs scored deals)
**Builds:** `alert_engine.py` with FSM, cooldown management
**Risk:** Medium (changes when and how alerts fire -- could over-alert or under-alert)
**Value:** Tier-escalation alerts, proper cooldown, eliminates alert fatigue

### Phase 5: Subscriber Segmentation
**Dependencies:** Phase 2 (needs `subscribers` table in Turso)
**Builds:** Subscriber migration, preference-based routing in `alert_engine.py`
**Risk:** Low (additive; free tier gets everything during beta)
**Value:** Foundation for freemium model, regional preferences

### Phase 6: Business/First Class Monitoring
**Dependencies:** Phase 1 (Amadeus supports fare class parameter), Phase 2 (DB stores fare_class)
**Builds:** `fare_class` parameter in monitoring scripts, premium-only routing
**Risk:** Low (new data, additive)
**Value:** Premium-only feature, differentiation from competitors

### Phase 7: Email Delivery Upgrade (Gmail --> SendGrid)
**Dependencies:** Phase 5 (subscriber segmentation determines send volume)
**Builds:** SendGrid integration in `email_sender.py`, delivery tracking
**Risk:** Low (swap transport layer, keep email content unchanged)
**Value:** Scale beyond 200 subscribers, delivery analytics

---

## Cost Estimate (Target Architecture)

| Service | Purpose | Free Tier | Estimated Cost |
|---------|---------|-----------|----------------|
| **GitHub Actions** | Compute / scheduling | 2,000 min | $0-12/month (overage) |
| **Turso** | Database (prices, state, subscribers) | 5 GB, 500M reads | $0 (free tier sufficient) |
| **Amadeus API** | Priority route monitoring | 2,000 calls/month | $0 (free tier) |
| **Gmail SMTP** | Email delivery (<200 subs) | 500/day | $0 |
| **SendGrid** (Phase 7) | Email delivery (200+ subs) | 100/day free | $0-20/month |
| **Domain** | dettyflightdeals.com | -- | ~$12/year |
| **Total** | | | **$0-32/month** |

This is well within the $50-100/month budget, leaving headroom for Amadeus production upgrade ($20-40/month at ~$0.01-0.02/call) if priority route coverage expands.

---

## Patterns to Follow

### Pattern 1: Source-Agnostic Ingestion

Every price source (Amadeus, fast-flights, SerpApi, future GDS) produces the same `PriceObservation` data class. Downstream components never know or care where the price came from.

```python
@dataclass
class PriceObservation:
    origin: str          # "JFK"
    destination: str     # "LOS"
    travel_date: str     # "2026-07-15"
    return_date: str     # "2026-07-25" or None
    price_cents: int     # 89200
    fare_class: str      # "economy"
    source: str          # "amadeus" | "fast_flights" | "serpapi"
    observed_at: datetime
```

**Why:** Adding a new data source should be a single new file + workflow, not a refactor of the pipeline.

### Pattern 2: Idempotent Pipeline Stages

Every stage can be re-run safely. If `price_tracker.py` processes the same observation twice, the second run is a no-op (upsert to cache, append to history is already idempotent).

**Why:** GitHub Actions can retry. Cron jobs can overlap. The pipeline must handle it.

### Pattern 3: Graceful Degradation

If Turso is unreachable, fall back to local JSON. If Amadeus API fails, skip priority routes and rely on daily fast-flights scan. If Gmail SMTP fails, log deals to console (they will be sent on next successful run).

**Why:** A monitoring system that fails silently is worse than one that sends late.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Always-On Server

**What:** Running a VPS or container to host the monitoring pipeline.
**Why bad:** At $50-100/month budget, a $5-20/month VPS eats budget for zero benefit. The pipeline is batch, not real-time. GitHub Actions provides compute when needed.
**Instead:** Keep everything as scheduled batch jobs on GitHub Actions.

### Anti-Pattern 2: Event-Driven / Message Queue Architecture

**What:** Using Kafka, RabbitMQ, or AWS SQS between pipeline stages.
**Why bad:** Massive over-engineering for a system processing <100 events per run. Adds infrastructure cost, operational complexity, and debugging difficulty.
**Instead:** Direct function calls within the same Python process. If stage A produces output, stage B receives it as a function argument.

### Anti-Pattern 3: Committing State Files to Git

**What:** Current pattern of committing `seen_deals.json` back to the repo.
**Why bad:** Creates merge conflicts when multiple workflows run concurrently. Pollutes git history with state changes. Does not scale to frequent updates.
**Instead:** Use Turso DB for all mutable state. Git repo contains only code and static config.

### Anti-Pattern 4: Per-Date Alert Tracking

**What:** Tracking "I alerted JFK-LOS for March 15 departure."
**Why bad:** Creates explosion of tracked state. Users do not care about specific dates -- they care about "Lagos is cheap right now."
**Instead:** Track per-route alerts (JFK-LOS) with tier. One alert covers all dates where this route is cheap.

---

## Scalability Considerations

| Concern | At 200 Users (Now) | At 2,000 Users (6 months) | At 20,000 Users (18 months) |
|---------|-------------------|--------------------------|----------------------------|
| **Email delivery** | Gmail SMTP (500/day) | SendGrid free (100/day) or paid ($20/mo for 40K/mo) | SendGrid or Amazon SES ($0.10/1000) |
| **Database size** | <100 MB (Turso free) | <500 MB (Turso free) | 1-2 GB (Turso $4.99/mo) |
| **API calls** | Amadeus free (2K/mo) | Amadeus paid (~$40/mo) | Amadeus paid + SerpApi backup |
| **Compute** | GitHub Actions free | GitHub Actions ($12/mo overage) | Consider Railway/Fly.io ($5-25/mo) |
| **Subscriber management** | Turso table | Turso table + preferences | Turso + auth (Clerk/Auth0 free tier) |
| **Payment** | Manual (Venmo/$5) | Stripe Checkout ($0) | Stripe Billing |

The architecture does not need to change at any of these scales. The components stay the same. What changes is:
- Transport layer (Gmail --> SendGrid --> SES)
- API budget (free --> paid)
- Compute provider (GitHub Actions --> Railway, if needed)

---

## Open Questions (Flagged for Phase-Specific Research)

1. **Amadeus test vs. production environment**: The design doc says test environment returns "real prices." Need to validate whether test environment prices match production accuracy before relying on them for anomaly detection baselines.

2. **fast-flights reliability at scale**: The scraper can get rate-limited or blocked. If fast-flights becomes unreliable, SerpApi (Google Flights API) is the backup at $50/month for 5,000 searches. This is a Phase 1 risk to monitor.

3. **Turso Python SDK maturity**: The `libsql` Python SDK is relatively new. Need to test connection handling, retry behavior, and error handling in the GitHub Actions environment specifically. This is a Phase 2 risk.

4. **Gmail SMTP rate limits under concurrent sends**: If 3 workflows detect deals simultaneously and all try to send emails, does Gmail throttle? Need to centralize sending or add a mutex. This is a Phase 4 consideration.

5. **Trip length flexibility**: Current system hardcodes 10-day trips. Amadeus Cheapest Date Search can return variable trip lengths. Architecture supports this (just add `trip_length` to `PriceObservation`), but the alert messaging needs updating.

---

## Sources

- [Turso Pricing](https://turso.tech/pricing) - Free tier: 500 DBs, 5 GB, 500M reads/month (MEDIUM confidence - pricing page, not official contract)
- [Turso Python SDK](https://docs.turso.tech/sdk/python/quickstart) - `libsql` package for Python (HIGH confidence - official docs)
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage) - 2,000 free minutes for GitHub Free (HIGH confidence - official docs)
- [GitHub Actions 2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/) - Free minute quotas unchanged, runner price -39%, new platform charge for self-hosted (HIGH confidence - official announcement)
- [Amadeus Flight Cheapest Date Search API](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search) - Official API docs (HIGH confidence)
- [Amadeus Python SDK](https://github.com/amadeus4dev/amadeus-python) - `amadeus` package, MIT licensed (HIGH confidence - official repo)
- [GitHub Actions Database Persistence Experiments](https://github.com/karlhorky/github-actions-database-persistence) - Patterns for persisting SQLite to GitHub Actions (MEDIUM confidence - community project)
- [AirHint Flight Price Predictor](https://www.airhint.com/) - Airline-specific neural networks for price prediction (LOW confidence - commercial tool, methodology not public)
- Existing design docs: `docs/plans/2026-01-19-amadeus-continuous-monitoring-design.md`, `docs/plans/2026-01-19-pricing-tiers-design.md` (HIGH confidence - project artifacts)
