# Technology Stack

**Project:** Detty Flight Deals - Flight Deal Monitoring Service Upgrade
**Researched:** 2026-01-27
**Overall Confidence:** MEDIUM-HIGH

---

## Budget Summary

**Target:** $50-100/month total infrastructure
**Estimated Total:** $25-65/month (well within budget)

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| Flight Data (Amadeus) | $0-15 | Free quota covers priority routes; pay-per-call beyond |
| Flight Data (fast-flights/fli) | $0 | Free scraping for broad coverage |
| Database (Turso) | $0-5 | Free tier covers MVP; $4.99 if exceeded |
| Email (Resend) | $0-20 | Free tier covers 200 subs; Pro at scale |
| Scheduling (GitHub Actions) | $0 | Public repo = unlimited minutes |
| Subscriber Mgmt (Supabase) | $0 | Free tier = 50K MAU, 500MB DB |
| **Total** | **$0-40** | **Leaves $60-100 headroom for growth** |

---

## 1. Flight Data Sources

### RECOMMENDED: Hybrid Approach (Amadeus API + fast-flights/fli scraper)

**Confidence:** MEDIUM-HIGH

Use Amadeus for priority/premium routes where accuracy matters most. Keep fast-flights (or upgrade to `fli`) for broad coverage scanning where cost per query matters.

#### Primary: Amadeus Self-Service API

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `amadeus` (Python SDK) | latest | Priority route monitoring, business class, cheapest date search | Only legitimate API with GDS-level fare data, 400+ airlines, business/first class fares |

**Pricing (verified via official docs):**
- Free quota: 1,000-10,000 calls/month per API (exact per-API quota shown on pricing page after login)
- Pay-per-call beyond free: ~EUR 0.001-0.025/call (~$0.001-0.027)
- Rate limit: 10 req/sec (test), 40 req/sec (production)
- No monthly subscription required

**Key APIs to use:**
1. **Flight Cheapest Date Search** -- Returns cached cheapest prices across a date range for an origin-destination pair. One call covers an entire month of dates. This is the highest-value API for Detty because it replaces 26 separate fast-flights calls with a single API call.
2. **Flight Offers Search** -- Real-time search across 400+ airlines. Use for validating deals before alerting, and for business/first class searches.
3. **Flight Inspiration Search** -- "Where can I fly cheaply from JFK?" Returns destinations sorted by price. Useful for discovering unexpected deals.

**Budget math for Amadeus:**
- 77 routes x 1 call/route = 77 calls for a full scan using Cheapest Date Search
- Every 2 hours = 12 scans/day = 924 calls/day = ~27,720 calls/month
- Free quota absorbs first 2,000-10,000 calls
- Remaining ~18,000-26,000 calls at ~$0.005/call = $90-130/month -- **TOO EXPENSIVE for every-2-hour full scans**

**Recommended strategy:**
- **Tier 1 (every 2 hours):** Top 15 priority routes (JFK/EWR/IAD to LOS/ACC/ABV) = 15 x 12 x 30 = 5,400 calls/month. Fits within or near free quota. Cost: $0-15/month.
- **Tier 2 (every 6 hours):** Next 30 routes = 30 x 4 x 30 = 3,600 calls/month. Cost: $0-10/month.
- **Tier 3 (daily):** Remaining 32 routes via fast-flights = $0/month.
- **Business class:** Use Flight Offers Search for Tier 1 routes only, 2x/day = 900 calls/month.

**Estimated Amadeus total:** ~10,000-11,000 calls/month = $0-30/month (depending on how much the free quota absorbs).

**Confidence note:** Exact free quota per API could not be confirmed from web research alone -- the Amadeus pricing page renders dynamically. The PROJECT.md states "Free tier = 2,000 calls/month" which is plausible. After signup, check the dashboard. [LOW confidence on exact quota, HIGH confidence on pricing model]

#### Secondary: fast-flights or fli (Google Flights scraping)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `fast-flights` | >=1.0.0 | Broad daily route scanning (Tier 3 routes) | Already integrated, free, good enough for daily scans |
| `flights` (fli) | 0.7.0 | Potential replacement for fast-flights | Reverse-engineered API (no scraping), faster, more reliable |

**fast-flights status:**
- Currently in use and working
- Risk: Scraping-based, can break when Google changes HTML
- Limitation: Searches specific date pairs, not date ranges
- No business class support confirmed

**fli (flights) as potential upgrade:**
- Released Dec 2025 by punitarani
- Uses reverse-engineered Google Flights API endpoints directly -- no HTML parsing
- Faster and more reliable than scraping
- MIT licensed, active development
- Includes CLI and MCP server
- **Risk:** Reverse-engineered APIs can break without notice. Google may block.
- [MEDIUM confidence -- newer library, promising but less battle-tested]

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **SerpAPI Google Flights** | $75/month for 5,000 searches. Way too expensive for 77 routes x multiple scans. At $0.015/search, monitoring costs would consume entire budget. |
| **Skyscanner API** | Requires partner approval for "established travel businesses with significant traffic." Not available for small/early projects. Case-by-case approval, needs existing audience. |
| **Kiwi Tequila API** | Previously free but shifted to selective partnerships in 2024. Public access no longer guaranteed. Travelpayouts channel requires 50K MAU minimum. |
| **ITA Matrix** | No API access. Manual-only tool. |
| **Duffel** | Booking-focused, not price monitoring. Charges per booking, not per search. |
| **Full GDS access (Sabre/Travelport)** | Enterprise pricing, complex integration, way beyond budget. |
| **Scraping services (Oxylabs, Bright Data)** | $200+/month for proxy infrastructure. Overkill for this use case. |

---

## 2. Price Database

### RECOMMENDED: Turso (libSQL)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Turso (libSQL) | latest | Price history storage, baseline calculation, anomaly detection queries | Free tier covers MVP (5GB, 500M reads, 10M writes/month), SQLite-compatible, edge-ready |

**Confidence:** HIGH

**Why Turso over alternatives:**

1. **SQLite-compatible** -- Your existing `price_history.jsonl` migration is trivial. Standard SQL, no ORM learning curve.
2. **Free tier is generous** -- 5GB storage, 500M row reads, 10M row writes per month. More than enough for millions of price points.
3. **Cloud-hosted without ops burden** -- No server to manage, no PostgreSQL to maintain. Just a connection string.
4. **Local dev works offline** -- Use a local SQLite file in development, Turso in production. Same queries.
5. **Upgrade path is cheap** -- $4.99/month Developer plan if you outgrow the free tier.

**Schema considerations:**
- ~77 routes x ~30 price points/month = ~2,310 rows/month from Amadeus
- ~77 routes x ~26 dates x daily = ~60,060 rows/month from fast-flights
- At ~62K rows/month, you'll have ~750K rows after a year. Turso handles this easily.
- Add indexes on (origin, destination, search_date) and (origin, destination, travel_date) for fast baseline queries.

**Migration from price_history.jsonl:**
```python
import sqlite3, json
conn = sqlite3.connect("prices.db")
conn.execute("""CREATE TABLE prices (
    id INTEGER PRIMARY KEY,
    searched_at TEXT, origin TEXT, destination TEXT,
    travel_date TEXT, return_date TEXT, price INTEGER,
    source TEXT, days_until_travel INTEGER, season TEXT,
    cabin_class TEXT DEFAULT 'economy'
)""")
with open("price_history.jsonl") as f:
    for line in f:
        row = json.loads(line)
        conn.execute("INSERT INTO prices (...) VALUES (...)", ...)
```

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **Plain SQLite file** | Works locally but doesn't survive GitHub Actions ephemeral runners. You'd need to commit the DB to git (messy) or use artifact storage (brittle). Turso solves this. |
| **Supabase (PostgreSQL)** | Overkill for price storage. 500MB free tier is tight for millions of rows. PostgreSQL is heavier than needed -- you don't need JOINs across 20 tables, you need fast time-series reads. Use Supabase for subscriber management instead (see below). |
| **PlanetScale** | Deprecated free tier in 2024. No longer cost-competitive for small projects. |
| **Neon (PostgreSQL)** | Good alternative but Turso's SQLite compatibility is simpler for this Python-heavy project. Neon's free tier (500MB, 100 hours compute) is more restrictive. |
| **TimescaleDB** | Enterprise-grade time-series DB. Extreme overkill for <1M rows/year. |
| **DynamoDB/MongoDB** | NoSQL is a poor fit for price range queries and statistical aggregations. |

---

## 3. Email Delivery

### RECOMMENDED: Resend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Resend (Python SDK) | latest | Email delivery for deal alerts | 3,000 emails/month free, clean API, best DX, scales to $20/month for 50K emails |

**Confidence:** HIGH

**Why Resend:**

1. **Free tier perfectly matches your scale** -- 200 subscribers x ~4 emails/month = 800 emails. Well within 3,000 free limit.
2. **Clean upgrade path** -- When you hit 1,000 subscribers sending 4x/month = 4,000 emails, the Pro plan at $20/month covers 50,000 emails.
3. **Developer-first API** -- Simple Python integration. No bloated dashboard.
4. **HTML email support** -- Your existing HTML templates work as-is.
5. **Deliverability** -- Purpose-built for transactional email. Better inbox placement than Gmail SMTP.
6. **No daily sending limit on paid plans** -- Gmail SMTP caps at 500/day; Resend doesn't.

**Cost at scale:**
| Subscribers | Emails/month (4 alerts) | Plan | Cost |
|-------------|------------------------|------|------|
| 200 | 800 | Free | $0 |
| 500 | 2,000 | Free | $0 |
| 750 | 3,000 | Free (limit) | $0 |
| 1,000 | 4,000 | Pro | $20 |
| 5,000 | 20,000 | Pro | $20 |
| 10,000 | 40,000 | Pro | $20 |

**Implementation note:** Keep Gmail SMTP as a fallback. Resend integration is ~20 lines of Python:
```python
import resend
resend.api_key = os.environ["RESEND_API_KEY"]
resend.Emails.send({
    "from": "deals@dettyflightdeals.com",
    "to": subscriber_email,
    "subject": subject,
    "html": html_body
})
```

**Requires:** A custom domain (dettyflightdeals.com) with DNS records for Resend verification. You already have the domain.

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **Gmail SMTP** | Current solution. Caps at 500/day, no tracking, poor deliverability at scale, Google can suspend for "bulk sending." Keep as emergency fallback only. |
| **SendGrid** | Free tier is only 100 emails/day for 60 days, then requires paid plan. Essentials at $19.95/month gives 50K emails but the product is bloated, UI is confusing, and deliverability has declined since Twilio acquisition. |
| **Postmark** | Excellent deliverability but no real free tier (100 emails/month for testing only). $15/month for 10K emails. More expensive than Resend for equivalent volume. Better if deliverability is the only thing that matters. |
| **Buttondown** | Already tried. Newsletter platform, not a transactional email API. Wrong tool for programmatic deal alerts. |
| **Amazon SES** | Cheapest at scale ($0.10/1K emails) but requires AWS account, IAM setup, domain verification, and dealing with sandbox mode. Operational complexity not worth it under 50K emails/month. |
| **Mailgun** | $0.80/1K emails on Flex plan. More expensive than Resend for this volume range. API is good but Resend is simpler. |

---

## 4. Subscriber Management

### RECOMMENDED: Supabase (Free Tier)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Supabase | latest | Subscriber database, preferences, auth, freemium tier management | 50K MAU free, PostgreSQL, built-in auth, Row Level Security, REST API |

**Confidence:** HIGH

**Why Supabase for subscribers (not Turso):**

Turso is better for price data (high-volume writes, simple schema). Supabase is better for subscriber management because:

1. **Built-in authentication** -- Email/password, magic links, social login. No auth library needed.
2. **Row Level Security** -- Subscribers can only see/edit their own preferences. Policy-based, no custom middleware.
3. **REST API included** -- Your landing page can call Supabase directly for signup without a backend server.
4. **PostgreSQL for relational data** -- Subscribers have preferences, tiers, billing status, route preferences -- relational data that benefits from JOINs.
5. **Free tier is massive** -- 50K MAU, 500MB database, unlimited API requests. You won't outgrow this for years.
6. **Replaces Google Sheets** -- Structured queries, proper indexing, no row limits, no API rate limiting.

**Schema sketch:**
```sql
-- Supabase handles auth.users automatically
CREATE TABLE subscribers (
    id UUID PRIMARY KEY REFERENCES auth.users(id),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    tier TEXT DEFAULT 'free' CHECK (tier IN ('free', 'premium', 'trial')),
    origin_region TEXT[], -- ['northeast', 'southeast']
    dest_region TEXT[],   -- ['west_africa', 'east_africa']
    cabin_class TEXT[] DEFAULT '{economy}',
    created_at TIMESTAMPTZ DEFAULT now(),
    trial_expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE alert_history (
    id BIGSERIAL PRIMARY KEY,
    subscriber_id UUID REFERENCES subscribers(id),
    sent_at TIMESTAMPTZ DEFAULT now(),
    deal_tier TEXT,
    origin TEXT,
    destination TEXT,
    price INTEGER
);
```

**Migration from Google Sheets:** Export CSV, import into Supabase via dashboard or `psycopg2`.

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **Google Sheets** | Current solution. No auth, no preferences, 200-row practical limit, API rate limits, no query capability, manual unsubscribe. |
| **Firebase** | Firestore's NoSQL model is awkward for subscriber data with preferences. Proprietary lock-in. Pricing can spike unpredictably on reads. |
| **Plain PostgreSQL (self-hosted)** | You'd need to manage a server, handle auth yourself, build an API. Supabase gives you all of this for free. |
| **Airtable** | Better Google Sheets but still not a real database. 1,000-row limit on free tier. |
| **Turso** | No built-in auth. No REST API for landing page integration. Wrong tool for user management. |

---

## 5. Anomaly Detection

### RECOMMENDED: Rolling Z-Score with scipy + ADTK for advanced cases

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `scipy` | >=1.11.0 | Z-score and Modified Z-score calculations | Already a standard dependency, no new library needed |
| `numpy` | >=1.24.0 | Array operations for price statistics | Standard dependency |
| `adtk` | 0.6.2 | Level shift detection, seasonal anomaly detection | Purpose-built for time-series anomaly detection, rule-based (no ML training needed) |

**Confidence:** HIGH (for the approach), MEDIUM (for ADTK library maintenance -- last release was a while ago)

**Approach -- Build in Layers:**

**Layer 1: Rolling Z-Score (start here, covers 80% of cases)**
```python
from scipy.stats import zscore
import numpy as np

def is_anomaly(current_price, historical_prices, threshold=-2.5):
    """Detect if current price is anomalously LOW."""
    if len(historical_prices) < 10:
        return False  # Not enough data
    z = (current_price - np.mean(historical_prices)) / np.std(historical_prices)
    return z < threshold  # Negative z = below average
```

Use rolling 90-day windows per route. Flag prices with z-score < -2.5 (2.5 standard deviations below mean).

**Layer 2: Modified Z-Score with MAD (handles outlier-skewed history)**
```python
from scipy.stats import median_abs_deviation

def modified_z_score(price, historical_prices):
    median = np.median(historical_prices)
    mad = median_abs_deviation(historical_prices)
    if mad == 0:
        return 0
    return 0.6745 * (price - median) / mad
```

Use MAD-based z-scores when a route has volatile history (e.g., seasonal peaks). Threshold: < -3.5.

**Layer 3: ADTK Level Shift Detection (for mistake fares)**
```python
from adtk.detector import LevelShiftAD
detector = LevelShiftAD(c=6.0, side='negative', window=5)
anomalies = detector.detect(price_series)
```

ADTK's `LevelShiftAD` uses two sliding windows to detect sudden drops. Perfect for catching mistake fares that appear as sharp level shifts.

**Layer 4: Seasonal Baseline (future enhancement)**
Once you have 6+ months of data per route, calculate seasonal baselines:
- Peak (Dec-Feb): Higher normal prices
- Shoulder (Mar-May, Sep-Nov): Moderate
- Summer (Jun-Aug): Lower

Adjust z-score thresholds by season for more accurate anomaly detection.

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **Machine Learning models (Prophet, LSTM)** | Requires large training datasets you don't have yet. Overkill for 77 routes with <1 year of data. Z-scores work better with small datasets. |
| **Luminol** | Last updated years ago (v0.4). Not actively maintained. ADTK is more capable and better documented. |
| **PyOD / PySAD** | Designed for general outlier detection, not time-series price monitoring specifically. More complex setup for less relevant output. |
| **Paid anomaly detection services** | Unnecessary cost for a problem solvable with scipy in 20 lines of code. |

---

## 6. Scheduling & Automation

### RECOMMENDED: GitHub Actions (keep current approach, with tiered scheduling)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| GitHub Actions | N/A | Cron scheduling for all monitoring jobs | Free unlimited minutes (public repo), already integrated, improving reliability in Q1 2026 |

**Confidence:** HIGH

**Why stay on GitHub Actions:**

1. **Free for public repos** -- Unlimited minutes. No cost.
2. **Already working** -- Current workflows are proven. Migration has real cost.
3. **2026 improvements** -- GitHub is adding timezone support for scheduled jobs and improving schedule reliability in Q1 2026.
4. **Sufficient for 2-hour intervals** -- The minimum interval is 5 minutes. 2-hour cron works fine.
5. **Budget preservation** -- $0/month vs $5-20/month for alternatives.

**Known limitations (and mitigations):**
- **Timing drift:** Cron jobs can be delayed 15-30 minutes during high load. **Mitigation:** For flight deals, 15-30 minute delay is acceptable. Mistake fares last hours, not minutes.
- **60-day inactivity disable:** Workflows pause if repo has no commits. **Mitigation:** Add a weekly keep-alive commit or use workflow_dispatch triggers.
- **6-hour max runtime:** Fine -- full route scans should complete in 2-3 hours max.

**Tiered workflow design:**
```yaml
# .github/workflows/priority_monitor.yml
# Runs every 2 hours -- Tier 1 priority routes via Amadeus
on:
  schedule:
    - cron: '0 */2 * * *'

# .github/workflows/broad_monitor.yml
# Runs every 6 hours -- Tier 2 routes via Amadeus
on:
  schedule:
    - cron: '0 */6 * * *'

# .github/workflows/daily_scan.yml
# Runs daily -- Tier 3 routes via fast-flights (existing)
on:
  schedule:
    - cron: '0 8 * * *'

# .github/workflows/mistake_fare_monitor.yml
# Runs every 30 minutes -- RSS feeds (existing, lightweight)
on:
  schedule:
    - cron: '*/30 * * * *'
```

### What NOT to Use

| Option | Why Not |
|--------|---------|
| **Railway** | No free tier (30-day trial only). $5/month minimum. Cron jobs have same 5-min minimum interval. You gain timing precision but lose $60/year for marginal improvement. |
| **Render** | $1/month per cron job. With 4 scheduled workflows, that's $4/month. No persistent disk for cron jobs. Marginal benefit over GitHub Actions. |
| **Dedicated VPS (DigitalOcean, Hetzner)** | $5-12/month. Gives you full control but you're now managing a server, handling updates, monitoring uptime. Not worth it until you outgrow GitHub Actions (unlikely under 200 subs). |
| **Vercel Cron** | Hobby plan limited to daily crons. Pro plan ($20/month) for more frequent. Too expensive for what it provides. |
| **AWS Lambda + EventBridge** | Free tier generous (1M invocations/month) but operational complexity is high. CloudWatch, IAM, Lambda layers for dependencies. Over-engineered for this project. |

---

## 7. Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `amadeus` | latest | Amadeus API Python SDK | All Amadeus API calls |
| `fast-flights` | >=1.0.0 | Google Flights scraping | Tier 3 daily route scans (existing) |
| `feedparser` | >=6.0.0 | RSS mistake fare monitoring | Existing, keep as-is |
| `resend` | latest | Email delivery API | Replacing Gmail SMTP |
| `supabase` | latest | Supabase Python client | Subscriber management |
| `libsql-experimental` | latest | Turso/libSQL Python client | Price database access |
| `scipy` | >=1.11.0 | Statistical anomaly detection | Z-score calculations |
| `numpy` | >=1.24.0 | Numerical operations | Price array operations |
| `adtk` | 0.6.2 | Time-series anomaly detection | Level shift detection for mistake fares |
| `requests` | >=2.28.0 | HTTP requests | Existing, keep as-is |
| `gspread` | >=5.0.0 | Google Sheets access | Keep during migration, remove after |
| `google-auth` | >=2.0.0 | Google API auth | Keep during migration, remove after |

---

## Installation

```bash
# Core (new)
pip install amadeus resend supabase libsql-experimental scipy numpy adtk

# Existing (keep)
pip install fast-flights feedparser requests

# Migration period (remove after Supabase migration)
pip install gspread google-auth
```

---

## Phased Adoption Recommendation

### Phase 1: Database + Email (lowest risk, highest impact)
- Migrate price_history.jsonl to Turso
- Switch email delivery from Gmail SMTP to Resend
- Keep everything else the same
- **Cost change:** $0/month (both on free tiers)

### Phase 2: Amadeus Integration
- Add Amadeus API credentials
- Implement tiered route monitoring (priority routes every 2 hours)
- Keep fast-flights for Tier 3 daily scans
- **Cost change:** $0-15/month

### Phase 3: Anomaly Detection
- Implement rolling z-score on accumulated price data
- Add level shift detection for mistake fare discovery
- Requires: 2-3 months of Turso price data first
- **Cost change:** $0/month

### Phase 4: Subscriber Management
- Migrate Google Sheets subscribers to Supabase
- Add subscriber preferences (origin region, destination region)
- Implement freemium tier logic
- **Cost change:** $0/month (Supabase free tier)

### Phase 5: Business/First Class
- Add Amadeus Flight Offers Search for premium cabins on Tier 1 routes
- Premium-only feature for paid subscribers
- **Cost change:** +$5-10/month in Amadeus calls

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Flight data strategy (hybrid) | MEDIUM-HIGH | Amadeus pricing verified via multiple sources; exact free quotas need login confirmation |
| Database (Turso) | HIGH | Free tier limits verified (500M reads, 10M writes, 5GB); pricing page confirmed |
| Email (Resend) | HIGH | Pricing verified on official page (3K free, $20/50K Pro) |
| Scheduling (GitHub Actions) | HIGH | Pricing confirmed free for public repos; 2026 changes documented |
| Anomaly detection (scipy/ADTK) | HIGH | Well-established statistical methods; ADTK stable at 0.6.2 |
| Subscriber mgmt (Supabase) | HIGH | Free tier verified (50K MAU, 500MB); auth built-in |
| fast-flights reliability | MEDIUM | Scraping can break; fli is newer alternative but less tested |
| Kiwi/Skyscanner access | LOW | Both have restricted access; not recommended |

---

## Sources

### Flight Data
- [Amadeus Self-Service Pricing](https://developers.amadeus.com/pricing) -- official pricing page
- [Amadeus API Rate Limits](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/api-rate-limits/) -- rate limit docs
- [Amadeus Flight Cheapest Date Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search) -- API docs
- [Amadeus Pricing Guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/pricing/) -- pricing model explained
- [SerpAPI Pricing](https://serpapi.com/pricing) -- pricing comparison (rejected for cost)
- [fli (flights) on GitHub](https://github.com/punitarani/fli) -- fast-flights alternative
- [fli on PyPI](https://pypi.org/project/flights/) -- v0.7.0
- [fast-flights on PyPI](https://pypi.org/project/fast-flights/) -- current scraper
- [Skyscanner Partner Portal](https://www.partners.skyscanner.net/product/travel-api) -- partner access requirements
- [Kiwi Tequila](https://tequila.kiwi.com/) -- restricted access notice
- [Flight API Comparison - Codebridge](https://www.codebridge.tech/articles/top-5-flights-apis-for-travel-apps) -- ecosystem overview

### Database
- [Turso Pricing](https://turso.tech/pricing) -- free tier details
- [Turso Developer Plan](https://turso.tech/blog/turso-cloud-debuts-the-new-developer-plan) -- $4.99/month plan
- [Turso Free Tier Infographic](https://www.freetiers.com/directory/turso) -- limits summary
- [Turso vs Supabase](https://bejamas.com/compare/turso-vs-supabase) -- comparison

### Email
- [Resend Pricing](https://resend.com/pricing) -- official pricing
- [Resend Free Tier Details](https://resend.com/docs/knowledge-base/account-quotas-and-limits) -- quotas and limits
- [Transactional Email Comparison](https://www.pingram.io/blog/transactional-email-apis) -- multi-provider comparison
- [SendGrid Pricing](https://sendgrid.com/en-us/pricing) -- rejected alternative
- [Postmark Pricing](https://postmarkapp.com/pricing) -- rejected alternative

### Scheduling
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage) -- free tier docs
- [GitHub Actions 2026 Pricing Changes](https://resources.github.com/actions/2026-pricing-changes-for-github-actions/) -- upcoming changes
- [GitHub Actions Limits](https://docs.github.com/en/actions/reference/limits) -- rate limits and timeouts
- [Railway Pricing](https://railway.com/pricing) -- rejected alternative
- [Render Pricing](https://render.com/pricing) -- rejected alternative
- [Railway vs Render Comparison](https://northflank.com/blog/railway-vs-render) -- ecosystem comparison

### Anomaly Detection
- [ADTK Documentation](https://adtk.readthedocs.io/en/stable/) -- library docs
- [ADTK on GitHub](https://github.com/arundo/adtk) -- source code
- [SciPy zscore](https://pythonguides.com/scipy-stats-zscore/) -- scipy implementation
- [Time Series Anomaly Detection Guide](https://www.datasciencewithmarco.com/blog/practical-guide-for-anomaly-detection-in-time-series-with-python) -- practical approaches

### Subscriber Management
- [Supabase vs Firebase Free Tier](https://dev.to/wahee/supabase-vs-firebase-free-tier-2025-which-one-should-you-use-5cmp) -- free tier comparison
- [Supabase Pricing](https://supabase.com/) -- official pricing
- [Supabase Auth Pricing Comparison](https://zuplo.com/learning-center/api-authentication-pricing) -- auth provider comparison
