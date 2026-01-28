"""
Detty Flight Deals - Amadeus Priority Route Monitor
Main entry point for continuous monitoring of priority US-Africa routes.

Orchestrates the full pipeline:
  1. Fetch prices from Amadeus (amadeus_client)
  2. Detect price changes and classify deals (price_tracker)
  3. Cross-validate against Google Flights (cross_validator)
  4. Send email alerts for validated deals (deal_finder)

DISC-02: NEVER sends an alert based on Amadeus-only data.
Every deal must be cross-validated against Google Flights before alerting.
"""

import time
import random
import json
from datetime import datetime

from amadeus_client import create_amadeus_client, get_prices_for_route, PRIORITY_ROUTES
from price_tracker import PriceTracker
from cross_validator import cross_validate_deal, build_google_flights_url
from deal_finder import classify_deal, send_email, log_price_search, DESTINATIONS


# ============================================================
# PRIORITY ROUTE MONITORING
# ============================================================

def monitor_priority_routes() -> tuple[list[dict], dict]:
    """
    Monitor all priority routes: fetch prices, detect deals, cross-validate.

    Pipeline per route:
      1. get_prices_for_route() -> prices from Amadeus
      2. tracker.check_route() -> classify deals, update price cache
      3. cross_validate_deal() -> verify against Google Flights
      4. Only validated deals are returned for alerting

    Failed cross-validation behavior:
      - Price cache IS updated (observation is valid, happened in check_route)
      - Alert cooldown is NOT recorded (no alert was sent)
      - Logged with source="amadeus_FAILED_VALIDATION" for debugging

    Returns:
        Tuple of (validated_deals, run_summary) where:
          - validated_deals: List of validated deal dicts ready for email formatting
          - run_summary: Dict with api_calls, routes_checked, deals_found, cache_size
    """
    # Create Amadeus client
    try:
        client = create_amadeus_client()
    except Exception as e:
        print(f"Amadeus credentials not configured. Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET.")
        print(f"Error: {e}")
        return [], {"api_calls": 0, "routes_checked": 0, "deals_found": 0, "cache_size": 0}

    tracker = PriceTracker()
    validated_deals = []

    for i, (origin, dest) in enumerate(PRIORITY_ROUTES, 1):
        print(f"\n[{i}/{len(PRIORITY_ROUTES)}] Checking {origin}-{dest}...")

        try:
            # Step 1: Fetch prices from Amadeus
            prices, source = get_prices_for_route(client, origin, dest)

            # Track API calls
            if source == "flight_offers_search":
                tracker.track_api_calls(len(prices) if prices else 1)
            else:
                tracker.track_api_calls(1)

            # Step 2: Detect deals via price tracker (updates cache)
            deal_candidates = tracker.check_route(origin, dest, prices, source)

            if not deal_candidates:
                print(f"  No deal candidates for {origin}-{dest}")
                continue

            print(f"  {len(deal_candidates)} deal candidate(s) for {origin}-{dest}")

            # Step 3: Cross-validate each candidate against Google Flights
            for deal in deal_candidates:
                validation_result = cross_validate_deal(
                    origin=origin,
                    dest=dest,
                    departure_date=deal["departure_date"],
                    amadeus_price_usd=deal["price"],
                )

                if validation_result["validated"]:
                    # VALIDATED: Include Google Flights URL and add to validated deals
                    deal["url"] = validation_result["google_url"]
                    validated_deals.append(deal)
                    # Record alert cooldown (alert WILL be sent)
                    tracker.record_alert(origin, dest, deal["tier"])
                    print(f"  VALIDATED: {origin}-{dest} ${deal['price']} on {deal['departure_date']}")
                else:
                    # NOT VALIDATED: Log but do NOT alert
                    # Price cache IS already updated (tracker.check_route did that above)
                    # Alert cooldown is NOT recorded (no alert sent, eligible for re-check)
                    print(f"  Deal {origin}-{dest} ${deal['price']} on {deal['departure_date']} "
                          f"NOT cross-validated, skipping alert")

                    # Log failed validation for debugging
                    log_price_search(
                        origin=origin,
                        dest=dest,
                        travel_date=deal["departure_date"],
                        return_date=deal.get("return_date", ""),
                        price=deal["price"],
                        source="amadeus_FAILED_VALIDATION",
                    )

        except Exception as e:
            print(f"  [ERROR] Failed to check {origin}-{dest}: {e}")
            continue

        # Rate limiting between routes
        if i < len(PRIORITY_ROUTES):
            time.sleep(random.uniform(1, 3))

    # Save tracker state (cache + cooldown)
    tracker.save_cache()
    tracker.save_cooldown()

    return validated_deals, tracker.get_run_summary()


# ============================================================
# EMAIL FORMATTING
# ============================================================

def format_deals_for_email(validated_deals: list[dict]) -> list[dict]:
    """
    Transform validated deals into the format expected by deal_finder.send_email().

    deal_finder.build_email_content() expects each deal dict to have:
      origin, dest, dest_name, region, price, tier, label, normal_price,
      departure, return, url, lowest_found, highest_found, weeks_searched

    Field mapping from Amadeus deal dict -> email format:
      departure_date -> departure
      return_date    -> return
      url            -> url (Google Flights URL from cross-validation)
      price          -> lowest_found, highest_found (single observation)
      1              -> weeks_searched (Amadeus returns specific dates)
    """
    formatted = []

    for deal in validated_deals:
        dest_info = DESTINATIONS.get(deal["dest"])
        if not dest_info:
            continue

        formatted.append({
            "origin": deal["origin"],
            "dest": deal["dest"],
            "dest_name": deal["dest_name"],
            "region": dest_info["region"],
            "price": deal["price"],
            "tier": deal["tier"],
            "label": deal["label"],
            "normal_price": deal["normal_price"],
            "departure": deal["departure_date"],
            "return": deal["return_date"],
            "url": deal["url"],
            "lowest_found": deal["price"],
            "highest_found": deal["price"],
            "weeks_searched": 1,
        })

    return formatted


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def main():
    """
    Main entry point for priority route monitoring.

    Runs the full pipeline: fetch -> detect -> validate -> alert.
    Called by priority_monitor.yml GitHub workflow every 2 hours.
    """
    print("=" * 60)
    print(f"Detty Priority Monitor (Amadeus) - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print(f"Routes: {len(PRIORITY_ROUTES)} priority routes")
    print(f"Cross-validation: enabled (15% tolerance)")

    # Run the monitoring pipeline
    validated_deals, run_summary = monitor_priority_routes()

    if validated_deals:
        print(f"\n{len(validated_deals)} validated deal(s) found!")

        # Format for email delivery
        formatted_deals = format_deals_for_email(validated_deals)

        # Send via existing infrastructure (Google Sheets subscribers + Gmail SMTP)
        send_email(formatted_deals)
        print(f"Sent {len(formatted_deals)} validated deals to subscribers")
    else:
        print("\nNo validated deals this run.")

    # Print run summary
    print(f"\nRun summary:")
    print(f"  API calls: {run_summary['api_calls']}")
    print(f"  Routes checked: {run_summary['routes_checked']}")
    print(f"  Deals found: {run_summary['deals_found']}")
    print(f"  Cache size: {run_summary['cache_size']}")

    print(f"\nCompleted at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
