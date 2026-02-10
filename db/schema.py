"""
Detty Flight Deals - Database Schema
SQL schema definitions for Turso/libSQL database.

Tables:
  - price_observations: Append-only table for all price checks
  - price_cache: Current lowest price per route/tier (replaces seen_deals.json)
  - alert_state: FSM state per route for deal tier tracking and cooldowns
"""

import logging

logger = logging.getLogger(__name__)

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

-- alert_state: FSM state per route for deal tier tracking and cooldowns
CREATE TABLE IF NOT EXISTS alert_state (
    route TEXT PRIMARY KEY,
    current_tier TEXT,
    cooldown_expiry TEXT,
    consecutive_normal_count INTEGER DEFAULT 0,
    last_alert_tier TEXT,
    last_alert_price_cents INTEGER
);
"""

# Migration SQL for existing databases (Phase 4: Alert State Machine)
# SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN,
# so we check column existence via PRAGMA table_info before adding.
MIGRATION_COLUMNS = [
    ("alert_state", "last_alert_tier", "TEXT"),
    ("alert_state", "last_alert_price_cents", "INTEGER"),
]


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


def run_migrations(conn) -> None:
    """
    Run idempotent migrations to add new columns to existing tables.

    SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS,
    so we check column existence via PRAGMA table_info before adding.
    Safe to call multiple times -- only adds columns that are missing.

    Args:
        conn: Database connection (libsql or sqlite3 compatible)
    """
    for table, column, col_type in MIGRATION_COLUMNS:
        try:
            existing = conn.execute(f"PRAGMA table_info({table})").fetchall()
            existing_names = {row[1] for row in existing}

            if column not in existing_names:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                conn.commit()
                logger.info(f"[DB] Migration: added {column} to {table}")
            else:
                logger.debug(f"[DB] Migration: {column} already exists in {table}")
        except Exception as e:
            logger.error(f"[DB] Migration failed for {table}.{column}: {e}")
