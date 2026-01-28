"""
Detty Flight Deals - Database Schema
SQL schema definitions for Turso/libSQL database.

Tables:
  - price_observations: Append-only table for all price checks
  - price_cache: Current lowest price per route/tier (replaces seen_deals.json)
  - alert_state: FSM state per route for cooldowns (Phase 4 will use fully)
"""

SCHEMA_SQL = """
-- price_observations: append-only table for all price checks
CREATE TABLE IF NOT EXISTS price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route TEXT NOT NULL,
    date_checked TEXT NOT NULL,
    travel_date TEXT NOT NULL,
    return_date TEXT,
    price_cents INTEGER NOT NULL,
    source TEXT NOT NULL,
    cabin_class TEXT DEFAULT 'economy',
    tier_at_time TEXT
);

CREATE INDEX IF NOT EXISTS idx_observations_route_date
    ON price_observations(route, date_checked);
CREATE INDEX IF NOT EXISTS idx_observations_route_travel
    ON price_observations(route, travel_date);

-- price_cache: replaces seen_deals.json (current lowest price per route/tier)
CREATE TABLE IF NOT EXISTS price_cache (
    route TEXT NOT NULL,
    tier TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    dest_name TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (route, tier)
);

-- alert_state: FSM state per route for cooldowns (Phase 4 will use fully)
CREATE TABLE IF NOT EXISTS alert_state (
    route TEXT PRIMARY KEY,
    current_tier TEXT,
    cooldown_expiry TEXT,
    consecutive_normal_count INTEGER DEFAULT 0
);
"""


def init_schema(conn) -> None:
    """
    Initialize database schema.

    Creates all tables and indexes if they don't exist.
    Uses executescript() to run multiple statements.

    Args:
        conn: Database connection (libsql or sqlite3 compatible)
    """
    conn.executescript(SCHEMA_SQL)
    conn.commit()
