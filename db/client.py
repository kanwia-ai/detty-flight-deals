"""
Detty Flight Deals - Turso Database Client
Database client with Turso primary, JSON fallback.

Handles:
  - Connection to remote Turso database via libsql
  - Automatic schema initialization
  - Retry logic with exponential backoff
  - Graceful fallback when Turso unavailable

Usage:
    from db import TursoClient

    client = TursoClient()
    if client._turso_available:
        client.record_observation(...)
    else:
        # Handle JSON fallback in caller
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .schema import init_schema, run_migrations

# Configure logging
logger = logging.getLogger(__name__)


class TursoClient:
    """
    Database client with Turso primary, graceful fallback.

    When Turso credentials are missing or connection fails,
    sets _turso_available = False. Callers should check this
    flag and fall back to JSON-based storage.

    Attributes:
        _turso_available (bool): True if connected to Turso, False for fallback
        _conn: Database connection (libsql) or None
    """

    def __init__(self, dual_write: bool = True):
        """
        Initialize Turso client.

        Args:
            dual_write: If True, enables dual-write mode (for migration period).
                       Currently unused but reserved for Phase 2 migration.
        """
        self.dual_write = dual_write
        self._turso_available = False
        self._conn = None
        self._init_turso()
        self._run_migrations()

    def _init_turso(self) -> None:
        """Initialize Turso connection if credentials available."""
        url = os.getenv("TURSO_DATABASE_URL")
        token = os.getenv("TURSO_AUTH_TOKEN")

        if not url or not token:
            logger.warning(
                "[DB] Turso credentials not configured (TURSO_DATABASE_URL, TURSO_AUTH_TOKEN), "
                "using JSON-only mode"
            )
            return

        try:
            import libsql

            # Use in-memory local cache, sync to remote
            # This pattern works well for GitHub Actions ephemeral environment
            self._conn = libsql.connect(":memory:", sync_url=url, auth_token=token)
            self._conn.sync()

            # Initialize schema (creates tables if not exist)
            init_schema(self._conn)
            self._conn.sync()

            self._turso_available = True
            logger.info("[DB] Turso connection established")

        except ImportError:
            logger.error("[DB] libsql package not installed, using JSON fallback")
        except Exception as e:
            logger.error(f"[DB] Turso init failed: {e}, using JSON fallback")

    def _run_migrations(self) -> None:
        """
        Run idempotent migrations to ensure all columns exist.

        Called unconditionally in __init__ after schema initialization.
        Safe to run multiple times -- only adds columns that are missing.
        Skipped silently if Turso is not available.
        """
        if not self._turso_available or not self._conn:
            return

        try:
            run_migrations(self._conn)
            self._conn.sync()
            logger.info("[DB] Migrations check complete")
        except Exception as e:
            logger.error(f"[DB] Migration check failed: {e}")

    # ============================================================
    # RETRY DECORATOR
    # ============================================================

    def _with_retry(self, operation):
        """
        Wrap a database operation with retry logic.

        Uses tenacity for exponential backoff:
          - 3 attempts total
          - Wait 1-10 seconds between attempts
          - Retry on connection/timeout errors
        """
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
            reraise=True,
        )
        def wrapped():
            return operation()

        return wrapped()

    def _execute_with_fallback(self, operation) -> bool:
        """
        Execute a database operation with retry and fallback.

        Returns:
            True if operation succeeded, False if failed (caller should use fallback)
        """
        if not self._turso_available:
            return False

        try:
            self._with_retry(operation)
            return True
        except Exception as e:
            logger.error(f"[DB] Turso operation failed after retries: {e}")
            # Mark as unavailable for this session to avoid repeated failures
            self._turso_available = False
            return False

    # ============================================================
    # CORE METHODS
    # ============================================================

    def record_observation(
        self,
        route: str,
        date_checked: str,
        travel_date: str,
        return_date: Optional[str],
        price_cents: int,
        source: str,
        cabin_class: str = "economy",
        tier: Optional[str] = None,
    ) -> bool:
        """
        Record a price observation.

        Args:
            route: Route string e.g. "JFK-LOS"
            date_checked: ISO timestamp when price was checked
            travel_date: Departure date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD) or None for one-way
            price_cents: Price in cents (not dollars) to avoid float rounding
            source: Data source e.g. "amadeus_cheapest_date"
            cabin_class: Cabin class (default "economy")
            tier: Deal tier when observed ("good", "great", "wow") or None

        Returns:
            True if successfully written to Turso, False otherwise
        """
        if not self._turso_available:
            return False

        def do_insert():
            self._conn.execute(
                """
                INSERT INTO price_observations
                (route, date_checked, travel_date, return_date, price_cents, source, cabin_class, tier_at_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (route, date_checked, travel_date, return_date, price_cents, source, cabin_class, tier),
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_insert)

    def update_cache(
        self,
        route: str,
        tier: str,
        price_cents: int,
        dest_name: str,
    ) -> bool:
        """
        Update price cache (replaces seen_deals.json lookup).

        Uses INSERT OR REPLACE to upsert the cache entry.

        Args:
            route: Route string e.g. "JFK-LOS"
            tier: Deal tier ("good", "great", "wow")
            price_cents: Price in cents
            dest_name: Destination name e.g. "Lagos"

        Returns:
            True if successfully written to Turso, False otherwise
        """
        if not self._turso_available:
            return False

        last_seen = datetime.now().isoformat()

        def do_upsert():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO price_cache
                (route, tier, price_cents, dest_name, last_seen)
                VALUES (?, ?, ?, ?, ?)
                """,
                (route, tier, price_cents, dest_name, last_seen),
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_upsert)

    def get_cache(self, route: str, tier: str) -> Optional[dict]:
        """
        Get cached price for a route/tier.

        Args:
            route: Route string e.g. "JFK-LOS"
            tier: Deal tier ("good", "great", "wow")

        Returns:
            Dict with {route, tier, price_cents, dest_name, last_seen} or None
        """
        if not self._turso_available:
            return None

        try:
            result = self._conn.execute(
                """
                SELECT route, tier, price_cents, dest_name, last_seen
                FROM price_cache
                WHERE route = ? AND tier = ?
                """,
                (route, tier),
            ).fetchone()

            if result:
                return {
                    "route": result[0],
                    "tier": result[1],
                    "price_cents": result[2],
                    "dest_name": result[3],
                    "last_seen": result[4],
                }
            return None

        except Exception as e:
            logger.error(f"[DB] get_cache failed: {e}")
            return None

    def update_alert_state(
        self,
        route: str,
        current_tier: Optional[str],
        cooldown_expiry: Optional[str] = None,
        consecutive_normal_count: int = 0,
        last_alert_tier: Optional[str] = None,
        last_alert_price_cents: Optional[int] = None,
    ) -> bool:
        """
        Update alert state for a route (FSM state tracking).

        Args:
            route: Route string e.g. "JFK-LOS"
            current_tier: Current FSM state name (e.g. "NORMAL", "GREAT_ALERTED")
            cooldown_expiry: ISO timestamp when cooldown ends or None
            consecutive_normal_count: Count of consecutive normal prices
            last_alert_tier: Tier of the last alert sent ("Great", "WOW", "MISTAKE")
            last_alert_price_cents: Price in cents when last alert was sent

        Returns:
            True if successfully written to Turso, False otherwise
        """
        if not self._turso_available:
            return False

        def do_upsert():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO alert_state
                (route, current_tier, cooldown_expiry, consecutive_normal_count,
                 last_alert_tier, last_alert_price_cents)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (route, current_tier, cooldown_expiry, consecutive_normal_count,
                 last_alert_tier, last_alert_price_cents),
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_upsert)

    def get_alert_state(self, route: str) -> Optional[dict]:
        """
        Get alert state for a route.

        Args:
            route: Route string e.g. "JFK-LOS"

        Returns:
            Dict with {route, current_tier, cooldown_expiry, consecutive_normal_count,
            last_alert_tier, last_alert_price_cents} or None
        """
        if not self._turso_available:
            return None

        try:
            result = self._conn.execute(
                """
                SELECT route, current_tier, cooldown_expiry, consecutive_normal_count,
                       last_alert_tier, last_alert_price_cents
                FROM alert_state
                WHERE route = ?
                """,
                (route,),
            ).fetchone()

            if result:
                return {
                    "route": result[0],
                    "current_tier": result[1],
                    "cooldown_expiry": result[2],
                    "consecutive_normal_count": result[3],
                    "last_alert_tier": result[4],
                    "last_alert_price_cents": result[5],
                }
            return None

        except Exception as e:
            logger.error(f"[DB] get_alert_state failed: {e}")
            return None

    def get_price_history(
        self,
        route: str,
        days: int = 90,
        cabin_class: str = "economy"
    ) -> Optional[list]:
        """
        Get price history for a route from price_observations table.

        Used for baseline calculations in anomaly detection. Returns historical
        prices ordered by date_checked (most recent first).

        Args:
            route: Route string e.g. "JFK-LOS"
            days: Number of days of history to retrieve (default 90)
            cabin_class: Cabin class filter (default "economy")

        Returns:
            List of dicts with {date_checked, travel_date, price_cents}
            ordered by date_checked DESC, or None if Turso unavailable.
            Returns empty list if no observations found.

        Example:
            history = client.get_price_history("JFK-LOS", days=90)
            if history is not None:
                prices = pd.Series([obs["price_cents"] for obs in history])
                result = detector.detect(prices)
        """
        if not self._turso_available:
            return None

        try:
            # SQLite datetime function works with ISO format timestamps stored as TEXT
            result = self._conn.execute(
                f"""
                SELECT date_checked, travel_date, price_cents
                FROM price_observations
                WHERE route = ?
                  AND cabin_class = ?
                  AND date_checked >= datetime('now', '-{days} days')
                ORDER BY date_checked DESC
                """,
                (route, cabin_class),
            ).fetchall()

            observations = [
                {
                    "date_checked": row[0],
                    "travel_date": row[1],
                    "price_cents": row[2],
                }
                for row in result
            ]
            return observations

        except Exception as e:
            logger.error(f"[DB] get_price_history failed: {e}")
            return None

    # ============================================================
    # SUBSCRIBER METHODS (Phase 5: Freemium Infrastructure)
    # ============================================================

    def _rows_to_dicts(self, cursor_result, table: str) -> list[dict]:
        """
        Convert raw rows to list of dicts using PRAGMA table_info for column names.

        Args:
            cursor_result: List of row tuples from fetchall()
            table: Table name for PRAGMA lookup

        Returns:
            List of dicts with column names as keys
        """
        try:
            columns = [
                row[1] for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
            ]
            return [dict(zip(columns, row)) for row in cursor_result]
        except Exception as e:
            logger.error(f"[DB] _rows_to_dicts failed for {table}: {e}")
            return []

    def get_active_subscribers(self, tier: str = None) -> list[dict]:
        """
        Get all active subscribers, optionally filtered by tier.

        Args:
            tier: Filter by tier ('free', 'premium', 'trial') or None for all.

        Returns:
            List of subscriber dicts, or empty list on failure.
        """
        if not self._turso_available:
            return []

        try:
            if tier:
                result = self._conn.execute(
                    "SELECT * FROM subscribers WHERE active = 1 AND tier = ?",
                    (tier,),
                ).fetchall()
            else:
                result = self._conn.execute(
                    "SELECT * FROM subscribers WHERE active = 1"
                ).fetchall()

            return self._rows_to_dicts(result, "subscribers")

        except Exception as e:
            logger.error(f"[DB] get_active_subscribers failed: {e}")
            return []

    def add_subscriber(
        self,
        email: str,
        name: str = None,
        tier: str = "free",
        metro_group: str = None,
    ) -> bool:
        """
        Add a new subscriber.

        Uses INSERT OR IGNORE to avoid duplicate email errors.

        Args:
            email: Subscriber email (unique)
            name: Optional display name
            tier: Subscription tier ('free', 'premium', 'trial')
            metro_group: Metro group preference for free tier (e.g. 'NYC')

        Returns:
            True if successfully inserted, False otherwise.
        """
        def do_insert():
            self._conn.execute(
                """
                INSERT OR IGNORE INTO subscribers (email, name, tier, metro_group)
                VALUES (?, ?, ?, ?)
                """,
                (email, name, tier, metro_group),
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_insert)

    def update_subscriber(self, email: str, **kwargs) -> bool:
        """
        Update a subscriber's fields by email.

        Builds a dynamic UPDATE SET clause from kwargs. Only known column
        names are accepted. Always sets updated_at to current timestamp.

        Args:
            email: Subscriber email to update
            **kwargs: Column name/value pairs to update

        Returns:
            True if successfully updated, False otherwise.
        """
        # Whitelist of allowed columns to prevent SQL injection
        allowed_columns = {
            "name", "tier", "phone", "metro_group", "metro_groups_json",
            "dest_regions_json", "trial_start", "trial_expiry",
            "premium_start", "premium_expiry", "payment_reminder_sent",
            "metro_change_date", "active",
        }

        # Filter to only known columns
        updates = {k: v for k, v in kwargs.items() if k in allowed_columns}
        if not updates:
            logger.warning("[DB] update_subscriber: no valid columns provided")
            return False

        # Always update the updated_at timestamp
        updates["updated_at"] = "datetime('now')"

        # Build SET clause
        set_parts = []
        params = []
        for col, val in updates.items():
            if val == "datetime('now')":
                set_parts.append(f"{col} = datetime('now')")
            else:
                set_parts.append(f"{col} = ?")
                params.append(val)

        set_clause = ", ".join(set_parts)
        params.append(email)

        def do_update():
            self._conn.execute(
                f"UPDATE subscribers SET {set_clause} WHERE email = ?",
                params,
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_update)

    def queue_deal_for_digest(self, deal: dict) -> bool:
        """
        Queue a deal for inclusion in the weekly digest email.

        Args:
            deal: Deal dict containing route, origin, dest, dest_name,
                  price_cents, and tier fields.

        Returns:
            True if successfully queued, False otherwise.
        """
        def do_insert():
            self._conn.execute(
                """
                INSERT INTO digest_queue
                (route, origin, dest, dest_name, price_cents, tier, deal_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    deal.get("route", ""),
                    deal.get("origin", ""),
                    deal.get("dest", ""),
                    deal.get("dest_name", ""),
                    deal.get("price_cents", 0),
                    deal.get("tier", ""),
                    json.dumps(deal),
                ),
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_insert)

    def get_pending_digest_deals(self, max_age_days: int = 7) -> list[dict]:
        """
        Get deals pending for digest email (not yet sent, within age window).

        Returns deals ordered by tier (wow/mistake first) then by recency.

        Args:
            max_age_days: Maximum age of deals to include (default 7 days).

        Returns:
            List of deal dicts, or empty list on failure.
        """
        if not self._turso_available:
            return []

        try:
            result = self._conn.execute(
                f"""
                SELECT * FROM digest_queue
                WHERE digest_sent = 0
                  AND found_at >= datetime('now', '-{max_age_days} days')
                ORDER BY tier DESC, found_at DESC
                """,
            ).fetchall()

            return self._rows_to_dicts(result, "digest_queue")

        except Exception as e:
            logger.error(f"[DB] get_pending_digest_deals failed: {e}")
            return []

    def mark_digest_deals_sent(self, deal_ids: list[int]) -> bool:
        """
        Mark digest queue deals as sent.

        Args:
            deal_ids: List of digest_queue row IDs to mark as sent.

        Returns:
            True if successfully updated, False otherwise.
        """
        if not deal_ids:
            return True

        placeholders = ", ".join("?" for _ in deal_ids)

        def do_update():
            self._conn.execute(
                f"UPDATE digest_queue SET digest_sent = 1 WHERE id IN ({placeholders})",
                deal_ids,
            )
            self._conn.commit()
            self._conn.sync()

        return self._execute_with_fallback(do_update)

    def get_subscribers_needing_reminder(self, days_before: int = 7) -> list[dict]:
        """
        Get premium subscribers whose payment is expiring soon.

        Returns subscribers where:
        - tier is 'premium' and active
        - premium_expiry is within days_before days from now
        - No reminder sent in the last 6 days (avoid spam)

        Args:
            days_before: Days before expiry to send reminder (default 7).

        Returns:
            List of subscriber dicts, or empty list on failure.
        """
        if not self._turso_available:
            return []

        try:
            result = self._conn.execute(
                f"""
                SELECT * FROM subscribers
                WHERE tier = 'premium'
                  AND active = 1
                  AND premium_expiry IS NOT NULL
                  AND premium_expiry <= datetime('now', '+{days_before} days')
                  AND (payment_reminder_sent IS NULL
                       OR payment_reminder_sent < datetime('now', '-6 days'))
                """,
            ).fetchall()

            return self._rows_to_dicts(result, "subscribers")

        except Exception as e:
            logger.error(f"[DB] get_subscribers_needing_reminder failed: {e}")
            return []
