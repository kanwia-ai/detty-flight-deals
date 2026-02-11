"""
Detty Flight Deals - Metro Group Mappings

Maps US origin airports to metro groups and African destinations to regions.
Used for subscriber filtering: free tier subscribers pick one metro group,
premium subscribers can monitor multiple metros and destination regions.

Metro groups:
  NYC (JFK, EWR), DC (IAD), ATL, HOU (IAH), CHI (ORD), LA (LAX), DFW, BOS

Destination regions:
  West Africa, Central Africa, East Africa, Southern Africa, North Africa
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================
# METRO GROUPS: US origin airports grouped by metro area
# ============================================================
# Each metro group contains airports that serve the same metro area.
# Free tier subscribers pick one metro group.
# Premium subscribers can monitor multiple metro groups.

METRO_GROUPS: dict[str, list[str]] = {
    "NYC": ["JFK", "EWR"],
    "DC": ["IAD"],
    "ATL": ["ATL"],
    "HOU": ["IAH"],
    "CHI": ["ORD"],
    "LA": ["LAX"],
    "DFW": ["DFW"],
    "BOS": ["BOS"],
}

# Reverse mapping: airport code -> metro group name
# Built programmatically from METRO_GROUPS
AIRPORT_TO_METRO: dict[str, str] = {
    airport: metro
    for metro, airports in METRO_GROUPS.items()
    for airport in airports
}

# ============================================================
# DESTINATION REGIONS: African airports grouped by region
# ============================================================
# Used for premium subscribers to filter by destination region.
# West Africa is the primary market; others are future expansion.

DEST_REGIONS: dict[str, list[str]] = {
    "West": ["LOS", "ABV", "ACC", "DSS", "FNA", "ABJ", "LFW", "COO"],
    "Central": ["DLA", "NSI", "FIH"],
    "East": ["NBO", "ADD"],
    "Southern": ["JNB", "CPT"],
    "North": ["CAI", "CMN"],
}

# Reverse mapping: destination airport code -> region name
DEST_TO_REGION: dict[str, str] = {
    airport: region
    for region, airports in DEST_REGIONS.items()
    for airport in airports
}


# ============================================================
# SUBSCRIBER FILTERING HELPERS
# ============================================================


def get_subscriber_metros(subscriber: dict) -> list[str]:
    """
    Get the list of metro groups a subscriber monitors.

    Premium/trial subscribers with metro_groups_json get multiple metros.
    Free subscribers with metro_group get a single metro.
    Subscribers with no preference get all metros (no filtering).

    Args:
        subscriber: Dict with at least 'tier', 'metro_group', 'metro_groups_json' keys.

    Returns:
        List of metro group names (e.g. ["NYC", "DC"]).
    """
    if subscriber.get("tier") in ("premium", "trial") and subscriber.get("metro_groups_json"):
        try:
            return json.loads(subscriber["metro_groups_json"])
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "[Subscriber] Invalid metro_groups_json for %s, falling back to metro_group",
                subscriber.get("email", "unknown"),
            )

    if subscriber.get("metro_group"):
        return [subscriber["metro_group"]]

    # No preference set -- return all metros (subscriber sees all deals)
    return list(METRO_GROUPS.keys())


def get_airports_for_metros(metros: list[str]) -> set[str]:
    """
    Get the set of airport codes served by the given metro groups.

    Args:
        metros: List of metro group names (e.g. ["NYC", "DC"]).

    Returns:
        Set of airport codes (e.g. {"JFK", "EWR", "IAD"}).
    """
    airports = set()
    for metro in metros:
        if metro in METRO_GROUPS:
            airports.update(METRO_GROUPS[metro])
        else:
            logger.warning("[Subscriber] Unknown metro group: %s", metro)
    return airports


def airport_matches_subscriber(airport_code: str, subscriber: dict) -> bool:
    """
    Check if an airport code matches a subscriber's metro preferences.

    Args:
        airport_code: Origin airport code (e.g. "JFK").
        subscriber: Dict with subscriber data including tier and metro fields.

    Returns:
        True if the airport is in one of the subscriber's monitored metro groups.
    """
    if airport_code not in AIRPORT_TO_METRO:
        logger.warning(
            "[Subscriber] Airport %s not in AIRPORT_TO_METRO mapping", airport_code
        )

    metros = get_subscriber_metros(subscriber)
    airports = get_airports_for_metros(metros)
    return airport_code in airports
