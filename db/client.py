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

from .schema import init_schema

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
        cooldown_expiry: Optional[str],
        consecutive_normal_count: int = 0,
    ) -> bool:
        """
        Update alert state for a route (FSM state for Phase 4).

        Args:
            route: Route string e.g. "JFK-LOS"
            current_tier: Current deal tier or None
            cooldown_expiry: ISO timestamp when cooldown ends or None
            consecutive_normal_count: Count of consecutive normal prices

        Returns:
            True if successfully written to Turso, False otherwise
        """
        if not self._turso_available:
            return False

        def do_upsert():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO alert_state
                (route, current_tier, cooldown_expiry, consecutive_normal_count)
                VALUES (?, ?, ?, ?)
                """,
                (route, current_tier, cooldown_expiry, consecutive_normal_count),
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
            Dict with {route, current_tier, cooldown_expiry, consecutive_normal_count} or None
        """
        if not self._turso_available:
            return None

        try:
            result = self._conn.execute(
                """
                SELECT route, current_tier, cooldown_expiry, consecutive_normal_count
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
