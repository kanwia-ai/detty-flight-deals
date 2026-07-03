"""
SerpAPI Google Flights fallback for Detty Flight Deals.

Two jobs, both small on purpose:
  1. confirm_wow()   — one cross-check call before a WOW-tier deal is emailed
                       to friends, so a stale scraped price doesn't cry wolf.
  2. takeover_scan() — emergency coverage of the priority corridors (LOS/ACC)
                       while fast-flights is broken, ~6 calls per run.

Budget: SerpAPI's free tier is 250 searches/month (renews monthly). Usage is
tracked in serpapi_quota.json (committed back to the repo by the workflow)
with a HARD stop at 200 so validation calls always have headroom and a bug
can never drift into a paid tier. No SERPAPI_KEY set = everything no-ops.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search"

QUOTA_FILE = Path(__file__).parent / "serpapi_quota.json"
MONTHLY_HARD_STOP = 200  # free tier is 250/mo; never get near it

# Takeover config: multi-airport departure_id collapses all origins into one
# call, so 2 destinations x 3 date pairs = 6 calls per takeover run.
TAKEOVER_ORIGINS = "JFK,EWR,IAD,ATL"
TAKEOVER_DESTS = ["LOS", "ACC"]
TAKEOVER_DAYS_OUT = [60, 90, 120]
TAKEOVER_TRIP_DAYS = 10


# ============================================================
# QUOTA TRACKING
# ============================================================

def _load_quota() -> dict:
    month = datetime.now().strftime("%Y-%m")
    if QUOTA_FILE.exists():
        try:
            with open(QUOTA_FILE, "r") as f:
                data = json.load(f)
            if data.get("month") == month:
                return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"month": month, "used": 0}


def _save_quota(quota: dict):
    with open(QUOTA_FILE, "w") as f:
        json.dump(quota, f, indent=2)


def quota_remaining() -> int:
    return max(0, MONTHLY_HARD_STOP - _load_quota()["used"])


# ============================================================
# SEARCH
# ============================================================

def _search(params: dict) -> dict | None:
    """One SerpAPI google_flights call, quota-guarded. None on any failure."""
    if not SERPAPI_KEY:
        return None

    quota = _load_quota()
    if quota["used"] >= MONTHLY_HARD_STOP:
        print(f"      [SerpAPI] monthly hard stop ({MONTHLY_HARD_STOP}) reached — skipping")
        return None
    quota["used"] += 1
    _save_quota(quota)  # count the attempt before the call; failures cost quota too

    try:
        response = requests.get(
            SERPAPI_URL,
            params={
                "engine": "google_flights",
                "currency": "USD",
                "hl": "en",
                "type": "1",  # round trip
                "api_key": SERPAPI_KEY,
                **params,
            },
            timeout=60,
        )
        if response.status_code != 200:
            print(f"      [SerpAPI] HTTP {response.status_code}: {response.text[:120]}")
            return None
        return response.json()
    except requests.RequestException as e:
        print(f"      [SerpAPI] request failed: {e}")
        return None


def _all_flights(data: dict) -> list[dict]:
    return (data.get("best_flights") or []) + (data.get("other_flights") or [])


# ============================================================
# WOW VALIDATION
# ============================================================

def confirm_wow(origin: str, dest: str, departure: str, return_date: str,
                found_price: int) -> bool | None:
    """
    Cross-check a WOW-tier price against SerpAPI.

    Returns True (confirmed), False (bogus — SerpAPI's cheapest is way above
    and Google doesn't rate the fare as low), or None (couldn't check; caller
    should fail open).
    """
    data = _search({
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": departure,
        "return_date": return_date,
    })
    if data is None:
        return None

    prices = [f.get("price") for f in _all_flights(data) if f.get("price")]
    if not prices:
        return None

    serp_lowest = min(prices)
    price_level = (data.get("price_insights") or {}).get("price_level")

    confirmed = serp_lowest <= found_price * 1.10 or price_level == "low"
    print(f"      [SerpAPI] {origin}→{dest} {departure}: found=${found_price} "
          f"serp=${serp_lowest} level={price_level} → {'✓' if confirmed else '✗'}")
    return confirmed


# ============================================================
# TAKEOVER SCAN
# ============================================================

def takeover_scan() -> list[dict]:
    """
    Emergency scan of the priority corridors while fast-flights is down.
    Returns raw candidates: {origin, dest, price, departure, return,
    departure_dt, url} — deal_finder classifies and dedups them.
    """
    if not SERPAPI_KEY:
        print("      [SerpAPI] no SERPAPI_KEY set — takeover unavailable")
        return []

    candidates = []
    for dest in TAKEOVER_DESTS:
        for days_out in TAKEOVER_DAYS_OUT:
            departure_dt = datetime.now() + timedelta(days=days_out)
            departure = departure_dt.strftime("%Y-%m-%d")
            return_date = (departure_dt + timedelta(days=TAKEOVER_TRIP_DAYS)).strftime("%Y-%m-%d")

            data = _search({
                "departure_id": TAKEOVER_ORIGINS,
                "arrival_id": dest,
                "outbound_date": departure,
                "return_date": return_date,
            })
            if data is None:
                continue

            for flight in _all_flights(data):
                price = flight.get("price")
                legs = flight.get("flights") or []
                if not price or not legs:
                    continue
                origin = (legs[0].get("departure_airport") or {}).get("id")
                if not origin:
                    continue
                candidates.append({
                    "origin": origin,
                    "dest": dest,
                    "price": int(price),
                    "departure": departure,
                    "return": return_date,
                    "departure_dt": departure_dt,
                    "url": (
                        f"https://www.google.com/travel/flights?"
                        f"q=Flights%20from%20{origin}%20to%20{dest}%20"
                        f"departing%20{departure}%20returning%20{return_date}&curr=USD"
                    ),
                })

    print(f"      [SerpAPI] takeover scan: {len(candidates)} candidates, "
          f"{quota_remaining()} calls left this month")
    return candidates
