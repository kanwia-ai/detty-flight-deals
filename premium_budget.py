"""
Premium Cabin API Budget Tracker (Phase 6).

Tracks premium cabin monitoring API calls against a monthly budget cap.
Persists state to premium_budget.json with automatic monthly rollover.

$25/month hard budget cap at ~$0.004/call = ~6,250 calls max.
Starting conservative at 5,000 calls/month; adjust MAX_CALLS_PER_MONTH as needed.

Usage:
    budget = PremiumBudget()
    if budget.is_exhausted():
        print("Monthly budget exhausted, skipping premium cabin check.")
        return

    # Before a monitoring run, check if enough budget remains
    calls_needed = budget.calls_needed_for_run(num_routes=6, num_cabins=3, dates_per_route=12)
    if budget.remaining() < calls_needed:
        print(f"Not enough budget: need {calls_needed}, have {budget.remaining()}")
        return

    # After API calls, record usage
    budget.record(count=216)
    budget.save()
"""

import json
import logging
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)


class PremiumBudget:
    """Track premium cabin API calls against monthly budget cap."""

    BUDGET_FILE = Path(__file__).parent / "premium_budget.json"
    MAX_CALLS_PER_MONTH = 5000  # Conservative start (~$20 at $0.004/call, under $25 cap)

    def __init__(self):
        """Load budget from JSON and check for monthly rollover."""
        self._data = self._load()
        self._check_month_rollover()

    def _load(self) -> dict:
        """Load budget state from JSON file. Returns fresh state if missing/corrupt."""
        if not self.BUDGET_FILE.exists():
            return self._fresh_state()
        try:
            with open(self.BUDGET_FILE, "r") as f:
                data = json.load(f)
            # Validate required keys
            if "month" not in data or "calls_used" not in data:
                logger.warning("Corrupt budget file, creating fresh state")
                return self._fresh_state()
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load budget file: {e}")
            return self._fresh_state()

    def _fresh_state(self) -> dict:
        """Create a fresh budget state for the current month."""
        return {
            "month": datetime.now().strftime("%Y-%m"),
            "calls_used": 0,
            "budget_limit_calls": self.MAX_CALLS_PER_MONTH,
            "last_run": None,
        }

    def _check_month_rollover(self):
        """Reset budget counter if a new month has started."""
        current_month = datetime.now().strftime("%Y-%m")
        if self._data.get("month") != current_month:
            logger.info(f"New month ({current_month}), resetting premium cabin API budget")
            self._data = {
                "month": current_month,
                "calls_used": 0,
                "budget_limit_calls": self.MAX_CALLS_PER_MONTH,
                "last_run": self._data.get("last_run"),
            }

    def remaining(self) -> int:
        """How many API calls remain this month."""
        return max(0, self._data["budget_limit_calls"] - self._data["calls_used"])

    def is_exhausted(self) -> bool:
        """Whether the monthly budget has been fully consumed."""
        return self.remaining() <= 0

    def record(self, count: int):
        """
        Record API calls made.

        Args:
            count: Number of API calls to add to the counter.
        """
        self._data["calls_used"] += count
        self._data["last_run"] = datetime.now().isoformat()

        if self.is_exhausted():
            logger.warning(
                f"Premium cabin API budget EXHAUSTED for {self._data['month']}: "
                f"{self._data['calls_used']}/{self._data['budget_limit_calls']} calls used"
            )

    def save(self):
        """Write budget state to JSON file."""
        with open(self.BUDGET_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def calls_needed_for_run(
        self,
        num_routes: int,
        num_cabins: int,
        dates_per_route: int,
    ) -> int:
        """
        Calculate how many API calls a full monitoring run would need.

        Each route-cabin combination searches multiple dates, and each date
        costs 1 API call (Flight Offers Search).

        Args:
            num_routes: Number of routes to monitor (e.g., 6)
            num_cabins: Number of cabin classes to check (e.g., 3)
            dates_per_route: Sample dates per route-cabin combo (e.g., 12)

        Returns:
            Total API calls needed for a full run.
        """
        return num_routes * num_cabins * dates_per_route

    @property
    def calls_used(self) -> int:
        """Number of API calls used this month."""
        return self._data["calls_used"]

    @property
    def month(self) -> str:
        """Current budget month (YYYY-MM format)."""
        return self._data["month"]

    def __repr__(self) -> str:
        return (
            f"PremiumBudget(month={self.month}, "
            f"used={self.calls_used}/{self._data['budget_limit_calls']}, "
            f"remaining={self.remaining()})"
        )
