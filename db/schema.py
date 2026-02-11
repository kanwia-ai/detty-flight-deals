"""
Detty Flight Deals - Database Schema
SQL schema definitions for Turso/libSQL database.

Tables:
  - price_observations: Append-only table for all price checks
  - price_cache: Current lowest price per route/tier (replaces seen_deals.json)
  - alert_state: FSM state per route for deal tier tracking and cooldowns
  - subscribers: Freemium subscriber management (free/premium/trial tiers)
  - digest_queue: Weekly digest deal queue for Sunday email batches
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

# Subscribers table: freemium subscriber management
SUBSCRIBERS_SCHEMA_SQL = """
-- subscribers: freemium subscriber management (free/premium/trial tiers)
CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    tier TEXT NOT NULL DEFAULT 'free',
    phone TEXT DEFAULT NULL,
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
"""

# Digest queue table: weekly digest deal queue for Sunday email batches
DIGEST_QUEUE_SCHEMA_SQL = """
-- digest_queue: deals queued for inclusion in weekly digest emails
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

CREATE INDEX IF NOT EXISTS idx_digest_queue_pending ON digest_queue(digest_sent, tier);
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
    conn.executescript(SUBSCRIBERS_SCHEMA_SQL)
    conn.commit()
    conn.executescript(DIGEST_QUEUE_SCHEMA_SQL)
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
