"""
Detty Flight Deals - Data-driven price baselines.

Computes trailing-90-day price statistics per (destination, season bucket)
from price_history.jsonl — the same file deal_finder has been appending to
since January. These stats replace the hand-tuned static thresholds as the
primary deal test; static thresholds remain only as a bootstrap for routes
with thin history (see deal_finder.classify_deal).

Buckets: "detty" (departures Dec 10 – Jan 10) vs "std" (everything else).
Detty-window fares follow a completely different distribution — as of
Aug 2026 the observed Lagos December median runs ~1.8x the shoulder-season
median, while Kinshasa's runs ~1.2x, which is exactly why one static
PEAK_MULTIPLIER produced both spam (FIH) and permanent silence (LOS).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

PRICE_HISTORY_FILE = Path(__file__).parent / "price_history.jsonl"

TRAILING_DAYS = 90
# Below this many observations the distribution isn't trustworthy — callers
# should fall back to static thresholds.
MIN_OBSERVATIONS = 100

_cache: dict | None = None


def _in_detty_window(month: int, day: int) -> bool:
    return (month == 12 and day >= 10) or (month == 1 and day <= 10)


def bucket_for(travel_dt: datetime) -> str:
    return "detty" if _in_detty_window(travel_dt.month, travel_dt.day) else "std"


def _percentile(sorted_vals: list, p: float) -> int:
    k = (len(sorted_vals) - 1) * p / 100
    f = int(k)
    if f >= len(sorted_vals) - 1:
        return sorted_vals[-1]
    return round(sorted_vals[f] + (sorted_vals[f + 1] - sorted_vals[f]) * (k - f))


def _load_stats() -> dict:
    """Parse price history once per process; ~17k lines, well under a second.

    Observations are deduped to one per probe per day (cheapest wins): the
    Detty sweeps re-search the same holiday dates up to 4x/day, and without
    the dedupe those corridors' detty buckets would be percentiled mostly
    against their own intraday repeats. Multi-source double-logging of one
    search (fast_flights + amadeus) collapses the same way."""
    cutoff = (datetime.now() - timedelta(days=TRAILING_DAYS)).isoformat()
    best: dict[tuple, tuple] = {}  # (origin, dest, travel_date, search day) -> (price, bucket key)

    if not PRICE_HISTORY_FILE.exists():
        return {}

    with open(PRICE_HISTORY_FILE) as f:
        for line in f:
            try:
                r = json.loads(line)
                if r["searched_at"] < cutoff:
                    continue
                month, day = int(r["travel_date"][5:7]), int(r["travel_date"][8:10])
                bkt = "detty" if _in_detty_window(month, day) else "std"
                probe = (r["origin"], r["destination"], r["travel_date"],
                         r["searched_at"][:10])
                if probe not in best or r["price"] < best[probe][0]:
                    best[probe] = (r["price"], (r["destination"], bkt))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue

    prices: dict[tuple, list] = {}
    for price, key in best.values():
        prices.setdefault(key, []).append(price)

    stats = {}
    for key, vals in prices.items():
        vals.sort()
        stats[key] = {
            "n": len(vals),
            "min": vals[0],
            "p5": _percentile(vals, 5),
            "p10": _percentile(vals, 10),
            "p25": _percentile(vals, 25),
            "median": _percentile(vals, 50),
        }
    return stats


def get_stats(dest: str, travel_dt: datetime) -> dict | None:
    """Trailing-90d stats for this destination + season bucket, or None if
    history is too thin to trust (< MIN_OBSERVATIONS)."""
    global _cache
    if _cache is None:
        _cache = _load_stats()
    s = _cache.get((dest, bucket_for(travel_dt)))
    if s and s["n"] >= MIN_OBSERVATIONS:
        return s
    return None
