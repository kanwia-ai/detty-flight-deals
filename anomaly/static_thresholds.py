"""
Static threshold fallbacks for cold-start classification.

DISC-06: Cold-start handling for routes with insufficient historical data.

When a route has fewer than 30 observations (min_periods for z-score),
these static thresholds provide fallback classification.

Thresholds are in DOLLARS (matching pm-docs/pricing-tiers.md).
EXCEPTIONAL_FLOORS are historical lows - anything below is "too good to be true".
"""

from datetime import datetime
from typing import Optional

from .seasonal_adjustments import SeasonalAdjuster


# Static thresholds in DOLLARS (from pm-docs/pricing-tiers.md)
# Used when insufficient historical data for z-score calculation
STATIC_THRESHOLDS = {
    # Nigeria (highest diaspora demand)
    "LOS": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    "ABV": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    # Ghana
    "ACC": {"normal": 1100, "good": 850, "great": 650, "wow": 650},
    # Senegal
    "DSS": {"normal": 1000, "good": 750, "great": 550, "wow": 550},
    # Sierra Leone
    "FNA": {"normal": 1100, "good": 900, "great": 700, "wow": 700},
    # Ivory Coast
    "ABJ": {"normal": 1300, "good": 1000, "great": 800, "wow": 800},
    # Togo
    "LFW": {"normal": 1300, "good": 1000, "great": 750, "wow": 750},
    # Benin
    "COO": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    # Cameroon
    "DLA": {"normal": 1000, "good": 800, "great": 600, "wow": 600},
    "NSI": {"normal": 1000, "good": 800, "great": 600, "wow": 600},
    # DRC
    "FIH": {"normal": 1500, "good": 1100, "great": 850, "wow": 850},
}


# Exceptional deal absolute floors (research-based historical lows)
# Anything below this is "too good to be true" - likely mistake fare territory
# Source: pm-docs/pricing-tiers.md "Best recent deals" data
EXCEPTIONAL_FLOORS = {
    "LOS": 500,  # Historical lows around $685-800, $500 would be exceptional
    "ABV": 500,
    "ACC": 450,  # Historical lows around $700-850
    "DSS": 350,  # Historical lows around $400-600 (direct flights)
    "FNA": 500,
    "ABJ": 600,
    "LFW": 400,  # Historical lows around $500-800
    "COO": 550,
    "DLA": 400,  # Historical lows around $570-800
    "NSI": 400,
    "FIH": 600,  # Historical lows around $700-950
}


def classify_with_static(
    price_cents: int,
    destination_code: str,
    travel_date: Optional[datetime] = None
) -> Optional[dict]:
    """
    Classify a price using static thresholds (cold-start fallback).

    Used when insufficient historical data exists for z-score calculation.

    Args:
        price_cents: Price in cents (e.g., 65000 = $650)
        destination_code: Airport code (e.g., "LOS") or route (e.g., "JFK-LOS")
        travel_date: Optional travel date for seasonal adjustment

    Returns:
        Classification dict or None if not a deal:
        {
            "tier": "good" | "great" | "wow" | "exceptional",
            "method": "static"
        }

    Example:
        # $650 to Lagos is a "great" deal (under $700 threshold)
        result = classify_with_static(65000, "LOS")
        # {'tier': 'great', 'method': 'static'}

        # $400 to Lagos is "exceptional" (below floor)
        result = classify_with_static(40000, "LOS")
        # {'tier': 'exceptional', 'method': 'static'}

        # $1000 to Lagos is not a deal
        result = classify_with_static(100000, "LOS")
        # None
    """
    # Extract destination code if route provided (e.g., "JFK-LOS" -> "LOS")
    if "-" in destination_code:
        destination_code = destination_code.split("-")[1]

    # Look up thresholds for destination
    thresholds = STATIC_THRESHOLDS.get(destination_code)
    if not thresholds:
        return None

    # Get exceptional floor for this destination
    floor = EXCEPTIONAL_FLOORS.get(destination_code, 0)

    # Convert price to dollars for comparison
    price_dollars = price_cents / 100

    # Apply seasonal adjustment if travel_date provided
    if travel_date:
        # Normalize price to remove seasonal effects
        price_cents_normalized = SeasonalAdjuster.normalize_price(price_cents, travel_date)
        price_dollars = price_cents_normalized / 100

    # Check exceptional floor first (mistake fare territory)
    if price_dollars < floor:
        return {"tier": "exceptional", "method": "static"}

    # Check tiers from best to worst
    if price_dollars < thresholds["wow"]:
        return {"tier": "wow", "method": "static"}
    elif price_dollars < thresholds["great"]:
        return {"tier": "great", "method": "static"}
    elif price_dollars < thresholds["good"]:
        return {"tier": "good", "method": "static"}

    # Not a deal
    return None
