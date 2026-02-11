"""
Detty Flight Deals - Amadeus API Client
SDK wrapper with Cheapest Date Search + Flight Offers Search fallback.

Uses the official amadeus Python SDK (NOT raw requests).
The SDK handles OAuth2 token management automatically.
"""

import os
import logging
from datetime import datetime, timedelta

from amadeus import Client, ResponseError


logger = logging.getLogger(__name__)


# ============================================================
# PRIORITY ROUTES
# ============================================================
# 6 priority US-Africa routes for continuous monitoring.
# These are the highest-demand diaspora corridors.

PRIORITY_ROUTES = [
    ("JFK", "LOS"),  # New York JFK -> Lagos
    ("EWR", "ACC"),  # Newark -> Accra
    ("ATL", "LOS"),  # Atlanta -> Lagos
    ("IAD", "ACC"),  # Washington Dulles -> Accra
    ("DFW", "LOS"),  # Dallas -> Lagos
    ("IAH", "ACC"),  # Houston -> Accra
]

# Premium cabin classes for business/first class monitoring (Phase 6)
CABIN_CLASSES = ["BUSINESS", "FIRST", "PREMIUM_ECONOMY"]


# ============================================================
# CLIENT INITIALIZATION
# ============================================================

def create_amadeus_client() -> Client:
    """
    Create and return an Amadeus SDK client.

    Reads credentials from environment variables:
      - AMADEUS_CLIENT_ID (API key)
      - AMADEUS_CLIENT_SECRET (API secret)

    The SDK reads these automatically when no explicit args are passed.

    Optional env vars:
      - AMADEUS_HOSTNAME: 'test' (default) or 'production'
    """
    hostname = os.environ.get("AMADEUS_HOSTNAME", "test")
    log_level = os.environ.get("AMADEUS_LOG_LEVEL", "warn")

    return Client(
        hostname=hostname,
        log_level=log_level,
    )


# ============================================================
# CHEAPEST DATE SEARCH
# ============================================================

def search_cheapest_dates(client: Client, origin: str, dest: str) -> list[dict]:
    """
    Search for cheapest flight dates using Amadeus Flight Cheapest Date Search API.

    This API returns cached price data for a given route across many dates.
    It is fast and cheap (1 API call per route) but only works for routes
    that exist in the Amadeus cache. Many African routes are NOT cached.

    Args:
        client: Amadeus SDK client instance
        origin: IATA origin airport code (e.g., "JFK")
        dest: IATA destination airport code (e.g., "LOS")

    Returns:
        List of dicts: [{"departureDate": str, "returnDate": str, "price_usd": int}, ...]
        Empty list if route not in cache or API error.
    """
    try:
        response = client.shopping.flight_dates.get(
            origin=origin,
            destination=dest,
        )

        results = []
        if response.data:
            for item in response.data:
                try:
                    price_usd = int(float(item["price"]["total"]))
                    results.append({
                        "departureDate": item.get("departureDate", ""),
                        "returnDate": item.get("returnDate", ""),
                        "price_usd": price_usd,
                    })
                except (KeyError, ValueError, TypeError) as e:
                    logger.debug(f"Skipping malformed price entry: {e}")
                    continue

        print(f"  Cheapest Date Search {origin}-{dest}: {len(results)} dates found")
        return results

    except ResponseError as e:
        print(f"  Cheapest Date Search {origin}-{dest}: no data (route not in cache) [{e}]")
        return []
    except Exception as e:
        print(f"  Cheapest Date Search {origin}-{dest}: error [{e}]")
        return []


# ============================================================
# FLIGHT OFFERS SEARCH (FALLBACK)
# ============================================================

def search_offers_fallback(
    client: Client,
    origin: str,
    dest: str,
    sample_dates: list[str],
) -> list[dict]:
    """
    Fallback: search individual dates using Flight Offers Search API.

    Used when Cheapest Date Search returns no data (common for African routes).
    Each date costs 1 API call, so we sample strategically rather than
    searching every date.

    Args:
        client: Amadeus SDK client instance
        origin: IATA origin airport code
        dest: IATA destination airport code
        sample_dates: List of departure dates in YYYY-MM-DD format

    Returns:
        List of dicts same format as search_cheapest_dates.
    """
    results = []
    successful = 0

    for date in sample_dates:
        try:
            response = client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=dest,
                departureDate=date,
                adults=1,
                max=5,
                currencyCode="USD",
            )

            if response.data:
                # Find cheapest offer
                cheapest = min(response.data, key=lambda x: float(x["price"]["total"]))
                price_usd = int(float(cheapest["price"]["total"]))
                results.append({
                    "departureDate": date,
                    "returnDate": "",  # One-way search; return date not in offers response
                    "price_usd": price_usd,
                })
                successful += 1

        except ResponseError as e:
            logger.debug(f"  Offers Search {origin}-{dest} {date}: skipped [{e}]")
            continue
        except Exception as e:
            logger.debug(f"  Offers Search {origin}-{dest} {date}: error [{e}]")
            continue

    print(f"  Flight Offers Search {origin}-{dest}: {successful}/{len(sample_dates)} dates returned prices")
    return results


# ============================================================
# PREMIUM CABIN FLIGHT OFFERS SEARCH (Phase 6)
# ============================================================

def search_offers_for_cabin(
    client: Client,
    origin: str,
    dest: str,
    sample_dates: list[str],
    cabin_class: str = "BUSINESS",
) -> list[dict]:
    """
    Search flight offers for a specific cabin class (Business, First, Premium Economy).

    Uses Flight Offers Search API with travelClass parameter. Does NOT use
    Cheapest Date Search because it does not support cabin class filtering
    (06-RESEARCH.md Pitfall 1).

    IMPORTANT: This function is separate from search_offers_fallback() to keep
    economy monitoring unchanged. search_offers_fallback() remains economy-only
    for backward compatibility.

    Args:
        client: Amadeus SDK client instance
        origin: IATA origin airport code (e.g., "JFK")
        dest: IATA destination airport code (e.g., "LOS")
        sample_dates: List of departure dates in YYYY-MM-DD format
        cabin_class: One of "BUSINESS", "FIRST", "PREMIUM_ECONOMY"

    Returns:
        List of dicts: [{"departureDate": str, "returnDate": str, "price_usd": int}, ...]
        Empty list if no inventory found (common for FIRST class on US-Africa routes).
    """
    results = []
    successful = 0

    for date in sample_dates:
        try:
            response = client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=dest,
                departureDate=date,
                adults=1,
                max=5,
                currencyCode="USD",
                travelClass=cabin_class,
            )

            if response.data:
                # Find cheapest offer
                cheapest = min(response.data, key=lambda x: float(x["price"]["total"]))
                price_usd = int(float(cheapest["price"]["total"]))
                results.append({
                    "departureDate": date,
                    "returnDate": "",  # One-way search; return date not in offers response
                    "price_usd": price_usd,
                })
                successful += 1

        except ResponseError as e:
            logger.debug(f"  Offers Search {origin}-{dest} {date} ({cabin_class}): skipped [{e}]")
            continue
        except Exception as e:
            logger.debug(f"  Offers Search {origin}-{dest} {date} ({cabin_class}): error [{e}]")
            continue

    print(f"  Premium Cabin Search {origin}-{dest} ({cabin_class}): {successful}/{len(sample_dates)} dates returned prices")

    if not results:
        logger.info(f"  No {cabin_class} inventory found for {origin}-{dest} (this may be normal for FIRST class on US-Africa routes)")

    return results


# ============================================================
# SAMPLE DATE GENERATION
# ============================================================

def generate_sample_dates(num_dates: int = 12) -> list[str]:
    """
    Generate sample departure dates for fallback search.

    Produces 12 dates every 2 weeks starting from 6 weeks out,
    up to approximately 6 months out. This provides best-effort
    coverage when Cheapest Date Search cache misses (common for
    African routes like JFK-LOS, JFK-ACC).

    NOTE: Even with 12 samples, this is best-effort coverage --
    not equivalent to the full date range that Cheapest Date Search
    provides. The cache typically returns 30-60+ dates per route.

    Returns:
        List of date strings in YYYY-MM-DD format.
    """
    dates = []
    start = datetime.now() + timedelta(weeks=6)  # Start 6 weeks out

    for i in range(num_dates):
        date = start + timedelta(weeks=2 * i)  # Every 2 weeks
        dates.append(date.strftime("%Y-%m-%d"))

    return dates


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def get_prices_for_route(
    client: Client,
    origin: str,
    dest: str,
) -> tuple[list[dict], str]:
    """
    Get prices for a route, trying Cheapest Date Search first,
    falling back to Flight Offers Search with sampled dates.

    Args:
        client: Amadeus SDK client instance
        origin: IATA origin airport code
        dest: IATA destination airport code

    Returns:
        Tuple of (prices_list, source_str) where:
          - prices_list: list of {"departureDate", "returnDate", "price_usd"} dicts
          - source_str: "cheapest_date_search" or "flight_offers_search"
    """
    # Try Cheapest Date Search first (1 API call, many dates)
    prices = search_cheapest_dates(client, origin, dest)

    if prices:
        print(f"  {origin}-{dest}: Using Cheapest Date Search ({len(prices)} dates)")
        return prices, "cheapest_date_search"

    # Fallback: Flight Offers Search with sampled dates (12 API calls)
    print(f"  {origin}-{dest}: Falling back to Flight Offers Search (12 sampled dates)")
    sample_dates = generate_sample_dates()
    prices = search_offers_fallback(client, origin, dest, sample_dates)

    return prices, "flight_offers_search"
