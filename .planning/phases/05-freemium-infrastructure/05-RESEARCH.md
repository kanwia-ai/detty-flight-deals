# Phase 5: Freemium Infrastructure - Research

**Researched:** 2026-02-10
**Domain:** Subscriber management, tier-based routing, weekly digest generation, SMS delivery, trial management
**Confidence:** HIGH (mostly uses existing stack patterns, well-understood domain)

## Summary

Phase 5 transforms Detty Flight Deals from a "send everything to everyone" system into a segmented freemium service. The core work involves: (1) adding a `subscribers` table to the existing Turso database, (2) building a deal accumulation and weekly digest pipeline, (3) splitting the current "send to all" email path into tier-based routing (free weekly digest vs. premium instant alerts), (4) adding SMS delivery for premium mistake fare alerts via Twilio, and (5) implementing trial management with auto-downgrade.

The existing codebase is well-structured for this. The `db/` package already has TursoClient with retry logic, schema migrations, and the in-memory-sync pattern. The `alert/` package already classifies deals into Great (free) and WOW (premium) tiers. The main work is plumbing: connecting subscriber preferences to deal routing and building the weekly digest accumulation/generation pipeline.

The biggest architectural decision is deal accumulation for the weekly digest. Since the system runs on GitHub Actions (stateless), deals found during the week must be stored in Turso and then batched into a digest on the weekly cron run. This is straightforward with a new `digest_queue` table.

**Primary recommendation:** Extend the existing Turso database with `subscribers` and `digest_queue` tables, build a `subscriber/` package mirroring the `db/` and `alert/` package patterns, and add a new `weekly_digest.yml` GitHub Actions workflow on a Sunday morning cron.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| libsql | >=0.1.11 | Turso database access | Already in use, proven pattern in db/client.py |
| twilio | >=9.0.0 | SMS delivery for mistake fare alerts | Industry standard, Python SDK, pay-per-message |
| gspread | >=5.0.0 | Migration-only: read existing subscribers from Google Sheets | Already in requirements.txt, used by mvp0_sender.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | >=8.0.0 | Retry logic for DB and SMS operations | Already in use in db/client.py |
| smtplib | stdlib | Gmail SMTP email delivery | Already in use, stays until Phase 7 (Resend migration) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Twilio | Plivo ($0.0055/msg vs $0.0083/msg) | Cheaper per-message but less documentation and smaller community; Twilio's $15 free trial credit covers ~1,500 SMS which is months of mistake fare alerts |
| Twilio | Vonage ($0.00809/msg) | Similar pricing to Twilio, less Python ecosystem support |
| Turso subscribers table | Keep Google Sheets + add columns | Sheets has no query capability, rate limits on API, and already hitting complexity ceiling with mvp0_sender.py |

**Installation:**
```bash
pip install twilio>=9.0.0
```
(Add to requirements.txt alongside existing dependencies)

## Architecture Patterns

### Recommended Project Structure
```
subscriber/
    __init__.py          # Export SubscriberManager, AlertRouter
    manager.py           # CRUD operations on subscribers table
    router.py            # Route deals to correct subscribers by tier/metro
    digest.py            # Weekly digest generation (accumulate + format)
    trial.py             # Trial start/expiry tracking
    metro_groups.py      # Metro group definitions and airport mapping
    migration.py         # One-time Google Sheets -> Turso migration script

db/
    schema.py            # ADD: subscribers table, digest_queue table schemas
    client.py            # ADD: subscriber CRUD methods, digest queue methods

alert/
    templates.py         # ADD: weekly digest HTML template, FOMO teaser template

.github/workflows/
    weekly_digest.yml    # NEW: Sunday morning cron for free tier digest
    trial_check.yml      # NEW: Daily check for expired trials (or combine with digest)
```

### Pattern 1: Subscriber Data Model (Flat Table with JSON Preferences)
**What:** Single `subscribers` table with metro preferences stored as JSON text column.
**When to use:** When preference data is small, rarely queried independently, and the subscriber count is <1000.
**Why not a separate table:** With only 6 metro groups and 200 subscribers, a join table adds complexity without benefit. JSON column keeps reads simple (one query per subscriber) and SQLite's json_extract() can filter when needed.

```sql
-- Source: Turso docs + existing db/schema.py patterns
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    tier TEXT NOT NULL DEFAULT 'free',           -- 'free', 'premium', 'trial'
    metro_group TEXT DEFAULT NULL,               -- Free: single metro e.g. 'NYC'
    metro_groups_json TEXT DEFAULT NULL,          -- Premium: JSON array e.g. '["NYC","DC","ATL"]'
    dest_regions_json TEXT DEFAULT NULL,          -- Premium: JSON array e.g. '["West","Central"]'
    trial_start TEXT DEFAULT NULL,               -- ISO timestamp when trial started
    trial_expiry TEXT DEFAULT NULL,              -- ISO timestamp when trial expires
    premium_start TEXT DEFAULT NULL,             -- ISO timestamp when premium activated
    premium_expiry TEXT DEFAULT NULL,            -- ISO timestamp when quarterly payment expires
    payment_reminder_sent TEXT DEFAULT NULL,     -- ISO timestamp of last payment reminder
    metro_change_date TEXT DEFAULT NULL,         -- ISO timestamp of last metro change (free tier: once/month)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 1            -- Soft delete / unsubscribe flag
);

CREATE INDEX IF NOT EXISTS idx_subscribers_tier ON subscribers(tier);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(active);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
```

### Pattern 2: Deal Accumulation Queue for Weekly Digest
**What:** Store deals found during the week in a `digest_queue` table. The weekly cron reads, groups by subscriber, generates personalized digests, then clears the queue.
**When to use:** Stateless execution environments (GitHub Actions) where you cannot accumulate state in memory across runs.

```sql
-- Deals waiting to be included in the next weekly digest
CREATE TABLE IF NOT EXISTS digest_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,                    -- e.g. "JFK-LOS"
    origin TEXT NOT NULL,                   -- e.g. "JFK"
    dest TEXT NOT NULL,                     -- e.g. "LOS"
    dest_name TEXT NOT NULL,               -- e.g. "Lagos"
    price_cents INTEGER NOT NULL,
    tier TEXT NOT NULL,                     -- "great" (free content) or "wow"/"mistake" (teaser content)
    deal_data_json TEXT NOT NULL,           -- Full deal dict as JSON for template rendering
    found_at TEXT NOT NULL DEFAULT (datetime('now')),
    digest_sent INTEGER NOT NULL DEFAULT 0, -- 0=pending, 1=included in digest
    expired INTEGER NOT NULL DEFAULT 0      -- 1=deal has expired (for FOMO teasers)
);

CREATE INDEX IF NOT EXISTS idx_digest_queue_pending
    ON digest_queue(digest_sent, tier);
```

### Pattern 3: Alert Routing (Tier-Based Dispatch)
**What:** After a deal is classified by the FSM, route it to the correct delivery channel based on subscriber tier and preferences.
**When to use:** Every time a deal triggers an alert.

```python
# Pseudocode for alert routing pattern
def route_deal(deal, subscribers, sms_client):
    origin_metro = AIRPORT_TO_METRO[deal["origin"]]  # e.g. JFK -> NYC

    if deal["tier"] in ("wow", "mistake"):
        # Premium: instant email + SMS for mistake fares
        premium_subs = [s for s in subscribers
                        if s["tier"] in ("premium", "trial")
                        and origin_metro in get_metros(s)]
        send_instant_alert(deal, premium_subs)

        if deal.get("is_mistake_fare"):
            send_sms_alert(deal, premium_subs, sms_client)

        # Also queue for free tier FOMO teaser
        queue_for_digest(deal, is_teaser=True)

    elif deal["tier"] == "great":
        # Free tier: queue for weekly digest
        queue_for_digest(deal, is_teaser=False)

        # Premium: also send instant
        premium_subs = [s for s in subscribers
                        if s["tier"] in ("premium", "trial")
                        and origin_metro in get_metros(s)]
        send_instant_alert(deal, premium_subs)
```

### Pattern 4: Metro Group Mapping
**What:** Map airport codes to metro groups for subscriber filtering.
**When to use:** Every subscriber lookup and deal routing operation.

```python
# Metro group definitions (from CONTEXT.md decisions)
METRO_GROUPS = {
    "NYC": ["JFK", "EWR"],
    "DC": ["IAD"],
    "ATL": ["ATL"],
    "HOU": ["IAH"],
    "CHI": ["ORD"],
    "LA": ["LAX"],
}

# Reverse mapping: airport -> metro
AIRPORT_TO_METRO = {}
for metro, airports in METRO_GROUPS.items():
    for airport in airports:
        AIRPORT_TO_METRO[airport] = metro

# NOTE: Current ORIGINS list includes DFW and BOS which are NOT in metro groups.
# DFW maps to Dallas (no metro group defined). BOS maps to Boston (no metro group).
# These airports will need to either:
# (a) Be added as new metro groups: "DFW": ["DFW"], "BOS": ["BOS"]
# (b) Be removed from ORIGINS if they don't align with subscriber metros
# RECOMMENDATION: Add DFW and BOS as their own metro groups for now.
# They can be consolidated later if subscriber demand warrants it.
```

### Anti-Patterns to Avoid
- **Sending individual SMTP connections per subscriber in a loop:** Gmail SMTP has 100/day limit. Batch all free-tier emails in the weekly digest (1 email per subscriber = max ~200 emails in one run). Add 0.5s delay between sends to avoid rate limiting. This is exactly what mvp0_sender.py already does.
- **Querying subscribers table for every deal:** Load all active subscribers once per workflow run, filter in Python. At 200 subscribers, this is a single small query.
- **Storing metro preferences as separate rows:** With only 6 metro groups and <1000 subscribers, a JSON column is simpler than a junction table. Use json_extract() in SQL only if you need to query by metro (rare).
- **Running digest generation inline with deal finding:** The weekly digest is a separate workflow. deal_finder.py and amadeus_monitor.py queue deals; weekly_digest.py reads the queue and sends.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SMS delivery | Custom HTTP to carrier APIs | Twilio Python SDK (`twilio` package) | Carrier routing, delivery receipts, number formatting, compliance (10DLC registration) |
| Email HTML templates | String concatenation soup | Extend existing `alert/templates.py` pattern | Consistency with current codebase, inline CSS for email compatibility |
| Cron scheduling | Custom date logic for "is it Sunday?" | GitHub Actions cron `0 14 * * 0` | Reliable, already in use for other workflows, no state to manage |
| Retry logic | Custom try/except loops | `tenacity` (already in use) | Exponential backoff, configurable stop conditions, already proven in db/client.py |
| Schema migrations | Manual ALTER TABLE | Extend existing `run_migrations()` in db/schema.py | Already handles column existence checks with PRAGMA table_info |
| Google Sheets reading | Custom HTTP to Sheets API | `gspread` (already in use) | Already works in mvp0_sender.py, only needed for one-time migration |

**Key insight:** Almost everything in this phase extends existing patterns. The codebase already has: TursoClient with retry logic, schema migrations, Gmail SMTP sending with subscriber loops, alert templates with tier-based formatting. Phase 5 is primarily plumbing and new tables, not new technology.

## Common Pitfalls

### Pitfall 1: Gmail 100/Day Limit Collision
**What goes wrong:** Weekly digest (up to 200 free subscribers) + instant premium alerts (maybe 20-50) could exceed Gmail's 100/day SMTP limit on a day with both a digest run and a WOW deal.
**Why it happens:** Digest runs on Sunday, a WOW deal also fires on Sunday, total exceeds 100.
**How to avoid:** Track email send count per day in Turso. If approaching 90, defer non-urgent sends. Alternatively, run the digest at a time when instant alerts are unlikely (early Sunday morning UTC). At current scale (<200 subscribers), split: digest first (all free users), then premium alerts have remaining quota. Phase 7 (Resend migration) permanently solves this.
**Warning signs:** Failed SMTP sends, "Daily user sending limit exceeded" errors in logs.

### Pitfall 2: Trial Expiry Drift
**What goes wrong:** Trial expires but subscriber keeps getting premium content because the check only runs weekly.
**Why it happens:** Trial is 7 days but the check is in the weekly digest cron (runs once/week). If trial started on Tuesday and digest runs Sunday, trial could run 5-12 days.
**How to avoid:** Check trial expiry at the point of sending, not on a separate cron. In `router.py`, when filtering premium subscribers, check `trial_expiry < now()` and auto-downgrade. This makes the check lazy but accurate -- no separate cron needed.
**Warning signs:** Free-tier subscribers receiving WOW/mistake fare instant alerts.

### Pitfall 3: Metro Group Mismatch with ORIGINS
**What goes wrong:** DFW and BOS are in the current ORIGINS list but not in the CONTEXT.md metro groups. Deals from these airports won't match any subscriber's metro preference.
**Why it happens:** Metro groups were defined as NYC, DC, ATL, HOU, CHI, LA -- but ORIGINS includes DFW (Dallas) and BOS (Boston).
**How to avoid:** Either add DFW and BOS as metro groups (recommended) or remove them from ORIGINS. Decision should be explicit. The metro_groups.py module should raise a warning if a deal's origin airport has no metro mapping.
**Warning signs:** Deals found for DFW/BOS routes that are never delivered to any subscriber.

### Pitfall 4: Digest Queue Growing Unbounded
**What goes wrong:** If the weekly digest workflow fails (GitHub Actions outage, bug), the queue keeps growing. Next successful run sends a massive email with 2+ weeks of deals.
**Why it happens:** No cleanup mechanism for old queue entries.
**How to avoid:** Add a `found_at` filter: only include deals from the past 7 days in the digest. Mark older entries as expired (useful for FOMO teasers). Add a `MAX_DIGEST_DEALS` cap (e.g., 15 deals per digest).
**Warning signs:** Digest emails with 30+ deals, very long email bodies.

### Pitfall 5: Migration Data Loss
**What goes wrong:** Subscribers in Google Sheets are not migrated to Turso, or are duplicated.
**Why it happens:** Running migration script multiple times, or Google Sheets columns change.
**How to avoid:** Migration script should be idempotent (use INSERT OR IGNORE on email UNIQUE constraint). Run migration, then compare counts: Sheets rows vs. Turso rows. Keep Google Sheets as read-only backup for 30 days after migration.
**Warning signs:** Subscriber count mismatch between Sheets and Turso.

### Pitfall 6: Twilio 10DLC Registration
**What goes wrong:** SMS messages are filtered or blocked by carriers because the sending number isn't registered for A2P (application-to-person) messaging.
**Why it happens:** US carriers require 10DLC registration for business SMS. Unregistered numbers face throttling and filtering.
**How to avoid:** Register the Twilio number for 10DLC campaign (costs ~$15 one-time + $2/month). Alternatively, use a toll-free number ($2.15/month) which has simpler verification. For the low volume expected (<50 SMS/month), a toll-free number is simplest.
**Warning signs:** SMS delivery rate below 90%, messages not arriving.

## Code Examples

Verified patterns from the existing codebase and official documentation:

### Adding Subscribers Table to Schema
```python
# In db/schema.py - extend SCHEMA_SQL
# Source: existing db/schema.py pattern

SUBSCRIBERS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    tier TEXT NOT NULL DEFAULT 'free',
    metro_group TEXT DEFAULT NULL,
    metro_groups_json TEXT DEFAULT NULL,
    dest_regions_json TEXT DEFAULT NULL,
    trial_start TEXT DEFAULT NULL,
    trial_expiry TEXT DEFAULT NULL,
    premium_start TEXT DEFAULT NULL,
    premium_expiry TEXT DEFAULT NULL,
    payment_reminder_sent TEXT DEFAULT NULL,
    metro_change_date TEXT DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    active INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_subscribers_tier ON subscribers(tier);
CREATE INDEX IF NOT EXISTS idx_subscribers_active ON subscribers(active);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

CREATE TABLE IF NOT EXISTS digest_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    dest_name TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    tier TEXT NOT NULL,
    deal_data_json TEXT NOT NULL,
    found_at TEXT NOT NULL DEFAULT (datetime('now')),
    digest_sent INTEGER NOT NULL DEFAULT 0,
    expired INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_digest_queue_pending
    ON digest_queue(digest_sent, tier);
"""
```

### TursoClient Subscriber Methods
```python
# In db/client.py - extend TursoClient class
# Source: existing db/client.py pattern (record_observation, get_cache, etc.)

def get_active_subscribers(self, tier: str = None) -> list[dict]:
    """Get active subscribers, optionally filtered by tier."""
    if not self._turso_available:
        return []
    try:
        if tier:
            rows = self._conn.execute(
                "SELECT * FROM subscribers WHERE active = 1 AND tier = ?",
                (tier,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM subscribers WHERE active = 1"
            ).fetchall()
        # Convert to dicts using column names
        columns = [desc[0] for desc in self._conn.execute(
            "PRAGMA table_info(subscribers)"
        ).fetchall()]
        # PRAGMA returns (cid, name, type, notnull, dflt_value, pk)
        col_names = [row[1] for row in self._conn.execute(
            "PRAGMA table_info(subscribers)"
        ).fetchall()]
        return [dict(zip(col_names, row)) for row in rows]
    except Exception as e:
        logger.error(f"[DB] get_active_subscribers failed: {e}")
        return []

def queue_deal_for_digest(self, deal: dict) -> bool:
    """Add a deal to the weekly digest queue."""
    if not self._turso_available:
        return False
    import json
    def do_insert():
        self._conn.execute(
            """INSERT INTO digest_queue
               (route, origin, dest, dest_name, price_cents, tier, deal_data_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (deal["route"], deal["origin"], deal["dest"],
             deal["dest_name"], deal["price_cents"], deal["tier"],
             json.dumps(deal)),
        )
        self._conn.commit()
        self._conn.sync()
    return self._execute_with_fallback(do_insert)
```

### Twilio SMS Alert
```python
# Source: Twilio Python SDK quickstart (https://www.twilio.com/docs/messaging/quickstart)
import os
from twilio.rest import Client

def send_sms_alert(phone: str, deal: dict) -> bool:
    """Send SMS for mistake fare deal to premium subscriber."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("[SMS] Twilio credentials not configured")
        return False

    try:
        client = Client(account_sid, auth_token)
        price = deal["price_cents"] // 100
        message = client.messages.create(
            body=(
                f"MISTAKE FARE: {deal['dest_name']} ${price} from {deal['origin']}! "
                f"Book NOW before it disappears. {deal.get('url', '')}"
            ),
            from_=from_number,
            to=phone,
        )
        logger.info(f"[SMS] Sent to {phone}: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"[SMS] Failed to send to {phone}: {e}")
        return False
```

### Google Sheets Migration Script
```python
# One-time migration: Google Sheets -> Turso subscribers table
# Source: existing mvp0_sender.py get_subscribers() pattern
import json
from mvp0_sender import get_subscribers
from db import TursoClient

def migrate_subscribers():
    """Migrate all subscribers from Google Sheets to Turso."""
    emails = get_subscribers()  # Returns list of email strings
    db = TursoClient()

    if not db._turso_available:
        print("ERROR: Turso not available")
        return

    migrated = 0
    skipped = 0
    for email in emails:
        try:
            db._conn.execute(
                """INSERT OR IGNORE INTO subscribers (email, tier, active)
                   VALUES (?, 'free', 1)""",
                (email,),
            )
            # Check if inserted or ignored
            result = db._conn.execute(
                "SELECT changes()"
            ).fetchone()
            if result and result[0] > 0:
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"Error migrating {email}: {e}")

    db._conn.commit()
    db._conn.sync()
    print(f"Migrated: {migrated}, Skipped (duplicates): {skipped}")
    print(f"Total in Turso: {db._conn.execute('SELECT COUNT(*) FROM subscribers').fetchone()[0]}")
```

### Weekly Digest GitHub Actions Workflow
```yaml
# .github/workflows/weekly_digest.yml
name: Weekly Free Tier Digest

on:
  schedule:
    - cron: '0 14 * * 0'  # Sunday 2PM UTC (10AM ET / 7AM PT)
  workflow_dispatch:

jobs:
  send-digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - name: Generate and send weekly digest
        env:
          TURSO_DATABASE_URL: ${{ secrets.TURSO_DATABASE_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
          SMTP_EMAIL: ${{ secrets.SMTP_EMAIL }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
        run: python -m subscriber.digest
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Sheets subscribers | Turso database subscribers | Phase 5 | Queryable, supports tier/preferences, eliminates gspread dependency |
| Send all deals to all users | Tier-based routing (free/premium) | Phase 5 | Enables freemium model |
| No SMS | Twilio SMS for mistake fares | Phase 5 | Premium value prop, time-sensitive alerts |
| Instant email for every deal | Free: weekly digest / Premium: instant | Phase 5 | Reduces free tier email volume, creates urgency for premium |
| Gmail SMTP only (100/day) | Gmail SMTP + Twilio SMS | Phase 5 | SMS adds a channel; Gmail limit still constraining until Phase 7 |

**Deprecated/outdated:**
- `mvp0_sender.py` `get_subscribers()`: Will be replaced by TursoClient subscriber queries after migration. Keep as fallback during migration period.
- Google Sheets subscriber storage: Becomes read-only backup after migration, can be removed after 30 days.

## Open Questions

Things that couldn't be fully resolved:

1. **Phone number collection for SMS**
   - What we know: Premium subscribers need a phone number for SMS alerts. Current Google Sheets signup only collects email.
   - What's unclear: How to collect phone numbers from existing subscribers. A form/email asking for phone numbers? Add to signup flow?
   - Recommendation: Add a `phone` column to subscribers table. For existing subscribers, send an email asking them to reply with their phone number when they upgrade to premium. For new premium subscribers, collect at signup.

2. **Twilio 10DLC vs. Toll-Free**
   - What we know: US carriers require registration for A2P messaging. 10DLC costs ~$15 registration + $2/month. Toll-free costs $2.15/month with simpler verification.
   - What's unclear: Whether toll-free verification will be approved for a small flight deals service.
   - Recommendation: Start with toll-free number (simpler). If messages get filtered, switch to 10DLC.

3. **DFW and BOS Metro Group Mapping**
   - What we know: ORIGINS includes DFW and BOS but CONTEXT.md metro groups only define NYC, DC, ATL, HOU, CHI, LA.
   - What's unclear: Whether these airports should become their own metro groups or be removed.
   - Recommendation: Add "DFW" (Dallas) and "BOS" (Boston) as metro groups. They serve real diaspora populations and are already monitored.

4. **Payment Reminder Scheduling**
   - What we know: Premium is $15/quarter via manual Venmo/Zelle. Automated email reminders needed before renewal.
   - What's unclear: Exact timing of reminders (7 days before? 3 days? day-of?).
   - Recommendation: Send reminders at 7 days and 1 day before premium_expiry. Can run in the weekly digest workflow (check upcoming expirations each Sunday) or a lightweight daily check.

5. **Free Tier Metro Selection UX**
   - What we know: Free users pick 1 metro at signup, can change once per month.
   - What's unclear: How the metro selection happens (reply to email? Google Form? future web UI?).
   - Recommendation: For MVP, set metro in the migration script based on proximity/self-report. Add a simple "reply with your city" mechanism in the welcome email. Store `metro_change_date` to enforce once-per-month limit.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `db/client.py`, `db/schema.py` -- Turso connection pattern, schema migration pattern, retry logic
- Existing codebase: `mvp0_sender.py` -- Current subscriber management, email sending pattern
- Existing codebase: `alert/state_machine.py`, `alert/templates.py` -- Deal tier classification, email formatting
- Existing codebase: `deal_finder.py` -- Current deal routing and email dispatch
- [Turso Python Quickstart](https://docs.turso.tech/sdk/python/quickstart) -- libsql connect/execute/sync API
- [Twilio SMS Quickstart](https://www.twilio.com/docs/messaging/quickstart) -- Python SDK message.create() pattern
- [Twilio US SMS Pricing](https://www.twilio.com/en-us/sms/pricing/us) -- $0.0083/message + carrier fees

### Secondary (MEDIUM confidence)
- [Twilio Free Trial Limitations](https://support.twilio.com/hc/en-us/articles/360036052753-Twilio-Free-Trial-Limitations) -- $15 credits, verified numbers only
- [GitHub Actions Cron Scheduling](https://cicube.io/blog/github-actions-cron/) -- Cron syntax for weekly workflows
- [SQLite JSON Functions](https://www.sqlite.org/json1.html) -- json_extract() for querying JSON columns
- [Google Sheets to SQLite Migration](https://www.geeksforgeeks.org/python/store-google-sheets-data-into-sqlite-database-using-python/) -- gspread + sqlite3 migration pattern

### Tertiary (LOW confidence)
- SMS provider comparison (WebSearch only): Plivo at $0.0055/msg may be cheaper alternative to Twilio
- 10DLC registration requirements may evolve; check current Twilio documentation at implementation time

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Uses existing codebase patterns (Turso, Gmail SMTP) plus well-documented Twilio SDK
- Architecture: HIGH - Extends proven patterns from db/ and alert/ packages; digest queue is a standard batch pattern
- Pitfalls: HIGH - Gmail limit is a known constraint; metro mapping gap is visible in code; trial drift is a common timing bug
- SMS delivery: MEDIUM - Twilio is standard but 10DLC/toll-free registration requirements may need verification at implementation time
- Migration: HIGH - gspread already works, Turso already works, just connecting them

**Research date:** 2026-02-10
**Valid until:** 2026-03-10 (30 days -- stable domain, no fast-moving dependencies)
