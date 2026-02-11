"""
Detty Flight Deals - Subscriber Manager
Business logic layer for subscriber operations.

Wraps TursoClient subscriber methods with:
  - CRUD operations (add, deactivate, update)
  - Metro change enforcement (once per month for free tier)
  - Premium tier management (quarterly billing)
  - Trial lifecycle integration

Usage:
    from subscriber.manager import SubscriberManager

    manager = SubscriberManager()
    manager.add("user@example.com", name="User", metro_group="NYC")
    manager.update_metro("user@example.com", "DC")
    manager.set_premium("user@example.com", months=3)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class SubscriberManager:
    """
    Business logic layer for subscriber operations.

    Wraps TursoClient with subscriber-specific logic like metro change
    rate limiting, trial auto-start, and premium tier management.

    Attributes:
        db: TursoClient instance for database operations.
    """

    def __init__(self, db_client=None):
        """
        Initialize SubscriberManager.

        Args:
            db_client: TursoClient instance. If None, creates a new one.
        """
        if db_client is None:
            from db.client import TursoClient
            db_client = TursoClient()
        self.db = db_client

    # ============================================================
    # READ OPERATIONS
    # ============================================================

    def get_all_active(self, tier: str = None) -> list[dict]:
        """
        Get all active subscribers, optionally filtered by tier.

        Args:
            tier: Filter by tier ('free', 'premium', 'trial') or None for all.

        Returns:
            List of subscriber dicts.
        """
        return self.db.get_active_subscribers(tier)

    def get_by_email(self, email: str) -> Optional[dict]:
        """
        Get a single active subscriber by email.

        Args:
            email: Subscriber email address.

        Returns:
            Subscriber dict or None if not found/inactive.
        """
        if not self.db._turso_available or not self.db._conn:
            return None

        try:
            result = self.db._conn.execute(
                "SELECT * FROM subscribers WHERE email = ? AND active = 1",
                (email,),
            ).fetchone()

            if result:
                rows = self.db._rows_to_dicts([result], "subscribers")
                return rows[0] if rows else None
            return None

        except Exception as e:
            logger.error(f"[Subscriber] get_by_email failed for {email}: {e}")
            return None

    # ============================================================
    # CREATE / DEACTIVATE
    # ============================================================

    def add(
        self,
        email: str,
        name: str = None,
        tier: str = "free",
        metro_group: str = None,
        start_trial: bool = True,
    ) -> Optional[dict]:
        """
        Add a new subscriber.

        Uses INSERT OR IGNORE to handle duplicate emails gracefully.
        If start_trial is True and tier is "free", automatically starts
        a 7-day premium trial for the new subscriber.

        Args:
            email: Subscriber email (unique).
            name: Optional display name.
            tier: Subscription tier ('free', 'premium', 'trial').
            metro_group: Metro group preference for free tier (e.g. 'NYC').
            start_trial: If True and tier is "free", auto-start 7-day trial.

        Returns:
            Subscriber dict, or None on failure.
        """
        self.db.add_subscriber(email, name, tier, metro_group)

        # Auto-start trial for new free subscribers
        if start_trial and tier == "free":
            from subscriber.trial import start_trial as _start_trial
            _start_trial(self, email)

        return self.get_by_email(email)

    def deactivate(self, email: str) -> bool:
        """
        Soft-delete a subscriber (set active = 0).

        Args:
            email: Subscriber email to deactivate.

        Returns:
            True if successfully deactivated, False otherwise.
        """
        result = self.db.update_subscriber(email, active=0)
        if result:
            logger.info(f"[Subscriber] Deactivated {email}")
        return result

    # ============================================================
    # METRO UPDATE (with rate limiting)
    # ============================================================

    def update_metro(self, email: str, new_metro: str) -> tuple[bool, str]:
        """
        Update a subscriber's metro group.

        Free tier: limited to one change per month.
        Premium/trial: update freely, add to metro_groups_json.

        Args:
            email: Subscriber email.
            new_metro: New metro group name (e.g. 'DC').

        Returns:
            Tuple of (success: bool, message: str).
        """
        subscriber = self.get_by_email(email)
        if subscriber is None:
            return (False, "Subscriber not found")

        if subscriber["tier"] == "free":
            return self._update_metro_free(email, subscriber, new_metro)
        elif subscriber["tier"] in ("premium", "trial"):
            return self._update_metro_premium(email, subscriber, new_metro)
        else:
            return (False, f"Unknown tier: {subscriber['tier']}")

    def _update_metro_free(
        self, email: str, subscriber: dict, new_metro: str
    ) -> tuple[bool, str]:
        """
        Update metro for free tier subscriber with once-per-month enforcement.

        Args:
            email: Subscriber email.
            subscriber: Current subscriber dict.
            new_metro: New metro group name.

        Returns:
            Tuple of (success: bool, message: str).
        """
        change_date = subscriber.get("metro_change_date")
        if change_date:
            try:
                last_change = datetime.fromisoformat(change_date)
                if datetime.now() - last_change < timedelta(days=30):
                    days_left = 30 - (datetime.now() - last_change).days
                    return (
                        False,
                        f"Metro can only be changed once per month. "
                        f"Try again in {days_left} day(s).",
                    )
            except (ValueError, TypeError):
                # Invalid date format, allow the change
                logger.warning(
                    f"[Subscriber] Invalid metro_change_date for {email}: {change_date}"
                )

        # Update metro_group and record change date
        result = self.db.update_subscriber(
            email,
            metro_group=new_metro,
            metro_change_date="datetime('now')",
        )
        if result:
            logger.info(f"[Subscriber] Free tier metro updated for {email}: {new_metro}")
            return (True, "Metro updated")
        return (False, "Failed to update metro")

    def _update_metro_premium(
        self, email: str, subscriber: dict, new_metro: str
    ) -> tuple[bool, str]:
        """
        Update metro for premium/trial subscriber (no rate limit).

        Adds new metro to metro_groups_json if not already present.

        Args:
            email: Subscriber email.
            subscriber: Current subscriber dict.
            new_metro: New metro group name to add.

        Returns:
            Tuple of (success: bool, message: str).
        """
        # Parse existing metro groups
        metros = []
        if subscriber.get("metro_groups_json"):
            try:
                metros = json.loads(subscriber["metro_groups_json"])
            except (json.JSONDecodeError, TypeError):
                metros = []

        # Add new metro if not already present
        if new_metro not in metros:
            metros.append(new_metro)

        result = self.db.update_subscriber(
            email,
            metro_groups_json=json.dumps(metros),
        )
        if result:
            logger.info(
                f"[Subscriber] Premium metro updated for {email}: {metros}"
            )
            return (True, "Metro updated")
        return (False, "Failed to update metro")

    # ============================================================
    # PREMIUM MANAGEMENT
    # ============================================================

    def set_premium(self, email: str, months: int = 3) -> bool:
        """
        Upgrade a subscriber to premium tier.

        Sets tier to "premium" with start/expiry dates. Clears any
        existing trial fields since premium supersedes trial.

        Args:
            email: Subscriber email.
            months: Duration of premium subscription (default 3 = quarterly).

        Returns:
            True if successfully upgraded, False otherwise.
        """
        now = datetime.now()
        expiry = now + timedelta(days=months * 30)

        result = self.db.update_subscriber(
            email,
            tier="premium",
            premium_start=now.isoformat(),
            premium_expiry=expiry.isoformat(),
            trial_start=None,
            trial_expiry=None,
        )
        if result:
            logger.info(
                f"[Subscriber] Set premium for {email}, "
                f"expires {expiry.isoformat()}"
            )
        return result

    def set_premium_metros(self, email: str, metros: list[str]) -> bool:
        """
        Set the full list of metro groups for a premium subscriber.

        Args:
            email: Subscriber email.
            metros: List of metro group names (e.g. ['NYC', 'DC', 'ATL']).

        Returns:
            True if successfully updated, False otherwise.
        """
        result = self.db.update_subscriber(
            email,
            metro_groups_json=json.dumps(metros),
        )
        if result:
            logger.info(f"[Subscriber] Set premium metros for {email}: {metros}")
        return result

    def set_dest_regions(self, email: str, regions: list[str]) -> bool:
        """
        Set destination region preferences for a subscriber.

        Args:
            email: Subscriber email.
            regions: List of region names (e.g. ['West', 'East']).

        Returns:
            True if successfully updated, False otherwise.
        """
        result = self.db.update_subscriber(
            email,
            dest_regions_json=json.dumps(regions),
        )
        if result:
            logger.info(f"[Subscriber] Set dest regions for {email}: {regions}")
        return result

    def set_phone(self, email: str, phone: str) -> bool:
        """
        Set phone number for SMS alerts (premium feature).

        Args:
            email: Subscriber email.
            phone: Phone number (e.g. '+1234567890').

        Returns:
            True if successfully updated, False otherwise.
        """
        result = self.db.update_subscriber(email, phone=phone)
        if result:
            logger.info(f"[Subscriber] Set phone for {email}")
        return result
