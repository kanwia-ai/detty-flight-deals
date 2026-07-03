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
# PRICE THRESHOLDS BY DESTINATION
# ============================================================
# Based on market research (Jan 2026), re-banded 2026-07-03. Thresholds define
# deal quality (classification uses strict <, so bands must not overlap):
#   - WOW: rare price, book immediately
#   - Great: strong deal, book soon
#   - Good: worth booking
#
# Source: pm-docs/pricing-tiers.md. The original config set wow == great on
# most routes, which made the Great tier unreachable; wow keeps the original
# hand-tuned "rare" price and great now sits between wow and good.

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
DETTY_SWEEP_DESTS = ["LOS", "ACC"]
DETTY_DEPARTURE_DAYS = ["12-15", "12-18", "12-20", "12-22", "12-26"]  # MM-DD
DETTY_TRIP_LENGTH_DAYS = 14


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
    Classify a deal based on price thresholds.
    Returns dict with tier and messaging, or None if not a deal.

    Holiday-window departures are judged against thresholds scaled by
    PEAK_MULTIPLIER, since Detty December fares run far above shoulder season.

    Tiers:
      - "wow": WOW deal. Book immediately.
      - "great": Great deal. Book soon.
      - "good": Good deal. Worth booking.
    """
    config = DESTINATIONS.get(dest)
    if not config:
        return None

    multiplier = PEAK_MULTIPLIER if (travel_dt and in_detty_window(travel_dt)) else 1.0
    normal_price = round(config["normal"] * multiplier)

    if price < config["wow"] * multiplier:
        return {
            "tier": "wow",
            "label": "WOW",
            "normal_price": normal_price,
        }
    elif price < config["great"] * multiplier:
        return {
            "tier": "great",
            "label": "Great",
            "normal_price": normal_price,
        }
    elif price < config["good"] * multiplier:
        return {
            "tier": "good",
            "label": "Good",
            "normal_price": normal_price,
        }
    else:
        return None  # Not a deal


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
# seen_deals came up empty, regardless of this date.)
# 2026-07-03: Kyra approved full-list delivery after reviewing the revival run.
TEST_EMAIL_ONLY_UNTIL = None

# Deal tracking
SEEN_DEALS_FILE = Path(__file__).parent / "seen_deals.json"
DEAL_EXPIRY_DAYS = 14  # Only consider deals "new" if not seen in past 14 days

# Price history for future accuracy improvements (Phase 2)
PRICE_HISTORY_FILE = Path(__file__).parent / "price_history.jsonl"

# fast-flights health: consecutive days the scraper returned zero prices.
# At 3+ empty days the run falls back to SerpAPI and emails Kyra — the
# June 2026 breakage went unnoticed for 3 weeks; never again.
HEALTH_FILE = Path(__file__).parent / "fastflights_health.json"
EMPTY_DAYS_BEFORE_TAKEOVER = 3

# Running tally so main() can tell "no deals today" from "scraper is broken"
SEARCH_STATS = {"prices_found": 0}




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


def make_deal_key(origin: str, dest: str, tier: str, departure: str) -> str:
    """Create a unique key for a deal (route + tier + season bucket).

    Only alert when price crosses into a NEW tier, not for minor fluctuations
    within the same tier. The season bucket ("std" vs "detty-<year>") keeps a
    shoulder-season deal from suppressing a Detty December deal on the same
    route, WITHOUT re-alerting when the best departure date merely hops a
    month boundary between runs (Oct 28 → Nov 4 is still the same deal).
    """
    try:
        dt = datetime.strptime(departure, "%Y-%m-%d")
        if in_detty_window(dt):
            detty_year = dt.year if dt.month == 12 else dt.year - 1
            bucket = f"detty-{detty_year}"
        else:
            bucket = "std"
    except ValueError:
        bucket = "std"
    return f"{origin}-{dest}-{tier}-{bucket}"


def is_new_deal(deal: dict, seen_deals: dict) -> bool:
    """Check if this deal's tier is new (not alerted in past 14 days).

    This means:
    - JFK-LOS enters 'good' tier → SEND
    - JFK-LOS drops more but still 'good' → DON'T SEND
    - JFK-LOS enters 'great' tier → SEND
    """
    key = make_deal_key(deal["origin"], deal["dest"], deal["tier"], deal["departure"])
    return key not in seen_deals


def record_deal(deal: dict, seen_deals: dict):
    """Record a deal's tier as seen."""
    key = make_deal_key(deal["origin"], deal["dest"], deal["tier"], deal["departure"])
    seen_deals[key] = {
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
        return None

    except Exception as e:
        print(f"      [ERROR] {origin}-{dest} {departure}: {e}")
        return None


def pick_best_deal(results: list, dest: str) -> tuple | None:
    """
    Classify each result against its own travel date (holiday-window departures
    use scaled thresholds) and return (result, classification) for the
    strongest deal — best tier first, then lowest price. None if no deal.
    """
    tier_rank = {"wow": 0, "great": 1, "good": 2}
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
    config = DESTINATIONS.get(dest, {})
    dest_name = config.get("name", dest)
    good_threshold = config.get("good", 900)
    search_date = datetime.now()

    prices_found = []
    all_results = []

    print(f"    Searching every {WEEK_STEP} weeks over {SEARCH_WEEKS} weeks (Good < ${good_threshold})...")

    # Search every other week for the next 6 months
    for week in range(1, SEARCH_WEEKS + 1, WEEK_STEP):
        departure_dt = datetime.now() + timedelta(weeks=week)
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
        print(f"    ${lowest} lowest - not a deal (Good < ${good_threshold})")
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
    tier = best_deal.get("tier", "good")
    label = best_deal.get("label", "Deal")
    normal_price = best_deal.get("normal_price", 1200)

    # Color coding by tier
    colors = {
        "wow": {"bg": "#FEE2E2", "border": "#E31C25", "badge_bg": "#E31C25", "badge_text": "#FFF"},
        "great": {"bg": "#FFFDE7", "border": "#FCD116", "badge_bg": "#FCD116", "badge_text": "#000"},
        "good": {"bg": "#F0FDF4", "border": "#009639", "badge_bg": "#009639", "badge_text": "#FFF"},
    }
    c = colors.get(tier, colors["good"])

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
        <div style="font-size: 14px; color: #525252; margin-bottom: 12px;">
            From <strong style="color: #009639; font-size: 18px;">${best_deal['price']}</strong> <span style="text-decoration: line-through; color: #909090;">${normal_price}</span>
        </div>
        <div style="margin-bottom: 8px;">
            {origins_html}
        </div>
    </div>
    '''


def build_email_content(deals: list) -> tuple[str, str, str]:
    """Build email subject and body from deals. Returns (subject, plain_body, html_body)."""
    # Group deals by destination
    grouped = group_deals_by_dest(deals)
    num_destinations = len(grouped)

    # Sort by tier priority (wow > great > good), then by price
    tier_priority = {"wow": 0, "great": 1, "good": 2}
    sorted_dests = sorted(
        grouped.items(),
        key=lambda x: (tier_priority.get(x[1][0].get("tier", "good"), 2), x[1][0]["price"])
    )

    # Build subject line based on best deal
    best_tier = sorted_dests[0][1][0].get("tier", "good")
    subject_deals = []
    for dest, dest_deals in sorted_dests[:3]:
        dest_name = dest_deals[0]["dest_name"]
        best_price = dest_deals[0]["price"]
        subject_deals.append(f"{dest_name} ${best_price}")

    if best_tier == "wow":
        subject = f"🚨 WOW Deals: {', '.join(subject_deals)}"
    elif best_tier == "great":
        subject = f"🔥 Great deals: {', '.join(subject_deals)}"
    else:
        subject = f"✈️ Detty Deals: {', '.join(subject_deals)}"

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
    if best_tier == "wow":
        header_msg = "WOW deals found — book immediately!"
    elif best_tier == "great":
        header_msg = f"{num_destinations} great deal{'s' if num_destinations != 1 else ''} found"
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


def send_email(deals: list, kyra_only: bool = False):
    """
    Send email with found deals.
    Tries Google Sheet subscribers first, falls back to SMTP (single user).
    """
    if not deals:
        return

    # Build email content (subject, plain text, HTML)
    subject, plain_body, html_body = build_email_content(deals)

    # Try Google Sheet subscribers first (multi-user, HTML)
    if HAS_GSHEET_SUPPORT:
        count = send_to_gsheet_subscribers(subject, html_body, plain_body, kyra_only)
        if count > 0:
            return  # Success via Google Sheets

    # Fall back to SMTP (single user, plain text)
    if SMTP_EMAIL and SMTP_PASSWORD:
        if send_via_smtp(subject, plain_body):
            return  # Success via SMTP

    # No email method configured - print to console
    print("\n📧 No email delivery configured. Deals found:")
    for deal in deals:
        print(f"  🔥 {deal['origin']} → {deal['dest_name']}: ${deal['price']} (threshold: ${deal.get('threshold', '?')})")
        print(f"     {deal['departure']} to {deal['return']}")
        print(f"     Book: {deal['url']}")




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
    print(f"Mode: {'TEST' if TEST_MODE else 'FULL'}")
    print(f"Routes: {len(ROUTES)} ({len(ORIGINS)} origins × {len(DESTINATIONS)} destinations)")
    print(f"Dates: every {WEEK_STEP} weeks over {SEARCH_WEEKS} weeks ({TRIP_LENGTH_DAYS}-day trips)")
    print(f"Max searches: ~{len(ROUTES) * standard_dates} standard + {detty_searches} Detty sweep")
    print()

    # Show thresholds
    print("Alert thresholds (Good / Great / WOW):")
    for dest, info in DESTINATIONS.items():
        print(f"  {info['name']}: ${info['good']} / ${info['great']} / ${info['wow']}")
    print()

    # Load and clean seen deals (for dedup)
    seen_deals = load_seen_deals()
    seen_deals = clean_old_deals(seen_deals)
    print(f"Tracking {len(seen_deals)} deals from past {DEAL_EXPIRY_DAYS} days")
    print()

    all_deals = []
    start_time = time.time()

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
    health = load_health()
    if SEARCH_STATS["prices_found"] == 0:
        health["empty_days"] = health.get("empty_days", 0) + 1
    else:
        health["empty_days"] = 0
    health["last_run"] = datetime.now().strftime("%Y-%m-%d")
    save_health(health)

    if SEARCH_STATS["prices_found"] == 0 and health["empty_days"] >= EMPTY_DAYS_BEFORE_TAKEOVER:
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

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f}s ({SEARCH_STATS['prices_found']} prices observed)")
    print(f"Found {len(all_deals)} deals under threshold")

    # Only send email for NEW deals (not seen in past 14 days)
    new_deals = [d for d in all_deals if is_new_deal(d, seen_deals)]

    # Catch-up guard: on the first run after a state reset (seen_deals came up
    # empty) a pile of "new" deals is back-catalog, not news — route the blast
    # to Kyra only, no matter what the calendar-date test gate says.
    catch_up_run = len(seen_deals) == 0 and len(new_deals) >= 5

    # Cross-check WOW-tier deals BEFORE recording them as seen — a bogus WOW
    # recorded now would suppress the genuine fare on that route for 14 days.
    validated_new = validate_wow_deals(new_deals)
    dropped_as_bogus = {id(d) for d in new_deals} - {id(d) for d in validated_new}
    new_deals = validated_new

    # Record deals as seen (except the ones dropped as bogus)
    for deal in all_deals:
        if id(deal) in dropped_as_bogus:
            continue
        record_deal(deal, seen_deals)
    save_seen_deals(seen_deals)

    if new_deals:
        print(f"\n🔥 {len(new_deals)} NEW deals to send!")
        if catch_up_run:
            print("🧪 Catch-up run (state was empty) — sending to Kyra only")
        send_email(new_deals, kyra_only=catch_up_run)
    elif all_deals:
        print("\nAll deals already sent recently - no email needed.")
    else:
        print("\nNo deals found this scan.")


if __name__ == "__main__":
    main()
