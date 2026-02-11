"""
Detty Flight Deals - Premium Cabin Monitor
Monitors Business, First, and Premium Economy fares on priority routes.

Runs every 4-6 hours via GitHub Actions (separate from economy monitor).
All premium cabin deals route exclusively to premium subscribers.

BUSN-01: Monitor premium cabin fares via Amadeus cabin class parameter
BUSN-02: Separate thresholds from economy (static fallback + z-score)
BUSN-03: Premium cabin deals routed only to premium subscribers

Pipeline per route-cabin combo:
  1. Check API budget (stop if exhausted)
  2. Fetch prices via search_offers_for_cabin()
  3. Record observations in Turso DB
  4. Classify deals via BaselineCalculator (premium path)
  5. Process through AlertStateMachine (cabin-aware route keys)
  6. Route to premium subscribers via AlertRouter
"""

import os
import time
import random
import logging
from datetime import datetime
from typing import Optional

from amadeus_client import (
    create_amadeus_client,
    search_offers_for_cabin,
    generate_sample_dates,
    PRIORITY_ROUTES,
    CABIN_CLASSES,
)
from premium_budget import PremiumBudget
from anomaly.baseline_calculator import BaselineCalculator
from alert.state_machine import AlertStateMachine
from subscriber.router import AlertRouter
from db.client import TursoClient
from deal_finder import DESTINATIONS


logger = logging.getLogger(__name__)

# Number of sample dates per route-cabin combo (same as economy: 12 dates, 2-week intervals)
DATES_PER_COMBO = 12

# Google Flights travel class parameter mapping
_GOOGLE_FLIGHTS_CLASS = {
    "ECONOMY": 1,
    "PREMIUM_ECONOMY": 2,
    "BUSINESS": 3,
    "FIRST": 4,
}


class PremiumCabinMonitor:
    """
    Orchestrates premium cabin fare monitoring end-to-end.

    Fetches prices from Amadeus for Business, First, and Premium Economy
    on all 6 priority routes, classifies deals via the anomaly detection
    pipeline, and routes premium cabin deals exclusively to premium subscribers.

    Attributes:
        _budget: PremiumBudget instance for API call tracking
        _db: TursoClient instance for database operations
        _fsm: AlertStateMachine for deal state tracking
        _router: AlertRouter for subscriber routing
        _baseline: BaselineCalculator for deal classification
        _enabled: Whether premium monitoring is enabled (env var toggle)
    """

    def __init__(self):
        """
        Initialize all pipeline components.

        Checks PREMIUM_CABIN_MONITORING_ENABLED env var (default "true").
        If "false", monitoring is disabled and run() returns empty summary.
        """
        self._enabled = os.environ.get(
            "PREMIUM_CABIN_MONITORING_ENABLED", "true"
        ).lower() != "false"

        self._budget = PremiumBudget()
        self._db = TursoClient()
        self._fsm = AlertStateMachine(db_client=self._db)
        self._router = AlertRouter(db_client=self._db)
        self._baseline = BaselineCalculator(db_client=self._db)

        # Run stats
        self._api_calls = 0
        self._routes_checked = 0
        self._deals_found = 0
        self._deals_routed = 0
        self._silent_period_count = 0

    def run(self) -> dict:
        """
        Main entry point: run the full premium cabin monitoring pipeline.

        For each route-cabin combo:
          1. Check budget remaining
          2. Fetch prices from Amadeus
          3. Process each price observation through classify -> FSM -> route

        Returns:
            Run summary dict with api_calls, routes_checked, deals_found,
            deals_routed, budget_remaining, and silent_period_count.
        """
        if not self._enabled:
            print("Premium cabin monitoring is DISABLED (PREMIUM_CABIN_MONITORING_ENABLED=false)")
            return self._build_summary()

        if self._budget.is_exhausted():
            print(f"Premium cabin API budget EXHAUSTED for {self._budget.month}")
            print(f"  Used: {self._budget.calls_used}/{PremiumBudget.MAX_CALLS_PER_MONTH}")
            print("  Monitoring skipped. Budget resets next month.")
            return self._build_summary()

        # Calculate total calls needed for a full run
        calls_needed = len(PRIORITY_ROUTES) * len(CABIN_CLASSES) * DATES_PER_COMBO
        remaining = self._budget.remaining()

        if remaining < calls_needed:
            print(f"  Budget warning: need {calls_needed} calls for full run, "
                  f"only {remaining} remaining. Will process until budget runs out.")

        # Generate sample dates (same strategy as economy monitor)
        sample_dates = generate_sample_dates(DATES_PER_COMBO)

        # Create Amadeus client
        try:
            client = create_amadeus_client()
        except Exception as e:
            print(f"Amadeus credentials not configured. "
                  f"Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET.")
            print(f"Error: {e}")
            return self._build_summary()

        combo_index = 0
        total_combos = len(PRIORITY_ROUTES) * len(CABIN_CLASSES)

        for origin, dest in PRIORITY_ROUTES:
            for cabin_class in CABIN_CLASSES:
                combo_index += 1

                # Check budget before each route-cabin combo
                if self._budget.remaining() < DATES_PER_COMBO:
                    print(f"\n  Budget exhausted mid-run "
                          f"({self._budget.remaining()} calls remaining, "
                          f"need {DATES_PER_COMBO}). Stopping.")
                    self._budget.save()
                    return self._build_summary()

                print(f"\n[{combo_index}/{total_combos}] "
                      f"{origin}-{dest} ({cabin_class})...")

                try:
                    # Fetch prices from Amadeus
                    results = search_offers_for_cabin(
                        client, origin, dest, sample_dates, cabin_class
                    )

                    # Record API calls to budget (1 call per date searched)
                    api_calls_made = len(sample_dates)
                    self._budget.record(api_calls_made)
                    self._api_calls += api_calls_made

                    if not results:
                        print(f"  No {cabin_class} inventory for {origin}-{dest}")
                        continue

                    self._routes_checked += 1

                    # Process each price observation
                    for price_data in results:
                        deal = self._process_observation(
                            origin, dest, cabin_class, price_data
                        )
                        if deal:
                            self._deals_found += 1

                except Exception as e:
                    print(f"  [ERROR] Failed to check {origin}-{dest} "
                          f"({cabin_class}): {e}")
                    continue

                # Rate limiting between combos
                if combo_index < total_combos:
                    time.sleep(random.uniform(0.5, 1.5))

        # Save budget state after full run
        self._budget.save()

        return self._build_summary()

    def _process_observation(
        self,
        origin: str,
        dest: str,
        cabin_class: str,
        price_data: dict,
    ) -> Optional[dict]:
        """
        Process a single price observation through the full pipeline.

        Steps:
          1. Record observation in Turso DB
          2. Classify deal via BaselineCalculator (premium path)
          3. If no deal or silent period: feed normal price to FSM, return None
          4. If deal detected: process through FSM, route if alert triggered

        Args:
            origin: IATA origin airport code
            dest: IATA destination airport code
            cabin_class: Cabin class (e.g., "BUSINESS")
            price_data: Dict with departureDate, returnDate, price_usd

        Returns:
            Deal dict if a deal was routed, None otherwise
        """
        price_usd = price_data["price_usd"]
        price_cents = int(price_usd * 100)
        departure_date = price_data.get("departureDate", "")
        return_date = price_data.get("returnDate", "")

        route = f"{origin}-{dest}"
        # Cabin-aware route key for FSM (e.g., "JFK-LOS:BUSINESS")
        route_key = f"{route}:{cabin_class}"

        # Step 1: Record observation in Turso DB
        if self._db._turso_available:
            try:
                self._db.record_observation(
                    route=route,
                    date_checked=datetime.now().isoformat(),
                    travel_date=departure_date,
                    return_date=return_date,
                    price_cents=price_cents,
                    source="amadeus_premium_cabin",
                    cabin_class=cabin_class.lower(),
                    tier=None,  # Classification happens next
                )
            except Exception as e:
                logger.warning(f"[PREMIUM] Turso write failed for {route_key}: {e}")

        # Step 2: Classify deal via BaselineCalculator
        classification = self._baseline.classify_deal(
            price_cents, route, cabin_class=cabin_class.lower()
        )

        if classification is None:
            # No deal or in silent period — feed normal price to FSM for reset tracking
            self._fsm.process(route_key, None, price_cents)

            # Check if this was a silent period suppression
            # (BaselineCalculator returns None for silent period, but we can infer)
            if self._db._turso_available:
                history = self._db.get_price_history(
                    route, days=90, cabin_class=cabin_class.lower()
                )
                obs_count = len(history) if history else 0
                if obs_count < 28:
                    self._silent_period_count += 1
                    logger.debug(
                        f"[PREMIUM] {route_key}: silent period "
                        f"({obs_count}/28 observations)"
                    )
            return None

        # Step 3: Deal detected! Determine deal characteristics
        deal_tier = classification["tier"]
        classification_method = classification["method"]

        # Mistake fare detection: level_shift method or exceptional tier
        is_mistake_fare = (
            classification_method == "level_shift"
            or deal_tier == "exceptional"
        )

        print(f"  DEAL: {route_key} ${price_usd} "
              f"({deal_tier}, method={classification_method})")

        # Step 4: Process through FSM with cabin-aware route key
        should_alert, alert_info = self._fsm.process(
            route_key,
            # Per CONTEXT.md: all premium cabin deals treated like mistake fares
            # Route as WOW tier for maximum urgency (email + SMS)
            "wow",
            price_cents,
            is_mistake_fare=is_mistake_fare,
        )

        if not should_alert:
            print(f"  FSM suppressed alert for {route_key} "
                  f"(already alerted or de-escalation)")
            return None

        # Step 5: Build deal dict and route to premium subscribers
        dest_info = DESTINATIONS.get(dest, {})
        dest_name = dest_info.get("name", dest)

        deal = {
            "origin": origin,
            "dest": dest,
            "dest_name": dest_name,
            "price": price_usd,
            "price_cents": price_cents,
            "tier": "wow",  # All premium cabin deals route as WOW
            "cabin_class": cabin_class,
            "is_mistake_fare": is_mistake_fare,
            "departure_date": departure_date,
            "return_date": return_date,
            "url": self._build_google_flights_url(
                origin, dest, departure_date, cabin_class
            ),
            "classification_method": classification_method,
            "observation_count": classification.get("observation_count", 0),
            "z_score": classification.get("z_score"),
            "drop_pct": classification.get("drop_pct"),
        }

        # Route via AlertRouter (handles premium-only delivery)
        routing_result = self._router.route_deal(deal)
        self._deals_routed += 1

        print(f"  ROUTED: {route_key} ${price_usd} -> "
              f"{routing_result.get('instant_emails', 0)} emails, "
              f"{routing_result.get('sms_sent', 0)} SMS")

        return deal

    @staticmethod
    def _build_google_flights_url(
        origin: str,
        dest: str,
        departure_date: str,
        cabin_class: str,
    ) -> str:
        """
        Build a Google Flights URL with cabin class parameter.

        Google Flights uses tfc= parameter for travel class:
          1 = Economy, 2 = Premium Economy, 3 = Business, 4 = First

        Args:
            origin: IATA origin airport code
            dest: IATA destination airport code
            departure_date: Departure date (YYYY-MM-DD)
            cabin_class: Cabin class (e.g., "BUSINESS")

        Returns:
            Google Flights URL string
        """
        tfc = _GOOGLE_FLIGHTS_CLASS.get(cabin_class.upper(), 1)
        # Format date for Google Flights URL (YYYY-MM-DD)
        return (
            f"https://www.google.com/travel/flights?"
            f"q=flights+from+{origin}+to+{dest}+on+{departure_date}"
            f"&tfc={tfc}"
        )

    def _build_summary(self) -> dict:
        """Build run summary dict."""
        return {
            "api_calls": self._api_calls,
            "routes_checked": self._routes_checked,
            "deals_found": self._deals_found,
            "deals_routed": self._deals_routed,
            "budget_remaining": self._budget.remaining(),
            "budget_used": self._budget.calls_used,
            "silent_period_count": self._silent_period_count,
            "enabled": self._enabled,
        }


def main():
    """
    Main entry point for premium cabin monitoring.

    Runs the full pipeline: fetch -> classify -> FSM -> route.
    Called by premium_cabin_monitor.yml GitHub workflow every 4-6 hours.
    """
    print("=" * 60)
    print(f"Detty Premium Cabin Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"Routes: {len(PRIORITY_ROUTES)} priority routes")
    print(f"Cabins: {', '.join(CABIN_CLASSES)}")
    print(f"Dates sampled: {DATES_PER_COMBO} per route-cabin combo")
    print(f"Total combos: {len(PRIORITY_ROUTES) * len(CABIN_CLASSES)}")

    monitor = PremiumCabinMonitor()
    summary = monitor.run()

    print(f"\n{'=' * 60}")
    print("Run Summary:")
    print(f"  Enabled: {summary['enabled']}")
    print(f"  API calls: {summary['api_calls']}")
    print(f"  Route-cabin combos checked: {summary['routes_checked']}")
    print(f"  Deals found: {summary['deals_found']}")
    print(f"  Deals routed: {summary['deals_routed']}")
    print(f"  Silent period (still collecting data): {summary['silent_period_count']}")
    print(f"  Budget: {summary['budget_used']} used, {summary['budget_remaining']} remaining")
    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
