"""
Detty Flight Deals - Cross Validator
Verifies Amadeus prices against Google Flights via fast-flights.

DISC-02 safety layer: No alert is sent based on Amadeus-only data.
If fast-flights fails for ANY reason, the deal is NOT validated.
"""

import time
import random
import logging
from datetime import datetime, timedelta

from fast_flights import FlightData, Passengers, get_flights
from deal_finder import parse_price


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

# Cross-validation tolerance: Amadeus price must be within 15% of Google price
# to be considered validated. If Amadeus is cheaper, that's also fine.
CROSS_VALIDATION_TOLERANCE = 0.15

# Trip length for return date calculation (must match deal_finder.TRIP_LENGTH_DAYS)
TRIP_LENGTH_DAYS = 10


# ============================================================
# GOOGLE FLIGHTS URL BUILDER
# ============================================================

def build_google_flights_url(origin: str, dest: str, departure_date: str, return_date: str) -> str:
    """
    Build a direct Google Flights URL for a round-trip search.

    This URL is included in email alerts so subscribers can book directly.
    Same pattern as deal_finder.py search_flight() (line 398-401).

    Args:
        origin: IATA origin airport code (e.g., "JFK")
        dest: IATA destination airport code (e.g., "LOS")
        departure_date: Departure date in YYYY-MM-DD format
        return_date: Return date in YYYY-MM-DD format

    Returns:
        Google Flights URL string
    """
    return (
        f"https://www.google.com/travel/flights?"
        f"q=Flights%20from%20{origin}%20to%20{dest}%20"
        f"departing%20{departure_date}%20returning%20{return_date}&curr=USD"
    )


# ============================================================
# CROSS-VALIDATION
# ============================================================

def cross_validate_deal(
    origin: str,
    dest: str,
    departure_date: str,
    amadeus_price_usd: int,
) -> dict:
    """
    Cross-validate an Amadeus price against Google Flights via fast-flights.

    Uses the same search pattern as deal_finder.py's search_flight():
    round-trip, economy, 1 adult, outbound + return legs.

    Validation logic (15% tolerance):
      - Amadeus <= Google min: VALIDATED (Amadeus found better deal)
      - Amadeus within 15% above Google min: VALIDATED (prices agree)
      - Amadeus > 15% above Google min: NOT VALIDATED (suspicious)
      - fast-flights exception: NOT VALIDATED (cannot confirm)

    Args:
        origin: IATA origin airport code
        dest: IATA destination airport code
        departure_date: Departure date in YYYY-MM-DD format
        amadeus_price_usd: Amadeus price in USD (integer)

    Returns:
        Dict with validation result:
        {
            "validated": bool,
            "amadeus_price": int,
            "google_price": int | None,
            "tolerance_pct": 15,
            "source": "fast_flights",
            "google_url": str,
            "error": str (only on exception),
        }
    """
    # Calculate return date (departure + TRIP_LENGTH_DAYS, matching deal_finder.py)
    try:
        dep_dt = datetime.strptime(departure_date, "%Y-%m-%d")
        return_date = (dep_dt + timedelta(days=TRIP_LENGTH_DAYS)).strftime("%Y-%m-%d")
    except ValueError:
        # If departure_date is invalid, still build what we can
        return_date = ""

    # Google Flights URL is always available (built from inputs, not fast-flights results)
    google_url = build_google_flights_url(origin, dest, departure_date, return_date)

    try:
        # Rate limiting: small delay before fast-flights call (same pattern as deal_finder.py)
        time.sleep(random.uniform(0.5, 1.5))

        # Search Google Flights via fast-flights (same pattern as deal_finder.search_flight)
        result = get_flights(
            flight_data=[
                FlightData(date=departure_date, from_airport=origin, to_airport=dest),
                FlightData(date=return_date, from_airport=dest, to_airport=origin),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
        )

        # Parse all valid prices from fast-flights results
        valid_prices = []
        if result and result.flights:
            for f in result.flights:
                price = parse_price(f.price)
                if price:
                    valid_prices.append(price)

        if not valid_prices:
            print(f"  Cross-validate {origin}-{dest} {departure_date}: "
                  f"Amadeus ${amadeus_price_usd} vs Google (no prices) -> FAIL")
            return {
                "validated": False,
                "amadeus_price": amadeus_price_usd,
                "google_price": None,
                "tolerance_pct": 15,
                "source": "fast_flights",
                "google_url": google_url,
                "error": "No valid prices from fast-flights",
            }

        google_min = min(valid_prices)

        # Apply 15% tolerance for cross-validation
        # Amadeus <= Google: VALIDATED (better deal found)
        # Amadeus within 15% above Google: VALIDATED (prices agree)
        # Amadeus > 15% above Google: NOT VALIDATED (suspicious)
        if amadeus_price_usd <= google_min:
            validated = True
        elif amadeus_price_usd <= google_min * (1 + CROSS_VALIDATION_TOLERANCE):
            validated = True
        else:
            validated = False

        status = "PASS" if validated else "FAIL"
        print(f"  Cross-validate {origin}-{dest} {departure_date}: "
              f"Amadeus ${amadeus_price_usd} vs Google ${google_min} -> {status}")

        return {
            "validated": validated,
            "amadeus_price": amadeus_price_usd,
            "google_price": google_min,
            "tolerance_pct": 15,
            "source": "fast_flights",
            "google_url": google_url,
        }

    except Exception as e:
        print(f"  Cross-validate {origin}-{dest} {departure_date}: "
              f"Amadeus ${amadeus_price_usd} vs Google (error: {e}) -> FAIL")
        return {
            "validated": False,
            "amadeus_price": amadeus_price_usd,
            "google_price": None,
            "tolerance_pct": 15,
            "source": "fast_flights",
            "google_url": google_url,
            "error": str(e),
        }
