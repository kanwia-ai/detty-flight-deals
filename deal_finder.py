"""
Detty Flight Deals - Deal Finder
Uses fast-flights to search all dates in the next 6 months.
Finds round-trip deals to West & Central Africa.
"""

import os
import json
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from fast_flights import FlightData, Passengers, get_flights

import baselines

# Import Google Sheets subscriber functions
try:
    from mvp0_sender import get_subscribers, send_to_subscriber
    HAS_GSHEET_SUPPORT = True
except ImportError:
    HAS_GSHEET_SUPPORT = False

# ============================================================
# CONFIGURATION
# ============================================================

# Email settings
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)

# Origins — trimmed 2026-07-03 to the airports the friend group actually flies
# from. Add "DFW", "IAH", "BOS" back here if someone in TX/New England joins.
ORIGINS = ["JFK", "EWR", "IAD", "ATL"]

# ============================================================
# PRICE THRESHOLDS BY DESTINATION (BOOTSTRAP FALLBACK ONLY)
# ============================================================
# As of 2026-08-09 these static bands are no longer the primary deal test —
# classify_deal() judges prices against trailing-90-day observed stats from
# price_history.jsonl (see baselines.py). Five weeks of live sends proved the
# static bands can't work: Kinshasa's peak "good" bar sat ABOVE the observed
# December median (half of all normal prices alerted), while Lagos's sat
# below the observed December minimum (the flagship route could never alert).
#
# These numbers remain as the fallback for buckets with thin history
# (< baselines.MIN_OBSERVATIONS data points), where only the "wow" band
# triggers an alert. Original research: pm-docs/pricing-tiers.md.

DESTINATIONS = {
    # Nigeria (highest diaspora demand)
    "LOS": {
        "name": "Lagos",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,
        "great": 800,
        "wow": 700,
    },
    "ABV": {
        "name": "Abuja",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,
        "great": 800,
        "wow": 700,
    },
    # Ghana
    "ACC": {
        "name": "Accra",
        "region": "West Africa",
        "normal": 1100,
        "good": 850,
        "great": 750,
        "wow": 650,
    },
    # Senegal
    "DSS": {
        "name": "Dakar",
        "region": "West Africa",
        "normal": 1000,
        "good": 750,
        "great": 650,
        "wow": 550,
    },
    # Sierra Leone
    "FNA": {
        "name": "Freetown",
        "region": "West Africa",
        "normal": 1100,
        "good": 900,
        "great": 800,
        "wow": 700,
    },
    # Ivory Coast
    "ABJ": {
        "name": "Abidjan",
        "region": "West Africa",
        "normal": 1300,
        "good": 1000,
        "great": 900,
        "wow": 800,
    },
    # Togo
    "LFW": {
        "name": "Lomé",
        "region": "West Africa",
        "normal": 1300,
        "good": 1000,
        "great": 875,
        "wow": 750,
    },
    # Benin
    "COO": {
        "name": "Cotonou",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,
        "great": 800,
        "wow": 700,
    },
    # Cameroon
    "DLA": {
        "name": "Douala",
        "region": "Central Africa",
        "normal": 1000,
        "good": 800,
        "great": 700,
        "wow": 600,
    },
    "NSI": {
        "name": "Yaoundé",
        "region": "Central Africa",
        "normal": 1000,
        "good": 800,
        "great": 700,
        "wow": 600,
    },
    # DRC
    "FIH": {
        "name": "Kinshasa",
        "region": "Central Africa",
        "normal": 1500,
        "good": 1100,
        "great": 975,
        "wow": 850,
    },
    # ---- East/Southern Africa (added 2026-08-09, zero price history) ----
    # quiet_until_history: never alert off the static bands below — collect
    # prices silently until baselines.py trusts the bucket (n >= 100, ~1 week
    # for std at current scan rates, several weeks for the holiday window),
    # then statistical classification takes over on its own. The bands are
    # rough placeholders, kept only so removing the flag later can't crash.
    "ADD": {
        "name": "Addis Ababa",
        "region": "East Africa",
        "normal": 1100,
        "good": 850,
        "great": 750,
        "wow": 650,
        "quiet_until_history": True,
        "digest_only": True,
    },
    "NBO": {
        "name": "Nairobi",
        "region": "East Africa",
        "normal": 1200,
        "good": 950,
        "great": 850,
        "wow": 750,
        "quiet_until_history": True,
        "digest_only": True,
    },
    "JNB": {
        "name": "Johannesburg",
        "region": "Southern Africa",
        "normal": 1300,
        "good": 1000,
        "great": 900,
        "wow": 800,
        "quiet_until_history": True,
        "digest_only": True,
    },
    # ---- Continent-wide expansion (2026-08-09, zero price history) ----
    # Everything below is quiet_until_history like ADD/NBO/JNB: silent until
    # baselines trusts the bucket. Bands are unused placeholders. Skipped on
    # purpose: KRT/TIP (conflict-closed), Cape Verde (add with a BOS origin),
    # and second cities without US-facing demand. Routes that turn out to
    # have no service get retired by the dead-probe tracker on their own.
    #
    # digest_only: the whole expansion is Saturday-digest material, never an
    # immediate email. Interrupts stay reserved for the core West/Central
    # Africa corridors the list signed up for — 45 destinations each allowed
    # to fire "drop everything" alerts would bury the inbox. Promote a dest
    # by removing the flag if subscribers start asking for it.
    # West Africa (completing the region)
    "BJL": {"name": "Banjul", "region": "West Africa",
            "normal": 1100, "good": 850, "great": 750, "wow": 650,
            "quiet_until_history": True, "digest_only": True},
    "CKY": {"name": "Conakry", "region": "West Africa",
            "normal": 1200, "good": 900, "great": 800, "wow": 700,
            "quiet_until_history": True, "digest_only": True},
    "ROB": {"name": "Monrovia", "region": "West Africa",
            "normal": 1200, "good": 900, "great": 800, "wow": 700,
            "quiet_until_history": True, "digest_only": True},
    "OUA": {"name": "Ouagadougou", "region": "West Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "NIM": {"name": "Niamey", "region": "West Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "BKO": {"name": "Bamako", "region": "West Africa",
            "normal": 1200, "good": 900, "great": 800, "wow": 700,
            "quiet_until_history": True, "digest_only": True},
    "PHC": {"name": "Port Harcourt", "region": "West Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    # Central Africa
    "LBV": {"name": "Libreville", "region": "Central Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "BZV": {"name": "Brazzaville", "region": "Central Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "NDJ": {"name": "N'Djamena", "region": "Central Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    # East Africa
    "KGL": {"name": "Kigali", "region": "East Africa",
            "normal": 1200, "good": 950, "great": 850, "wow": 750,
            "quiet_until_history": True, "digest_only": True},
    "EBB": {"name": "Entebbe", "region": "East Africa",
            "normal": 1200, "good": 950, "great": 850, "wow": 750,
            "quiet_until_history": True, "digest_only": True},
    "DAR": {"name": "Dar es Salaam", "region": "East Africa",
            "normal": 1200, "good": 950, "great": 850, "wow": 750,
            "quiet_until_history": True, "digest_only": True},
    "ZNZ": {"name": "Zanzibar", "region": "East Africa",
            "normal": 1250, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "ASM": {"name": "Asmara", "region": "East Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "MGQ": {"name": "Mogadishu", "region": "East Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    # Southern Africa
    "CPT": {"name": "Cape Town", "region": "Southern Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "HRE": {"name": "Harare", "region": "Southern Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "LUN": {"name": "Lusaka", "region": "Southern Africa",
            "normal": 1300, "good": 1000, "great": 900, "wow": 800,
            "quiet_until_history": True, "digest_only": True},
    "LLW": {"name": "Lilongwe", "region": "Southern Africa",
            "normal": 1350, "good": 1050, "great": 950, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "MPM": {"name": "Maputo", "region": "Southern Africa",
            "normal": 1350, "good": 1050, "great": 950, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "GBE": {"name": "Gaborone", "region": "Southern Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "WDH": {"name": "Windhoek", "region": "Southern Africa",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    # Indian Ocean
    "TNR": {"name": "Antananarivo", "region": "Indian Ocean",
            "normal": 1500, "good": 1200, "great": 1050, "wow": 900,
            "quiet_until_history": True, "digest_only": True},
    "MRU": {"name": "Mauritius", "region": "Indian Ocean",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    "SEZ": {"name": "Seychelles", "region": "Indian Ocean",
            "normal": 1400, "good": 1100, "great": 975, "wow": 850,
            "quiet_until_history": True, "digest_only": True},
    # North Africa
    "CAI": {"name": "Cairo", "region": "North Africa",
            "normal": 900, "good": 700, "great": 625, "wow": 550,
            "quiet_until_history": True, "digest_only": True},
    "CMN": {"name": "Casablanca", "region": "North Africa",
            "normal": 850, "good": 650, "great": 575, "wow": 500,
            "quiet_until_history": True, "digest_only": True},
    "RAK": {"name": "Marrakesh", "region": "North Africa",
            "normal": 850, "good": 650, "great": 575, "wow": 500,
            "quiet_until_history": True, "digest_only": True},
    "TUN": {"name": "Tunis", "region": "North Africa",
            "normal": 950, "good": 750, "great": 650, "wow": 550,
            "quiet_until_history": True, "digest_only": True},
    "ALG": {"name": "Algiers", "region": "North Africa",
            "normal": 900, "good": 700, "great": 625, "wow": 550,
            "quiet_until_history": True, "digest_only": True},
}

# Alert window: only search 2-6 months out (sweet spot for deals)
MIN_DAYS_OUT = 45
MAX_DAYS_OUT = 180

# Detty December: holiday-window fares run 30-50% above shoulder season, so a
# "deal" costs more. Thresholds are scaled up for departures in this window —
# a $950 JFK-LOS in December is a WOW; in May it's merely Good.
DETTY_WINDOW = ((12, 10), (1, 10))  # departures Dec 10 – Jan 10
PEAK_MULTIPLIER = 1.4

# Dedicated Detty December sweep: these corridors get the holiday window
# scanned explicitly all year, bypassing MIN_DAYS_OUT (people book late too).
# ABV added 2026-08-09 — the IAD-ABV alerts are the ones the group acts on.
DETTY_SWEEP_DESTS = ["LOS", "ACC", "ABV"]
DETTY_DEPARTURE_DAYS = ["12-11", "12-15", "12-18", "12-20", "12-22", "12-26", "12-28"]  # MM-DD
DETTY_TRIP_LENGTH_DAYS = 14

# RUN_MODE=sweep scans only the Detty corridors above (fast, runs every few
# hours via cron so a flash fare is caught same-day, not next morning).
# RUN_MODE=full (default) is the once-daily whole-network scan.
RUN_MODE = os.environ.get("RUN_MODE", "full")

# The weekly digest goes out with Saturday's full scan (or force with DIGEST=1).
IS_DIGEST_RUN = os.environ.get("DIGEST") == "1" or (
    RUN_MODE == "full" and datetime.now().weekday() == 5
)


# ============================================================
# DEAL CLASSIFICATION
# ============================================================

def in_detty_window(travel_dt: datetime) -> bool:
    """Departure falls inside the Detty December holiday window."""
    (start_month, start_day), (end_month, end_day) = DETTY_WINDOW
    if travel_dt.month == start_month and travel_dt.day >= start_day:
        return True
    if travel_dt.month == end_month and travel_dt.day <= end_day:
        return True
    return False


def classify_deal(price: int, dest: str, travel_dt: datetime | None = None) -> dict | None:
    """
    Classify a price against what this route+season has ACTUALLY traded at
    over the trailing 90 days (baselines.py). Two tiers, two channels:

      - "wow":    price <= trailing p5 AND <= 1.05x the trailing minimum.
                  "Basically the best price we've seen in 90 days." Emails
                  everyone immediately. Calibrated against 5 weeks of live
                  sends: the one deal anyone forwarded (ABV $895, a 90-day
                  min) passes; the ones nobody acted on (ABV $1147 @p10,
                  FIH $1145 @p5-p10) don't.
      - "digest": price <= trailing p10. Never interrupts — saved for the
                  Saturday weekly roundup.

    Anything above p10 is not a deal, full stop. A price half the
    distribution hits (the old FIH "good" bar) is just Tuesday.

    Buckets with thin history fall back to the static bands, where only the
    hand-tuned "wow" price alerts immediately and "good" feeds the digest.
    """
    config = DESTINATIONS.get(dest)
    if not config:
        return None

    stats = baselines.get_stats(dest, travel_dt) if travel_dt else None

    if stats:
        if price <= stats["p5"] and price <= round(stats["min"] * 1.05):
            return {
                "tier": "wow",
                "label": "WOW",
                "normal_price": stats["median"],
                "min_90d": stats["min"],
                "basis": f"cheapest 5% of {stats['n']} prices seen in 90 days",
            }
        if price <= stats["p10"]:
            return {
                "tier": "digest",
                "label": "Solid",
                "normal_price": stats["median"],
                "min_90d": stats["min"],
                "basis": f"cheapest 10% of {stats['n']} prices seen in 90 days",
            }
        return None

    # Bootstrap fallback: no trustworthy history for this bucket yet.
    if config.get("quiet_until_history"):
        return None
    multiplier = PEAK_MULTIPLIER if (travel_dt and in_detty_window(travel_dt)) else 1.0
    normal_price = round(config["normal"] * multiplier)
    if price < config["wow"] * multiplier:
        return {
            "tier": "wow",
            "label": "WOW",
            "normal_price": normal_price,
            "basis": "static threshold (thin history)",
        }
    if price < config["good"] * multiplier:
        return {
            "tier": "digest",
            "label": "Solid",
            "normal_price": normal_price,
            "basis": "static threshold (thin history)",
        }
    return None


def in_alert_window(days_out: int) -> bool:
    """Check if travel date is in our search window (2-6 months out)."""
    return MIN_DAYS_OUT <= days_out <= MAX_DAYS_OUT


# Trip configuration
TRIP_LENGTH_DAYS = 10
WEEKS_TO_SEARCH = 26  # 6 months
WEEK_STEP = 2  # scan every other week — deals persist across adjacent weeks

# Build routes
ALL_ROUTES = [
    (origin, dest, info["region"])
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
]

# Test mode: only 2 routes, only 4 weeks
TEST_MODE = False
ROUTES = ALL_ROUTES[:2] if TEST_MODE else ALL_ROUTES
SEARCH_WEEKS = 4 if TEST_MODE else WEEKS_TO_SEARCH

# Email test mode: only send to NOTIFY_EMAIL until this date
# Set to None to send to all subscribers
# (Catch-up blasts are handled separately: main() routes to Kyra only whenever
# seen_deals came up empty, regardless of this date. For a one-off send to
# everyone during the test window, use the "Resend Today's Deals" workflow.)
# 2026-07 revival warm-up: full list opens after this date.
TEST_EMAIL_ONLY_UNTIL = "2026-07-08"

# Deal tracking
SEEN_DEALS_FILE = Path(__file__).parent / "seen_deals.json"
# Alert memory. The old 14-day expiry re-alerted the SAME unchanged price
# every ~2 weeks (Kinshasa $1484 on Jul 21 came back as $1485 on Aug 8).
# Alerts now repeat only when the price BEATS the last alerted price
# (see should_alert_wow / should_include_in_digest); expiry is just a
# state-file garbage collector and a "it's been ages, worth resurfacing" cap.
DEAL_EXPIRY_DAYS = 60
WOW_REALERT_RATIO = 0.92     # re-alert a route only if 8%+ cheaper than last alert
DIGEST_REPEAT_RATIO = 0.95   # re-list in digest only if 5%+ cheaper...
DIGEST_REPEAT_DAYS = 21      # ...or it hasn't been listed in 3 weeks
DIGEST_MAX_FARES = 24        # one scannable Saturday email, not a phone book;
                             # overflow isn't recorded, so it re-competes next week

# Price history for future accuracy improvements (Phase 2)
PRICE_HISTORY_FILE = Path(__file__).parent / "price_history.jsonl"

# fast-flights health: consecutive days the scraper returned zero prices.
# At 3+ empty days the run falls back to SerpAPI and emails Kyra — the
# June 2026 breakage went unnoticed for 3 weeks; never again.
HEALTH_FILE = Path(__file__).parent / "fastflights_health.json"
EMPTY_DAYS_BEFORE_TAKEOVER = 3

# Probes that keep coming up empty burn scrape budget every run — e.g. the
# ATL-COO grid dates that return "No flights found" day after day because the
# route has no service that weekday. Airline schedules are weekday-based and
# the standard grid anchors a whole run to one weekday (see check_route), so
# the tracker keys on (route, departure weekday): after EMPTY_PROBE_MISSES
# consecutive all-empty runs the probe is skipped, then re-tested every
# EMPTY_PROBE_RETEST_DAYS in case a schedule change brings service back.
EMPTY_PROBES_FILE = Path(__file__).parent / "empty_probes.json"
EMPTY_PROBE_MISSES = 2
EMPTY_PROBE_RETEST_DAYS = 21

# Running tally so main() can tell "no deals today" from "scraper is broken"
SEARCH_STATS = {"prices_found": 0, "probes_skipped": 0}

# Per-run probe outcomes, reconciled into EMPTY_PROBES_FILE at end of run
_probe_outcomes: dict[str, dict] = {}




# ============================================================
# DEAL TRACKING
# ============================================================

def load_seen_deals() -> dict:
    """Load previously seen deals from JSON file."""
    if not SEEN_DEALS_FILE.exists():
        return {}
    try:
        with open(SEEN_DEALS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_seen_deals(deals: dict):
    """Save seen deals to JSON file."""
    with open(SEEN_DEALS_FILE, "w") as f:
        json.dump(deals, f, indent=2)


def clean_old_deals(seen_deals: dict) -> dict:
    """Remove deals older than DEAL_EXPIRY_DAYS."""
    cutoff = datetime.now() - timedelta(days=DEAL_EXPIRY_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    cleaned = {}
    for key, data in seen_deals.items():
        if data.get("last_seen", "") >= cutoff_str:
            cleaned[key] = data
    return cleaned


def load_health() -> dict:
    """Load fast-flights health state (consecutive empty-scan days)."""
    if not HEALTH_FILE.exists():
        return {"empty_days": 0}
    try:
        with open(HEALTH_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"empty_days": 0}


def save_health(health: dict):
    with open(HEALTH_FILE, "w") as f:
        json.dump(health, f, indent=2)


def load_empty_probes() -> dict:
    if not EMPTY_PROBES_FILE.exists():
        return {}
    try:
        with open(EMPTY_PROBES_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _probe_key(origin: str, dest: str, departure: str) -> str:
    weekday = datetime.strptime(departure, "%Y-%m-%d").weekday()
    return f"{origin}-{dest}:w{weekday}"


def probe_is_dead(origin: str, dest: str, departure: str) -> bool:
    """True if this (route, weekday) probe has come up empty enough runs in a
    row to skip, and its re-test window hasn't come around yet."""
    prior = EMPTY_PROBES.get(_probe_key(origin, dest, departure))
    if not prior or prior.get("misses", 0) < EMPTY_PROBE_MISSES:
        return False
    try:
        last = datetime.strptime(prior["last_tried"], "%Y-%m-%d")
    except (KeyError, ValueError):
        return False
    return (datetime.now() - last).days < EMPTY_PROBE_RETEST_DAYS


def record_probe_outcome(origin: str, dest: str, departure: str, found: bool):
    outcome = _probe_outcomes.setdefault(
        _probe_key(origin, dest, departure), {"tried": 0, "found": 0})
    outcome["tried"] += 1
    if found:
        outcome["found"] += 1


def reconcile_empty_probes():
    """Fold this run's probe outcomes into the tracker. A probe counts one
    miss per RUN where every attempt came up empty (a run's standard grid
    hits the same weekday ~13 times — that's one observation, not 13), and
    any hit clears the route+weekday entirely. Skipped entirely when the run
    found nothing at all: that's the scraper being broken (see HEALTH_FILE),
    not 44 routes going out of service at once."""
    if SEARCH_STATS["prices_found"] == 0:
        return
    today = datetime.now().strftime("%Y-%m-%d")
    for key, outcome in _probe_outcomes.items():
        if outcome["found"] > 0:
            EMPTY_PROBES.pop(key, None)
        elif outcome["tried"] > 0:
            misses = EMPTY_PROBES.get(key, {}).get("misses", 0) + 1
            EMPTY_PROBES[key] = {"misses": misses, "last_tried": today}
    with open(EMPTY_PROBES_FILE, "w") as f:
        json.dump(EMPTY_PROBES, f, indent=2)


EMPTY_PROBES = load_empty_probes()


def season_bucket(departure: str) -> str:
    """Season bucket ("std" vs "detty-<year>") for dedup keys. Keeps a
    shoulder-season deal from suppressing a Detty December deal on the same
    route, WITHOUT re-alerting when the best departure date merely hops a
    month boundary between runs (Oct 28 → Nov 4 is still the same deal)."""
    try:
        dt = datetime.strptime(departure, "%Y-%m-%d")
        if in_detty_window(dt):
            detty_year = dt.year if dt.month == 12 else dt.year - 1
            return f"detty-{detty_year}"
    except ValueError:
        pass
    return "std"


def make_deal_key(origin: str, dest: str, tier: str, departure: str) -> str:
    """Unique key for a deal (route + tier + season bucket)."""
    return f"{origin}-{dest}-{tier}-{season_bucket(departure)}"


def _alert_key(channel: str, deal: dict) -> str:
    return f"{channel}:{deal['origin']}-{deal['dest']}-{season_bucket(deal['departure'])}"


def _beats_last_alert(deal: dict, seen_deals: dict, channel: str,
                      ratio: float, max_age_days: int) -> bool:
    """True if nothing was alerted on this route+bucket+channel yet, the new
    price undercuts the last alerted price by the required margin, or the
    last alert is old enough that resurfacing is fair."""
    prior = seen_deals.get(_alert_key(channel, deal))
    if not prior:
        return True
    if deal["price"] <= round(prior["price"] * ratio):
        return True
    try:
        last = datetime.strptime(prior["last_seen"], "%Y-%m-%d")
        return (datetime.now() - last).days >= max_age_days
    except ValueError:
        return True


def should_alert_wow(deal: dict, seen_deals: dict) -> bool:
    return _beats_last_alert(deal, seen_deals, "wow",
                             WOW_REALERT_RATIO, DEAL_EXPIRY_DAYS)


def should_include_in_digest(deal: dict, seen_deals: dict) -> bool:
    return _beats_last_alert(deal, seen_deals, "digest",
                             DIGEST_REPEAT_RATIO, DIGEST_REPEAT_DAYS)


def record_alert(deal: dict, seen_deals: dict, channel: str):
    """Remember what price we alerted, per route+bucket+channel."""
    seen_deals[_alert_key(channel, deal)] = {
        "price": deal["price"],
        "tier": deal["tier"],
        "last_seen": datetime.now().strftime("%Y-%m-%d"),
        "dest_name": deal["dest_name"],
    }


# ============================================================
# PRICE HISTORY LOGGING
# ============================================================

def get_season(dt: datetime) -> str:
    """Simple season classification for logging."""
    month = dt.month
    if month in [12, 1, 2]:  # Dec-Feb (peak holiday + winter travel)
        return "peak"
    elif month in [6, 7, 8]:  # Jun-Aug (summer)
        return "summer"
    else:  # Mar-May, Sep-Nov
        return "shoulder"


def log_price_search(origin: str, dest: str, travel_date: str, return_date: str, price: int):
    """
    Log a price search to JSONL file for future accuracy improvements.
    This builds historical data to validate/improve seasonal baselines.
    """
    try:
        search_date = datetime.now()
        travel_dt = datetime.strptime(travel_date, "%Y-%m-%d")
        days_until_travel = (travel_dt - search_date).days

        record = {
            "searched_at": search_date.isoformat(),
            "origin": origin,
            "destination": dest,
            "travel_date": travel_date,
            "return_date": return_date,
            "price": price,
            "source": "fast_flights",
            "days_until_travel": days_until_travel,
            "season": get_season(travel_dt),
        }

        with open(PRICE_HISTORY_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

    except Exception as e:
        # Don't let logging failures break the main search
        print(f"      [WARN] Failed to log price: {e}")


# ============================================================
# FLIGHT SEARCH
# ============================================================

def parse_price(price_str: str) -> int | None:
    """Parse price string like '$1,234' to int. Returns None if invalid."""
    if not price_str:
        return None
    try:
        # Remove $ and commas, then convert to int
        cleaned = price_str.replace('$', '').replace(',', '').strip()
        if not cleaned or not cleaned.isdigit():
            return None
        price = int(cleaned)
        # Filter only truly invalid prices ($0 or impossibly high)
        if price < 1 or price > 10000:
            return None
        return price
    except (ValueError, AttributeError):
        return None


def search_flight(origin: str, dest: str, departure: str, return_date: str) -> dict | None:
    """
    Search for a round-trip flight using fast-flights.
    Returns: {"price": int, "departure": str, "return": str} or None
    """
    if probe_is_dead(origin, dest, departure):
        SEARCH_STATS["probes_skipped"] += 1
        return None
    try:
        result = get_flights(
            flight_data=[
                FlightData(date=departure, from_airport=origin, to_airport=dest),
                FlightData(date=return_date, from_airport=dest, to_airport=origin),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
        )

        if result and result.flights:
            # Parse all valid prices
            valid_prices = []
            for f in result.flights:
                price = parse_price(f.price)
                if price:
                    valid_prices.append(price)

            if valid_prices:
                min_price = min(valid_prices)
                SEARCH_STATS["prices_found"] += 1
                record_probe_outcome(origin, dest, departure, found=True)

                # Log price for historical data collection (Phase 2)
                log_price_search(origin, dest, departure, return_date, min_price)

                # Build direct Google Flights URL
                url = (
                    f"https://www.google.com/travel/flights?"
                    f"q=Flights%20from%20{origin}%20to%20{dest}%20"
                    f"departing%20{departure}%20returning%20{return_date}&curr=USD"
                )
                return {
                    "price": min_price,
                    "departure": departure,
                    "return": return_date,
                    "url": url
                }
        record_probe_outcome(origin, dest, departure, found=False)
        return None

    except Exception as e:
        print(f"      [ERROR] {origin}-{dest} {departure}: {e}")
        # Only a genuine "route has no flights" counts toward the dead-probe
        # tracker; network/parse failures say nothing about the schedule.
        if "no flights found" in str(e).lower():
            record_probe_outcome(origin, dest, departure, found=False)
        return None


def pick_best_deal(results: list, dest: str) -> tuple | None:
    """
    Classify each result against its own travel date (holiday-window departures
    use scaled thresholds) and return (result, classification) for the
    strongest deal — best tier first, then lowest price. None if no deal.
    """
    tier_rank = {"wow": 0, "digest": 1}
    best = None
    for result in results:
        classification = classify_deal(result["price"], dest, result["departure_dt"])
        if not classification:
            continue
        rank = (tier_rank[classification["tier"]], result["price"])
        if best is None or rank < best[0]:
            best = (rank, result, classification)
    if best is None:
        return None
    return best[1], best[2]


def build_deal(origin: str, dest: str, best_result: dict, classification: dict,
               all_prices: list, source: str = "fast_flights") -> dict:
    """Assemble the deal dict all senders/dedup consume."""
    config = DESTINATIONS.get(dest, {})
    return {
        "origin": origin,
        "dest": dest,
        "dest_name": config.get("name", dest),
        "region": config.get("region", "West Africa"),
        "price": best_result["price"],
        "tier": classification["tier"],
        "label": classification["label"],
        "normal_price": classification["normal_price"],
        "departure": best_result["departure"],
        "return": best_result["return"],
        "url": best_result["url"],
        "min_90d": classification.get("min_90d"),
        "basis": classification.get("basis", ""),
        "lowest_found": min(all_prices),
        "highest_found": max(all_prices),
        "weeks_searched": len(all_prices),
        "source": source,
    }


def check_route(origin: str, dest: str, region: str) -> list[dict]:
    """
    Check a route across ALL weeks in the search window.
    Returns up to one qualifying deal per season bucket (shoulder + Detty
    window) — a peak-window WOW must not hide a cheaper off-peak deal.
    """
    search_date = datetime.now()

    prices_found = []
    all_results = []

    # "now + N weeks" always lands on today's weekday, so a daily cron only
    # ever sampled one weekday per grid point — Tue-departure fares were
    # invisible to a Monday-anchored grid forever. Rotate the anchor by the
    # day of year so a week of daily runs covers every departure weekday.
    day_shift = (search_date.timetuple().tm_yday % 7) - 3

    print(f"    Searching every {WEEK_STEP} weeks over {SEARCH_WEEKS} weeks "
          f"(weekday shift {day_shift:+d})...")

    # Search every other week for the next 6 months
    for week in range(1, SEARCH_WEEKS + 1, WEEK_STEP):
        departure_dt = datetime.now() + timedelta(weeks=week, days=day_shift)
        days_out = (departure_dt - search_date).days

        # Skip if outside our alert window
        if not in_alert_window(days_out):
            continue

        departure_date = departure_dt.strftime("%Y-%m-%d")
        return_date = (departure_dt + timedelta(days=TRIP_LENGTH_DAYS)).strftime("%Y-%m-%d")

        result = search_flight(origin, dest, departure_date, return_date)

        if result:
            prices_found.append(result["price"])
            result["departure_dt"] = departure_dt
            all_results.append(result)

        # Small delay between requests
        time.sleep(random.uniform(0.3, 0.8))

    # Report findings
    if not prices_found:
        print(f"    No prices found")
        return []

    lowest = min(prices_found)
    highest = max(prices_found)
    print(f"    Found {len(prices_found)} prices: ${lowest} - ${highest}")

    deals = []
    for bucket_results in (
        [r for r in all_results if not in_detty_window(r["departure_dt"])],
        [r for r in all_results if in_detty_window(r["departure_dt"])],
    ):
        best = pick_best_deal(bucket_results, dest)
        if best:
            best_result, classification = best
            print(f"    🔥 {classification['label'].upper()}: ${best_result['price']} "
                  f"(dep {best_result['departure']})")
            deals.append(build_deal(
                origin, dest, best_result, classification,
                [r["price"] for r in bucket_results],
            ))

    if not deals:
        print(f"    ${lowest} lowest - not in the cheapest 10% for this route/season")
    return deals


def next_occurrence(month_day: str) -> datetime:
    """Next occurrence of 'MM-DD', at least 3 days out (late bookings count)."""
    month, day = (int(x) for x in month_day.split("-"))
    today = datetime.now()
    candidate = datetime(today.year, month, day)
    if candidate < today + timedelta(days=3):
        candidate = datetime(today.year + 1, month, day)
    return candidate


# Google Flights only sells ~330 days out; don't waste scrapes past this.
BOOKING_HORIZON_DAYS = 320


def check_detty_sweep(origin: str, dest: str) -> dict | None:
    """
    Scan the Detty December window explicitly, all year round. Deliberately
    bypasses in_alert_window() — holiday trips get booked outside the normal
    45-180 day sweet spot, and this window is the whole point of the tool.
    Dates that have rolled to next year beyond the booking horizon are
    skipped, so mid-December runs still scan the remaining holiday dates.
    Returns the best qualifying deal for this corridor, or None.
    """
    all_results = []

    print(f"    Detty sweep: {len(DETTY_DEPARTURE_DAYS)} holiday departures...")

    for month_day in DETTY_DEPARTURE_DAYS:
        departure_dt = next_occurrence(month_day)
        if (departure_dt - datetime.now()).days > BOOKING_HORIZON_DAYS:
            continue  # rolled past the bookable horizon; catch it next year
        departure_date = departure_dt.strftime("%Y-%m-%d")
        return_date = (departure_dt + timedelta(days=DETTY_TRIP_LENGTH_DAYS)).strftime("%Y-%m-%d")

        result = search_flight(origin, dest, departure_date, return_date)
        if result:
            result["departure_dt"] = departure_dt
            all_results.append(result)

        time.sleep(random.uniform(0.3, 0.8))

    if not all_results:
        print(f"    No prices found in Detty window")
        return None

    best = pick_best_deal(all_results, dest)
    if not best:
        lowest = min(r["price"] for r in all_results)
        print(f"    ${lowest} lowest in Detty window - not a deal")
        return None

    best_result, classification = best
    print(f"    🎉 DETTY {classification['label'].upper()}: ${best_result['price']}")
    return build_deal(origin, dest, best_result, classification,
                      [r["price"] for r in all_results])


# ============================================================
# EMAIL (SIMPLIFIED)
# ============================================================

def group_deals_by_dest(deals: list) -> dict:
    """Group deals by destination, keeping all origins."""
    by_dest = {}
    for deal in deals:
        dest = deal["dest"]
        if dest not in by_dest:
            by_dest[dest] = []
        by_dest[dest].append(deal)

    # Sort by price within each destination
    for dest in by_dest:
        by_dest[dest].sort(key=lambda x: x["price"])

    return by_dest


def format_departure_short(departure: str) -> str:
    """Format departure date as 'Mar 30' from '2026-03-30'."""
    try:
        dt = datetime.strptime(departure, "%Y-%m-%d")
        return dt.strftime("%b %d")
    except:
        return departure


def format_destination_card_html(dest: str, dest_deals: list) -> str:
    """Format a destination card with all origins for that destination."""
    best_deal = dest_deals[0]  # Already sorted by price
    dest_name = best_deal["dest_name"]
    tier = best_deal.get("tier", "digest")
    label = best_deal.get("label", "Deal")
    normal_price = best_deal.get("normal_price", 1200)

    # Color coding by tier
    colors = {
        "wow": {"bg": "#FEE2E2", "border": "#E31C25", "badge_bg": "#E31C25", "badge_text": "#FFF"},
        "digest": {"bg": "#F0FDF4", "border": "#009639", "badge_bg": "#009639", "badge_text": "#FFF"},
    }
    c = colors.get(tier, colors["digest"])

    # Evidence line: why this counts as a deal ("in the cheapest 5% of 312
    # prices seen in 90 days") — the receipts that make WOW believable.
    basis = best_deal.get("basis", "")
    basis_html = (
        f'<div style="font-size: 12px; color: #737373; margin-bottom: 12px;">{basis}</div>'
        if basis else ""
    )

    # Build origins list with prices - styled as clickable buttons
    origins_html = ""
    for deal in dest_deals:
        dep_short = format_departure_short(deal['departure'])
        origins_html += f'''
        <a href="{deal['url']}" style="display: inline-block; background: #E31C25; color: #FFFFFF; border-radius: 8px; padding: 10px 14px; margin: 4px; text-decoration: none; font-size: 13px; font-weight: 600;">
            {deal['origin']} ${deal['price']} →
            <span style="font-weight: 400; opacity: 0.9;">({dep_short})</span>
        </a>'''

    return f'''
    <div style="background: {c['bg']}; border: 2px solid {c['border']}; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <div style="margin-bottom: 8px;">
            <span style="background: {c['badge_bg']}; color: {c['badge_text']}; padding: 4px 12px; border-radius: 50px; font-size: 12px; font-weight: 700;">{label}</span>
        </div>
        <div style="font-size: 22px; font-weight: 800; color: #0D0D0D; margin-bottom: 4px;">
            {dest_name}
        </div>
        <div style="font-size: 14px; color: #525252; margin-bottom: 4px;">
            From <strong style="color: #009639; font-size: 18px;">${best_deal['price']}</strong> <span style="text-decoration: line-through; color: #909090;">${normal_price}</span>
        </div>
        {basis_html}
        <div style="margin-bottom: 8px;">
            {origins_html}
        </div>
    </div>
    '''


def build_email_content(deals: list, is_digest: bool = False) -> tuple[str, str, str]:
    """Build email subject and body from deals. Returns (subject, plain_body, html_body)."""
    # Group deals by destination
    grouped = group_deals_by_dest(deals)
    num_destinations = len(grouped)

    # Sort by tier priority (wow > digest), then by price
    tier_priority = {"wow": 0, "digest": 1}
    sorted_dests = sorted(
        grouped.items(),
        key=lambda x: (tier_priority.get(x[1][0].get("tier", "digest"), 2), x[1][0]["price"])
    )

    # Build subject line based on best deal
    best_tier = sorted_dests[0][1][0].get("tier", "digest")
    subject_deals = []
    for dest, dest_deals in sorted_dests[:3]:
        dest_name = dest_deals[0]["dest_name"]
        best_price = dest_deals[0]["price"]
        subject_deals.append(f"{dest_name} ${best_price}")

    if is_digest:
        subject = f"✈️ Weekly roundup: {', '.join(subject_deals)}"
    else:
        # Non-digest emails only exist for WOW fares now.
        subject = f"🚨 {subject_deals[0]} — cheapest we've seen in 90 days"

    # Build plain text body (fallback)
    plain_body = "=" * 50 + "\n"
    plain_body += "        DETTY FLIGHT DEALS\n"
    plain_body += "=" * 50 + "\n"
    plain_body += f"\n{num_destinations} deal{'s' if num_destinations != 1 else ''} found!\n\n"

    for dest, dest_deals in sorted_dests:
        best = dest_deals[0]
        label = best.get("label", "Deal")
        normal = best.get("normal_price", "?")
        plain_body += f"{label}\n"
        plain_body += f"✈️ {best['dest_name']} - ${best['price']} (usually ${normal})\n"
        for deal in dest_deals:
            plain_body += f"   • {deal['origin']} ${deal['price']} - {deal['departure']}\n"
            plain_body += f"     Book: {deal['url']}\n"
        plain_body += "\n"

    plain_body += "—" * 50 + "\n"
    plain_body += "Detty Flight Deals\n"
    plain_body += "Your personal flight radar for Africa\n"

    # Build HTML body - cards for each destination
    cards_html = ""
    for dest, dest_deals in sorted_dests:
        cards_html += format_destination_card_html(dest, dest_deals)

    # Header message based on urgency
    if is_digest:
        header_msg = "Your Saturday roundup — the week's best fares"
    elif best_tier == "wow":
        header_msg = "Rare fare — book before it's gone"
    else:
        header_msg = f"{num_destinations} deal{'s' if num_destinations != 1 else ''} worth considering"

    html_body = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; background-color: #F5F5F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">

        <!-- Header -->
        <div style="text-align: center; padding: 24px 0; margin-bottom: 24px;">
            <div style="font-size: 28px; font-weight: 800; margin-bottom: 8px;">
                ✈️ <span style="background: linear-gradient(90deg, #009639, #FCD116, #E31C25); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">Detty</span> <span style="color: #262626;">Flight Deals</span>
            </div>
            <div style="font-size: 14px; color: #525252;">
                {header_msg}
            </div>
        </div>

        <!-- Deal cards -->
        {cards_html}

        <!-- Feedback & Share -->
        <div style="background: #FFFFFF; border: 1px solid #E5E5E5; border-radius: 12px; padding: 24px; margin-top: 24px; text-align: center;">
            <div style="font-size: 18px; font-weight: 700; color: #0D0D0D; margin-bottom: 8px;">
                Booked this deal? Let us know.
            </div>
            <div style="font-size: 14px; color: #525252; margin-bottom: 16px;">
                We'd love to hear if you booked a trip! Know someone who'd love these deals? Share with them.
            </div>
            <div>
                <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display: inline-block; background: #009639; color: #FFFFFF; border-radius: 50px; padding: 12px 24px; text-decoration: none; font-size: 14px; font-weight: 600; margin: 4px;">
                    I booked this deal
                </a>
                <a href="mailto:?subject=Check%20out%20these%20Africa%20flight%20deals&body=I%20found%20cheap%20flights%20to%20Africa%20on%20Detty%20Flight%20Deals.%20Sign%20up%20here%3A%20https%3A%2F%2Fdettyflightdeals.com" style="display: inline-block; background: #FFFFFF; color: #0D0D0D; border: 2px solid #0D0D0D; border-radius: 50px; padding: 12px 24px; text-decoration: none; font-size: 14px; font-weight: 600; margin: 4px;">
                    Share with a friend
                </a>
            </div>
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 24px 0; border-top: 1px solid #E5E5E5; margin-top: 24px;">
            <div style="font-size: 12px; color: #909090;">
                You're receiving this because you signed up for Detty Flight Deals.<br>
                <a href="mailto:{SMTP_EMAIL or 'dettyflightdeals@gmail.com'}?subject=Unsubscribe%20Request&body=Hi%2C%20I%27d%20like%20to%20unsubscribe%20from%20Detty%20Flight%20Deals.%0A%0AReason%20(optional)%3A%20" style="color: #909090;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>
'''

    return subject, plain_body, html_body


def send_via_smtp(subject: str, body: str) -> bool:
    """
    Send email via Gmail SMTP (fallback for single user).
    Returns True if successful, False otherwise.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"\n📧 Email sent via SMTP to {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        print(f"\n❌ SMTP failed: {e}")
        return False


def send_to_gsheet_subscribers(subject: str, html_body: str, plain_body: str,
                               kyra_only: bool = False) -> int:
    """Send to all Google Sheet subscribers. Returns count of successful sends."""
    if not HAS_GSHEET_SUPPORT:
        print("⚠️ Google Sheets support not available")
        return 0

    # Only send to NOTIFY_EMAIL: catch-up runs, or inside the test window
    in_test_window = (
        TEST_EMAIL_ONLY_UNTIL
        and datetime.now().strftime("%Y-%m-%d") <= TEST_EMAIL_ONLY_UNTIL
    )
    if kyra_only or in_test_window:
        print(f"🧪 Only sending to {NOTIFY_EMAIL} "
              f"({'catch-up run' if kyra_only else f'test window until {TEST_EMAIL_ONLY_UNTIL}'})")
        if send_to_subscriber(NOTIFY_EMAIL, subject, html_body, plain_body):
            print(f"  ✓ {NOTIFY_EMAIL}")
            return 1
        else:
            print(f"  ✗ {NOTIFY_EMAIL}")
            return 0

    subscribers = get_subscribers()
    if not subscribers:
        print("⚠️ No subscribers found in Google Sheet")
        return 0

    print(f"\n📧 Sending to {len(subscribers)} subscribers...")
    success_count = 0
    for i, email in enumerate(subscribers, 1):
        if send_to_subscriber(email, subject, html_body, plain_body):
            success_count += 1
            print(f"  ✓ [{i}/{len(subscribers)}] {email}")
        else:
            print(f"  ✗ [{i}/{len(subscribers)}] {email}")
        # Small delay to avoid rate limiting
        if i < len(subscribers):
            time.sleep(0.5)

    print(f"\n📧 Sent to {success_count}/{len(subscribers)} subscribers")
    return success_count


def send_email(deals: list, kyra_only: bool = False, is_digest: bool = False) -> bool:
    """
    Send email with found deals. Returns True only if something was actually
    delivered — callers must not record an alert as "seen" otherwise.
    Tries Google Sheet subscribers first, falls back to SMTP (single user).
    """
    if not deals:
        return False

    # Build email content (subject, plain text, HTML)
    subject, plain_body, html_body = build_email_content(deals, is_digest=is_digest)

    # Try Google Sheet subscribers first (multi-user, HTML)
    if HAS_GSHEET_SUPPORT:
        count = send_to_gsheet_subscribers(subject, html_body, plain_body, kyra_only)
        if count > 0:
            return True  # Success via Google Sheets

    # Fall back to SMTP (single user, plain text)
    if SMTP_EMAIL and SMTP_PASSWORD:
        if send_via_smtp(subject, plain_body):
            return True  # Success via SMTP

    # No email method configured - print to console
    print("\n📧 No email delivery configured. Deals found:")
    for deal in deals:
        print(f"  🔥 {deal['origin']} → {deal['dest_name']}: ${deal['price']} ({deal.get('basis', '')})")
        print(f"     {deal['departure']} to {deal['return']}")
        print(f"     Book: {deal['url']}")
    return False




# ============================================================
# SERPAPI FALLBACK GLUE
# ============================================================
# Both hooks degrade gracefully: no SERPAPI_KEY or no quota means deals pass
# through unvalidated and takeover returns nothing — never block alerts.

def serpapi_takeover_deals() -> list:
    """Emergency deals from SerpAPI while fast-flights is down (LOS/ACC only)."""
    try:
        from serpapi_fallback import takeover_scan
        candidates = takeover_scan()
    except Exception as e:
        print(f"⚠️ SerpAPI takeover unavailable: {e}")
        return []

    by_route = {}
    for c in candidates:
        by_route.setdefault((c["origin"], c["dest"]), []).append(c)

    deals = []
    for (origin, dest), results in by_route.items():
        best = pick_best_deal(results, dest)
        if not best:
            continue
        result, classification = best
        # source="serpapi" exempts these from validate_wow_deals — no point
        # spending quota re-confirming prices SerpAPI itself just returned.
        deals.append(build_deal(origin, dest, result, classification,
                                [r["price"] for r in results], source="serpapi"))
    return deals


def validate_wow_deals(deals: list) -> list:
    """Cross-check WOW-tier deals via SerpAPI; drop only confirmed-bogus ones."""
    if not any(d["tier"] == "wow" for d in deals):
        return deals
    try:
        from serpapi_fallback import confirm_wow
    except Exception:
        return deals

    kept = []
    for deal in deals:
        if deal["tier"] != "wow" or deal.get("source") == "serpapi":
            kept.append(deal)
            continue
        verdict = confirm_wow(
            deal["origin"], deal["dest"], deal["departure"], deal["return"], deal["price"]
        )
        if verdict is False:
            print(f"  ✗ WOW not confirmed by SerpAPI, dropping: "
                  f"{deal['origin']}→{deal['dest']} ${deal['price']}")
        else:  # True, or None (couldn't check — fail open, don't hide deals)
            kept.append(deal)
    return kept


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*60}")
    print(f"Detty Deal Finder - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    standard_dates = len(range(1, SEARCH_WEEKS + 1, WEEK_STEP))
    detty_searches = len(ORIGINS) * len(DETTY_SWEEP_DESTS) * len(DETTY_DEPARTURE_DAYS)
    print(f"Mode: {'TEST' if TEST_MODE else RUN_MODE.upper()}"
          f"{' + DIGEST' if IS_DIGEST_RUN else ''}")
    print(f"Routes: {len(ROUTES)} ({len(ORIGINS)} origins × {len(DESTINATIONS)} destinations)")
    print(f"Dates: every {WEEK_STEP} weeks over {SEARCH_WEEKS} weeks ({TRIP_LENGTH_DAYS}-day trips)")
    print(f"Max searches: ~{len(ROUTES) * standard_dates} standard + {detty_searches} Detty sweep")
    print("Classification: trailing-90d stats per route/season (baselines.py);")
    print("  WOW = p5 + within 5% of the 90-day min | digest = p10 | static bands only as fallback")
    print()

    # Load and clean seen deals (for dedup)
    seen_deals = load_seen_deals()
    seen_deals = clean_old_deals(seen_deals)
    print(f"Tracking {len(seen_deals)} deals from past {DEAL_EXPIRY_DAYS} days")
    print()

    all_deals = []
    start_time = time.time()

    # Sweep mode skips the full network scan — it exists to hit the Detty
    # corridors every few hours so a flash fare gets caught the same day.
    if RUN_MODE != "sweep":
        for i, (origin, dest, region) in enumerate(ROUTES, 1):
            dest_name = DESTINATIONS.get(dest, {}).get("name", dest)
            print(f"\n[{i}/{len(ROUTES)}] {origin} → {dest_name} ({dest})")

            all_deals.extend(check_route(origin, dest, region))

            # Pause between routes
            if i < len(ROUTES):
                time.sleep(random.uniform(1, 2))

    # Detty December sweep — priority corridors, holiday window, all year
    detty_routes = [(o, d) for o in ORIGINS for d in DETTY_SWEEP_DESTS]
    for i, (origin, dest) in enumerate(detty_routes, 1):
        dest_name = DESTINATIONS.get(dest, {}).get("name", dest)
        print(f"\n[Detty {i}/{len(detty_routes)}] {origin} → {dest_name} ({dest})")

        deal = check_detty_sweep(origin, dest)
        if deal:
            all_deals.append(deal)

        if i < len(detty_routes):
            time.sleep(random.uniform(1, 2))

    # fast-flights health check: zero prices across the whole scan means the
    # scraper is broken, not that flights got expensive. Track the streak and
    # switch to the SerpAPI fallback (+ email Kyra) after 3 empty days.
    # Full runs only — the streak counts DAYS, and letting the 6-hourly sweep
    # bump it would turn one bad afternoon into a false takeover.
    health = load_health()
    if RUN_MODE == "full":
        if SEARCH_STATS["prices_found"] == 0:
            health["empty_days"] = health.get("empty_days", 0) + 1
        else:
            health["empty_days"] = 0
        health["last_run"] = datetime.now().strftime("%Y-%m-%d")
        save_health(health)

    if RUN_MODE == "full" and SEARCH_STATS["prices_found"] == 0 \
            and health["empty_days"] >= EMPTY_DAYS_BEFORE_TAKEOVER:
        print(f"\n⚠️ fast-flights returned nothing for {health['empty_days']} days — SerpAPI takeover")
        all_deals.extend(serpapi_takeover_deals())
        # Throttled: alert on day 3, then every 7th day — not daily spam.
        days = health["empty_days"]
        if days == EMPTY_DAYS_BEFORE_TAKEOVER or (days - EMPTY_DAYS_BEFORE_TAKEOVER) % 7 == 0:
            send_via_smtp(
                f"⚠️ Detty deal finder: scraper down {days} days",
                f"fast-flights has returned zero prices for {days} consecutive days.\n"
                f"SerpAPI fallback is covering the priority corridors (LOS/ACC only).\n\n"
                f"Check: https://github.com/kanwia-ai/detty-flight-deals/actions\n"
                f"Likely fix: fast-flights broke again — see requirements.txt pin comment.",
            )

    # Collapse duplicates — the standard scan and the Detty sweep can both
    # surface the same route/tier/month; keep the cheaper one.
    unique_deals = {}
    for deal in all_deals:
        key = make_deal_key(deal["origin"], deal["dest"], deal["tier"], deal["departure"])
        if key not in unique_deals or deal["price"] < unique_deals[key]["price"]:
            unique_deals[key] = deal
    all_deals = list(unique_deals.values())

    reconcile_empty_probes()

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f}s ({SEARCH_STATS['prices_found']} prices observed, "
          f"{SEARCH_STATS['probes_skipped']} dead probes skipped)")
    print(f"Found {len(all_deals)} deals in the cheapest 10% for their route/season")

    # Catch-up guard: on the first run after a state reset (seen_deals came up
    # empty) a pile of "new" deals is back-catalog, not news — route the blast
    # to Kyra only, no matter what the calendar-date test gate says.
    catch_up_run = len(seen_deals) == 0 and len(all_deals) >= 5

    # --- Immediate channel: WOW only. -----------------------------------
    # A WOW email means "drop what you're doing" — it goes out the moment a
    # fare is at/near its 90-day low AND beats whatever we last alerted on
    # that route by 8%+. Everything else waits for Saturday.
    # digest_only destinations never interrupt — their WOWs wait for Saturday.
    wow_candidates = [d for d in all_deals
                      if d["tier"] == "wow"
                      and not DESTINATIONS.get(d["dest"], {}).get("digest_only")
                      and should_alert_wow(d, seen_deals)]

    # Cross-check WOW-tier deals BEFORE recording them as seen — a bogus WOW
    # recorded now would suppress the genuine fare on that route for weeks.
    wow_deals = validate_wow_deals(wow_candidates)

    if wow_deals:
        print(f"\n🚨 {len(wow_deals)} WOW fare(s) to send!")
        if catch_up_run:
            print("🧪 Catch-up run (state was empty) — sending to Kyra only")
        if send_email(wow_deals, kyra_only=catch_up_run):
            # Record only what was actually delivered — a failed send should
            # re-alert next run, and a manual re-run right after a send
            # should NOT double-blast the list.
            for deal in wow_deals:
                record_alert(deal, seen_deals, "wow")

    # --- Weekly channel: the Saturday roundup. --------------------------
    # One email a week, only if something is in the cheapest 10%. Repeats a
    # route only when the price actually improved (or 3 quiet weeks passed).
    if IS_DIGEST_RUN:
        digest_deals = [d for d in all_deals
                        if d["tier"] == "wow" or should_include_in_digest(d, seen_deals)]
        # Keep the deepest discounts (price vs what the route normally
        # trades at) — a 45-destination fat week could qualify 100 fares.
        digest_deals.sort(key=lambda d: d["price"] / max(d.get("normal_price") or d["price"], 1))
        if len(digest_deals) > DIGEST_MAX_FARES:
            print(f"📰 Digest capped at {DIGEST_MAX_FARES} of {len(digest_deals)} qualifying fares")
            digest_deals = digest_deals[:DIGEST_MAX_FARES]
        if digest_deals:
            print(f"\n📰 Digest: {len(digest_deals)} fare(s) in this week's roundup")
            if send_email(digest_deals, kyra_only=catch_up_run, is_digest=True):
                for deal in digest_deals:
                    if deal["tier"] == "digest":
                        record_alert(deal, seen_deals, "digest")
        else:
            print("\n📰 Digest: nothing in the cheapest 10% this week — staying silent.")

    save_seen_deals(seen_deals)

    if not wow_deals and not IS_DIGEST_RUN:
        if all_deals:
            print(f"\n{len(all_deals)} sub-p10 fare(s) logged for Saturday; nothing WOW — no email.")
        else:
            print("\nNo deals found this scan.")


if __name__ == "__main__":
    main()
