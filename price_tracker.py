"""
Detty Flight Deals - Price Tracker
Price change detection, caching, and API budget tracking.

Uses deal_finder.py as single source of truth for deal classification
thresholds. Persists state via JSON files (same pattern as seen_deals.json).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from deal_finder import classify_deal, DESTINATIONS, log_price_search
from db import TursoClient


# ============================================================
# PRICE TRACKER
# ============================================================

class PriceTracker:
    """
    Tracks prices across runs, detects changes, and manages alert cooldowns.

    State files:
      - price_cache.json: Latest prices per route (persists across runs)
      - alert_cooldown.json: When each route/tier was last alerted (dedup)

    API budget tracking:
      - Counts API calls per run to prevent budget overrun
      - Monthly budget: 2160 calls (6 routes x 12 checks/day x 30 days)
    """

    # Monthly API call budget (6 routes x 12 checks/day x 30 days)
    MONTHLY_BUDGET = 2160

    def __init__(
        self,
        cache_file: str = "price_cache.json",
        cooldown_file: str = "alert_cooldown.json",
    ):
        self._cache_path = Path(__file__).parent / cache_file
        self._cooldown_path = Path(__file__).parent / cooldown_file

        self._cache = self.load_cache()
        self._cooldown = self.load_cooldown()

        self.api_call_counter = 0
        self._routes_checked = 0
        self._deals_found = 0

        # Initialize Turso client for dual-write (JSON is still primary)
        self._db = TursoClient(dual_write=True)

    # ============================================================
    # CACHE PERSISTENCE (same pattern as deal_finder.py load_seen_deals)
    # ============================================================

    def load_cache(self) -> dict:
        """Load price cache from JSON file. Returns empty dict if missing/corrupt."""
        if not self._cache_path.exists():
            return {}
        try:
            with open(self._cache_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_cache(self):
        """Write price cache to JSON file."""
        with open(self._cache_path, "w") as f:
            json.dump(self._cache, f, indent=2)

    def load_cooldown(self) -> dict:
        """Load alert cooldown state from JSON file. Returns empty dict if missing/corrupt."""
        if not self._cooldown_path.exists():
            return {}
        try:
            with open(self._cooldown_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_cooldown(self):
        """Write alert cooldown state to JSON file."""
        with open(self._cooldown_path, "w") as f:
            json.dump(self._cooldown, f, indent=2)

    # ============================================================
    # CACHE KEY
    # ============================================================

    def make_cache_key(self, origin: str, dest: str) -> str:
        """
        Create cache key for a route.

        Route-level (not date-level) because Amadeus returns
        many dates per route and we track the route's best price.
        """
        return f"{origin}-{dest}"

    # ============================================================
    # ROUTE CHECKING & DEAL DETECTION
    # ============================================================

    def check_route(
        self,
        origin: str,
        dest: str,
        prices: list[dict],
        source: str,
    ) -> list[dict]:
        """
        Check a route's prices for deals.

        Takes prices from amadeus_client.get_prices_for_route() and
        classifies each using deal_finder.classify_deal(). Compares
        against cached prices, updates cache, and returns new deals
        not on cooldown.

        Args:
            origin: IATA origin airport code
            dest: IATA destination airport code
            prices: List of {"departureDate", "returnDate", "price_usd"} dicts
            source: "cheapest_date_search" or "flight_offers_search"

        Returns:
            List of new deal dicts (not on cooldown) with keys:
            {origin, dest, dest_name, price, departure_date, return_date,
             tier, label, normal_price, source}
        """
        self._routes_checked += 1
        cache_key = self.make_cache_key(origin, dest)
        deals = []

        # Map source string to price history source tag
        source_tag = (
            "amadeus_cheapest_date"
            if source == "cheapest_date_search"
            else "amadeus_offers_search"
        )

        # Get destination name from deal_finder config
        dest_info = DESTINATIONS.get(dest)
        if not dest_info:
            print(f"  [WARN] Destination {dest} not in DESTINATIONS config, skipping")
            return []
        dest_name = dest_info["name"]

        for entry in prices:
            price_usd = entry["price_usd"]
            departure_date = entry.get("departureDate", "")
            return_date = entry.get("returnDate", "")

            # Log every price observation to price history (JSON - source of truth)
            log_price_search(
                origin=origin,
                dest=dest,
                travel_date=departure_date,
                return_date=return_date,
                price=price_usd,
                source=source_tag,
            )

            # Dual-write: Also record to Turso price_observations table
            if self._db._turso_available:
                try:
                    # Classify early to include tier in observation
                    classification = classify_deal(price_usd, dest)
                    tier_at_time = classification["tier"] if classification else None
                    self._db.record_observation(
                        route=f"{origin}-{dest}",
                        date_checked=datetime.now().isoformat(),
                        travel_date=departure_date,
                        return_date=return_date,
                        price_cents=int(price_usd * 100),  # Convert to cents
                        source=source_tag,
                        cabin_class="economy",
                        tier=tier_at_time,
                    )
                except Exception as e:
                    print(f"  [DB] Turso write failed: {e}")

            # Classify using deal_finder thresholds (single source of truth)
            classification = classify_deal(price_usd, dest)
            if classification is None:
                continue  # Not a deal

            tier = classification["tier"]
            label = classification["label"]
            normal_price = classification["normal_price"]

            # Check if this tier is on cooldown for this route
            if self.is_on_cooldown(origin, dest, tier):
                continue

            deals.append({
                "origin": origin,
                "dest": dest,
                "dest_name": dest_name,
                "price": price_usd,
                "departure_date": departure_date,
                "return_date": return_date,
                "tier": tier,
                "label": label,
                "normal_price": normal_price,
                "source": source,
            })

        # Update cache with latest data for this route (JSON - source of truth)
        if prices:
            best_price = min(p["price_usd"] for p in prices)
            self._cache[cache_key] = {
                "best_price": best_price,
                "checked_at": datetime.now().isoformat(),
                "source": source,
                "prices_count": len(prices),
            }

            # Dual-write: Also update Turso price_cache if we have deals
            if self._db._turso_available and deals:
                best_deal = sorted(deals, key=lambda d: d["price"])[0]
                try:
                    self._db.update_cache(
                        route=cache_key,
                        tier=best_deal["tier"],
                        price_cents=int(best_deal["price"] * 100),
                        dest_name=best_deal["dest_name"],
                    )
                except Exception as e:
                    print(f"  [DB] Turso cache update failed: {e}")

        self._deals_found += len(deals)
        return deals

    # ============================================================
    # ALERT COOLDOWN (24-hour for all tiers in Phase 1)
    # ============================================================

    def is_on_cooldown(self, origin: str, dest: str, tier: str) -> bool:
        """
        Check if an alert for this route/tier is on cooldown.

        Uses 24-hour cooldown for ALL tiers in Phase 1.
        Phase 4 will implement tier-specific cooldowns via FSM.

        Returns:
            True if alerted within last 24 hours (on cooldown).
        """
        key = f"{origin}-{dest}-{tier}"
        entry = self._cooldown.get(key)
        if not entry:
            return False

        try:
            alerted_at = datetime.fromisoformat(entry["alerted_at"])
            return datetime.now() - alerted_at < timedelta(hours=24)
        except (KeyError, ValueError):
            return False

    def record_alert(self, origin: str, dest: str, tier: str):
        """Record that an alert was sent for this route/tier."""
        key = f"{origin}-{dest}-{tier}"
        self._cooldown[key] = {
            "alerted_at": datetime.now().isoformat(),
            "tier": tier,
        }

        # Dual-write: Also update Turso alert_state
        if self._db._turso_available:
            try:
                self._db.update_alert_state(
                    route=f"{origin}-{dest}",
                    current_tier=tier,
                    cooldown_expiry=(datetime.now() + timedelta(hours=24)).isoformat(),
                )
            except Exception as e:
                print(f"  [DB] Turso alert_state update failed: {e}")

    # ============================================================
    # API BUDGET TRACKING
    # ============================================================

    def track_api_calls(self, count: int):
        """Track API calls made in this run."""
        self.api_call_counter += count
        print(f"  API calls this run: {self.api_call_counter}")

    # ============================================================
    # RUN SUMMARY
    # ============================================================

    def get_run_summary(self) -> dict:
        """
        Get summary statistics for the current run.

        Returns dict with:
          - api_calls: Total API calls made this run
          - routes_checked: Number of routes checked
          - deals_found: Number of deals found (before cooldown filter)
          - cache_size: Number of routes in price cache
        """
        return {
            "api_calls": self.api_call_counter,
            "routes_checked": self._routes_checked,
            "deals_found": self._deals_found,
            "cache_size": len(self._cache),
        }
