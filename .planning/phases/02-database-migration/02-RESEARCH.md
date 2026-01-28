# Phase 2: Database Migration - Research

**Researched:** 2026-01-28
**Domain:** Turso/libSQL database integration, Python, GitHub Actions
**Confidence:** HIGH

## Summary

This phase migrates from JSON file storage (`seen_deals.json`, `price_cache.json`, `price_history.jsonl`) to a Turso database using libSQL. Turso is a SQLite-compatible database accessible over HTTPS, making it ideal for GitHub Actions' ephemeral environment. The migration uses a dual-write strategy: write to both JSON and Turso for one week, with JSON remaining source of truth until validation passes.

The standard stack is the `libsql` package (v0.1.11, released September 2025) which provides a synchronous Python API compatible with Python's built-in sqlite3 module. This replaces the older `libsql-client` package (archived). Connection uses `sync_url` for remote Turso databases with HTTPS access. Since SQLite lacks native materialized views, the "price_cache" will be implemented as a regular table updated via application logic on each write.

**Primary recommendation:** Use the `libsql` package with synchronous API, implement retry logic with `tenacity` for graceful degradation, and create a `TursoClient` wrapper class that handles both Turso writes and JSON fallback transparently.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| libsql | 0.1.11 | Turso/libSQL Python bindings | Official Turso SDK, replaces archived libsql-client |
| tenacity | 8.x | Retry logic with exponential backoff | Industry standard for resilient database operations |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.x | Environment variable loading | Local development, loading TURSO_* env vars |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| libsql | libsql-client | libsql-client is archived, libsql is actively maintained |
| libsql | SQLAlchemy + libsql dialect | Overkill for simple CRUD, adds complexity |
| tenacity | Custom retry | tenacity is battle-tested, handles edge cases |

**Installation:**
```bash
pip install libsql tenacity python-dotenv
```

## Architecture Patterns

### Recommended Project Structure
```
detty-flight-deals/
├── db/
│   ├── __init__.py
│   ├── client.py          # TursoClient wrapper with fallback
│   ├── schema.py          # CREATE TABLE statements
│   └── migrations/        # Schema migration scripts
├── price_tracker.py       # Modified to use TursoClient
├── deal_finder.py         # Modified to use TursoClient
└── amadeus_monitor.py     # No changes needed (uses price_tracker)
```

### Pattern 1: TursoClient Wrapper with Fallback
**What:** A client class that wraps Turso operations and falls back to JSON on failure
**When to use:** All database operations in this codebase
**Example:**
```python
# Source: https://docs.turso.tech/sdk/python/quickstart
import os
import json
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class TursoClient:
    """
    Database client with Turso primary, JSON fallback.

    Dual-write mode: writes to both Turso and JSON during migration.
    Fallback mode: if Turso unreachable, silently falls back to JSON.
    """

    def __init__(self, dual_write: bool = True):
        self.dual_write = dual_write
        self._turso_available = False
        self._conn = None
        self._init_turso()

    def _init_turso(self):
        """Initialize Turso connection if credentials available."""
        url = os.getenv("TURSO_DATABASE_URL")
        token = os.getenv("TURSO_AUTH_TOKEN")

        if not url or not token:
            print("[DB] Turso credentials not configured, using JSON only")
            return

        try:
            import libsql
            # Use in-memory local cache, sync to remote
            self._conn = libsql.connect(":memory:", sync_url=url, auth_token=token)
            self._conn.sync()
            self._turso_available = True
            print("[DB] Turso connection established")
        except Exception as e:
            print(f"[DB] Turso init failed: {e}, using JSON fallback")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    def _execute_turso(self, sql: str, params: tuple = ()):
        """Execute SQL with retry logic."""
        if not self._turso_available:
            raise ConnectionError("Turso not available")
        self._conn.execute(sql, params)
        self._conn.commit()
        self._conn.sync()
```

### Pattern 2: Simulated Materialized View
**What:** A regular table updated on each write (SQLite has no native materialized views)
**When to use:** The price_cache "view" that replaces seen_deals.json
**Example:**
```python
# Source: SQLite documentation + application logic pattern
# SQLite doesn't have materialized views, so we maintain a cache table manually

def refresh_price_cache(conn, route: str, price: int, tier: str, dest_name: str):
    """
    Update price_cache table after inserting observation.

    Replaces the row for this route if new price is lower,
    or inserts if route not cached. This mimics a materialized
    view of MIN(price) per route.
    """
    # Upsert pattern for SQLite (INSERT OR REPLACE)
    conn.execute("""
        INSERT OR REPLACE INTO price_cache
        (route, price, tier, dest_name, last_seen)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, (route, price, tier, dest_name))
    conn.commit()
```

### Pattern 3: Dual-Write Migration
**What:** Write to both JSON and Turso during migration period
**When to use:** During the 1-week validation period
**Example:**
```python
def record_observation(self, route: str, price: int, tier: str, **kwargs):
    """
    Record a price observation to both stores during dual-write.

    JSON remains source of truth until validation passes.
    """
    # Always write to JSON (source of truth during migration)
    self._write_json(route, price, tier, **kwargs)

    # Attempt Turso write (best effort during migration)
    if self.dual_write and self._turso_available:
        try:
            self._write_turso(route, price, tier, **kwargs)
        except Exception as e:
            # Log but don't fail - JSON is source of truth
            print(f"[DB] Turso write failed (using JSON): {e}")
```

### Anti-Patterns to Avoid
- **Connection pooling:** Don't implement connection pooling - GitHub Actions runners are ephemeral, connections won't persist across runs
- **Background sync:** Don't sync in background threads - use synchronous operations for simplicity in GitHub Actions
- **Complex transactions:** Don't use complex multi-statement transactions - keep writes atomic and simple

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic | Custom while loops with sleep | `tenacity` library | Handles exponential backoff, jitter, exception filtering |
| Environment variables | Manual os.getenv everywhere | `python-dotenv` + centralized config | Cleaner, supports .env files for local dev |
| SQLite migrations | Raw SQL scripts | Schema version table + migration functions | Trackable, reversible, testable |

**Key insight:** The `tenacity` library handles retry edge cases (thundering herd, exception filtering, logging) that are easy to get wrong in custom implementations.

## Common Pitfalls

### Pitfall 1: Using libsql-client Instead of libsql
**What goes wrong:** Import errors, missing features, no maintenance
**Why it happens:** Old tutorials reference libsql-client, which is now archived
**How to avoid:** Use `pip install libsql`, import as `import libsql`
**Warning signs:** ImportError, GitHub repo says "archived"

### Pitfall 2: Forgetting to Call sync()
**What goes wrong:** Data written locally never reaches Turso cloud
**Why it happens:** libsql uses local cache, must explicitly sync to remote
**How to avoid:** Call `conn.sync()` after every commit in GitHub Actions
**Warning signs:** Data appears in local testing but not in Turso dashboard

### Pitfall 3: SQLite Type Mismatches
**What goes wrong:** Unexpected data truncation or type coercion
**Why it happens:** SQLite has flexible typing, Turso inherits this
**How to avoid:** Use explicit types: TEXT for strings, INTEGER for cents (not float), TEXT for ISO timestamps
**Warning signs:** Prices stored as floats causing rounding errors

### Pitfall 4: No Graceful Degradation
**What goes wrong:** Entire monitoring pipeline fails when Turso is down
**Why it happens:** Not handling connection failures
**How to avoid:** Wrap all Turso operations in try/except, fall back to JSON
**Warning signs:** GitHub Actions workflow failures during Turso outages

### Pitfall 5: Blocking on Turso During Fallback
**What goes wrong:** Slow retries when Turso is down delay the whole run
**Why it happens:** Retry logic with long waits
**How to avoid:** Limit retries to 3 attempts with max 10s total wait
**Warning signs:** GitHub Actions runs taking 5+ minutes longer than normal

## Code Examples

Verified patterns from official sources:

### Database Connection (Remote Turso)
```python
# Source: https://docs.turso.tech/sdk/python/quickstart
import libsql
import os

url = os.getenv("TURSO_DATABASE_URL")      # e.g., libsql://your-db.turso.io
auth_token = os.getenv("TURSO_AUTH_TOKEN")

# Connect with remote sync
conn = libsql.connect("local.db", sync_url=url, auth_token=auth_token)
conn.sync()  # Pull remote state

# Execute queries
conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)")
conn.execute("INSERT INTO users (id) VALUES (?)", (1,))
conn.commit()
conn.sync()  # Push to remote
```

### Schema for price_observations
```sql
-- Append-only table for all price observations
CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,              -- e.g., "JFK-LOS"
    date_checked TEXT NOT NULL,       -- ISO timestamp of observation
    travel_date TEXT NOT NULL,        -- Departure date
    return_date TEXT,                 -- Return date (nullable for one-way)
    price_cents INTEGER NOT NULL,     -- Price in cents (avoid float rounding)
    source TEXT NOT NULL,             -- e.g., "amadeus_cheapest_date"
    cabin_class TEXT DEFAULT 'economy',
    tier_at_time TEXT                 -- Deal tier when observed (good/great/wow)
);

-- Indexes for historical queries (Phase 3 anomaly detection)
CREATE INDEX IF NOT EXISTS idx_observations_route_date
    ON price_observations(route, date_checked);
CREATE INDEX IF NOT EXISTS idx_observations_route_travel
    ON price_observations(route, travel_date);
```

### Schema for price_cache
```sql
-- Replaces seen_deals.json - current lowest price per route/tier
CREATE TABLE IF NOT EXISTS price_cache (
    route TEXT NOT NULL,              -- e.g., "JFK-LOS"
    tier TEXT NOT NULL,               -- good/great/wow
    price_cents INTEGER NOT NULL,
    dest_name TEXT NOT NULL,
    last_seen TEXT NOT NULL,          -- ISO timestamp
    PRIMARY KEY (route, tier)
);
```

### Schema for alert_state
```sql
-- FSM state per route for alert cooldowns
CREATE TABLE IF NOT EXISTS alert_state (
    route TEXT PRIMARY KEY,           -- e.g., "JFK-LOS"
    current_tier TEXT,                -- Current deal tier (null if no active deal)
    cooldown_expiry TEXT,             -- ISO timestamp when cooldown ends
    consecutive_normal_count INTEGER DEFAULT 0
);
```

### Retry with Tenacity
```python
# Source: https://tenacity.readthedocs.io/
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError))
)
def sync_to_turso(conn):
    """Sync local changes to Turso with retry."""
    conn.sync()
```

### Dual-Write Validation Check
```python
def validate_dual_write(json_path: Path, turso_conn) -> dict:
    """
    Compare JSON and Turso state for validation.

    Returns dict with:
        - matches: bool
        - json_count: int
        - turso_count: int
        - discrepancies: list of differing keys
    """
    import json

    # Load JSON state
    with open(json_path) as f:
        json_data = json.load(f)

    # Query Turso state
    result = turso_conn.execute(
        "SELECT route || '-' || tier as key, price_cents FROM price_cache"
    ).fetchall()
    turso_data = {row[0]: row[1] for row in result}

    # Compare
    discrepancies = []
    for key, json_entry in json_data.items():
        json_price = json_entry.get("price", 0) * 100  # Convert to cents
        turso_price = turso_data.get(key)
        if turso_price != json_price:
            discrepancies.append({
                "key": key,
                "json_price": json_price,
                "turso_price": turso_price
            })

    return {
        "matches": len(discrepancies) == 0,
        "json_count": len(json_data),
        "turso_count": len(turso_data),
        "discrepancies": discrepancies
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| libsql-client package | libsql package | June 2025 | libsql-client archived, use libsql |
| WebSocket connections (wss://) | HTTPS connections (libsql://) | 2025 | Simpler for serverless, no persistent connections |
| Separate async/sync clients | Unified sync API with conn.sync() | September 2025 (v0.1.11) | Simpler API, better for GitHub Actions |

**Deprecated/outdated:**
- `libsql-client` (pip package): Archived, replaced by `libsql`
- `libsql-experimental`: Experimental features only, not recommended for production
- WebSocket-based connections (`ws://`, `wss://`): HTTPS is preferred for serverless

## Open Questions

Things that couldn't be fully resolved:

1. **Turso Free Tier Rate Limits**
   - What we know: Free tier includes 500M row reads, 5GB storage
   - What's unclear: Exact rate limits per second/minute for writes
   - Recommendation: Start with current write frequency, monitor Turso dashboard

2. **sync() Call Frequency Optimization**
   - What we know: Must call sync() to push/pull from remote
   - What's unclear: Optimal frequency - after each write vs batched
   - Recommendation: Start with sync() after each commit, optimize if slow

3. **Error Types from libsql**
   - What we know: ConnectionError, TimeoutError are common
   - What's unclear: Complete list of exception types for retry logic
   - Recommendation: Catch broad Exception initially, narrow down based on logs

## Sources

### Primary (HIGH confidence)
- [Turso Python Quickstart](https://docs.turso.tech/sdk/python/quickstart) - Installation, connection, sync() usage
- [libsql PyPI](https://pypi.org/project/libsql/) - Version 0.1.11, September 2025
- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Retry patterns, exponential backoff

### Secondary (MEDIUM confidence)
- [SQLite CREATE VIEW](https://www.sqlite.org/lang_createview.html) - Confirms no native materialized views
- [tursodatabase/libsql-python GitHub](https://github.com/tursodatabase/libsql-python) - Current SDK repository
- [tursodatabase/libsql-client-py GitHub](https://github.com/tursodatabase/libsql-client-py) - Archived status confirmed

### Tertiary (LOW confidence)
- [libsql-python Issue #36](https://github.com/tursodatabase/libsql-python/issues/36) - Feature request for built-in retry (open)
- WebSearch results on dual-write patterns - General patterns, not Turso-specific

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Turso documentation, PyPI verified
- Architecture: HIGH - Patterns from official docs + SQLite standards
- Pitfalls: MEDIUM - Based on SDK documentation, GitHub issues, general SQLite knowledge

**Research date:** 2026-01-28
**Valid until:** 2026-02-28 (30 days - Turso SDK is stable, libsql 0.1.x is recent)
