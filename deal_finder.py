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
import requests
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

# Buttondown API (for multi-user email delivery)
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY")

# Origins (7 US cities with large African diaspora populations)
ORIGINS = ["JFK", "EWR", "IAD", "ATL", "DFW", "IAH", "BOS"]

# ============================================================
# PRICE THRESHOLDS BY DESTINATION
# ============================================================
# Based on market research (Jan 2026). Thresholds define deal quality:
#   - WOW: Rare price, book immediately
#   - Great: Great deal, book soon
#   - Good: Solid price, worth considering
#
# Source: pm-docs/pricing-tiers.md

DESTINATIONS = {
    # Nigeria (highest diaspora demand)
    "LOS": {
        "name": "Lagos",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,    # 25% off
        "great": 700,   # 42% off
        "wow": 700,     # Same as great - anything under is rare
    },
    "ABV": {
        "name": "Abuja",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,
        "great": 700,
        "wow": 700,
    },
    # Ghana
    "ACC": {
        "name": "Accra",
        "region": "West Africa",
        "normal": 1100,
        "good": 850,
        "great": 650,
        "wow": 650,
    },
    # Senegal
    "DSS": {
        "name": "Dakar",
        "region": "West Africa",
        "normal": 1000,
        "good": 750,
        "great": 550,
        "wow": 550,
    },
    # Sierra Leone
    "FNA": {
        "name": "Freetown",
        "region": "West Africa",
        "normal": 1100,
        "good": 900,
        "great": 700,
        "wow": 700,
    },
    # Ivory Coast
    "ABJ": {
        "name": "Abidjan",
        "region": "West Africa",
        "normal": 1300,
        "good": 1000,
        "great": 800,
        "wow": 800,
    },
    # Togo
    "LFW": {
        "name": "Lomé",
        "region": "West Africa",
        "normal": 1300,
        "good": 1000,
        "great": 750,
        "wow": 750,
    },
    # Benin
    "COO": {
        "name": "Cotonou",
        "region": "West Africa",
        "normal": 1200,
        "good": 900,
        "great": 700,
        "wow": 700,
    },
    # Cameroon
    "DLA": {
        "name": "Douala",
        "region": "Central Africa",
        "normal": 1000,
        "good": 800,
        "great": 600,
        "wow": 600,
    },
    "NSI": {
        "name": "Yaoundé",
        "region": "Central Africa",
        "normal": 1000,
        "good": 800,
        "great": 600,
        "wow": 600,
    },
    # DRC
    "FIH": {
        "name": "Kinshasa",
        "region": "Central Africa",
        "normal": 1500,
        "good": 1100,
        "great": 850,
        "wow": 850,
    },
}

# Alert window: only search 2-6 months out (sweet spot for deals)
MIN_DAYS_OUT = 45
MAX_DAYS_OUT = 180


# ============================================================
# DEAL CLASSIFICATION
# ============================================================

def classify_deal(price: int, dest: str) -> dict | None:
    """
    Classify a deal based on price thresholds.
    Returns dict with tier and messaging, or None if not a deal.

    Tiers:
      - "wow": Rare price. Book immediately.
      - "great": Great deal. Book soon.
      - "good": Solid price. Worth considering.
    """
    config = DESTINATIONS.get(dest)
    if not config:
        return None

    if price < config["wow"]:
        return {
            "tier": "wow",
            "label": "Rare price",
            "action": "Book immediately.",
            "urgency": "high",
            "normal_price": config["normal"],
        }
    elif price < config["great"]:
        return {
            "tier": "great",
            "label": "Great deal",
            "action": "Book soon.",
            "urgency": "medium",
            "normal_price": config["normal"],
        }
    elif price < config["good"]:
        return {
            "tier": "good",
            "label": "Solid price",
            "action": "Worth considering.",
            "urgency": "low",
            "normal_price": config["normal"],
        }
    else:
        return None  # Not a deal


def in_alert_window(days_out: int) -> bool:
    """Check if travel date is in our search window (2-6 months out)."""
    return MIN_DAYS_OUT <= days_out <= MAX_DAYS_OUT


# Trip configuration
TRIP_LENGTH_DAYS = 10
WEEKS_TO_SEARCH = 26  # 6 months

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

# Deal tracking
SEEN_DEALS_FILE = Path(__file__).parent / "seen_deals.json"
DEAL_EXPIRY_DAYS = 14  # Only consider deals "new" if not seen in past 14 days

# Price history for future accuracy improvements (Phase 2)
PRICE_HISTORY_FILE = Path(__file__).parent / "price_history.jsonl"




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


def make_deal_key(origin: str, dest: str, tier: str) -> str:
    """Create a unique key for a deal (route + tier).

    Only alert when price crosses into a NEW tier, not for
    minor fluctuations within the same tier.
    """
    return f"{origin}-{dest}-{tier}"


def is_new_deal(deal: dict, seen_deals: dict) -> bool:
    """Check if this deal's tier is new (not alerted in past 10 days).

    This means:
    - JFK-LOS enters 'good' tier → SEND
    - JFK-LOS drops more but still 'good' → DON'T SEND
    - JFK-LOS enters 'great' tier → SEND
    """
    key = make_deal_key(deal["origin"], deal["dest"], deal["tier"])
    return key not in seen_deals


def record_deal(deal: dict, seen_deals: dict):
    """Record a deal's tier as seen."""
    key = make_deal_key(deal["origin"], deal["dest"], deal["tier"])
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


def check_route(origin: str, dest: str, region: str) -> dict | None:
    """
    Check a route across ALL weeks in the search window.
    Returns the best deal found if it qualifies as Good/Great/WOW.
    """
    config = DESTINATIONS.get(dest, {})
    dest_name = config.get("name", dest)
    good_threshold = config.get("good", 900)
    search_date = datetime.now()

    prices_found = []
    all_results = []

    print(f"    Searching {SEARCH_WEEKS} weeks (Good < ${good_threshold})...")

    # Search every week for the next 6 months
    for week in range(1, SEARCH_WEEKS + 1):
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
    if prices_found:
        lowest = min(prices_found)
        highest = max(prices_found)
        print(f"    Found {len(prices_found)} prices: ${lowest} - ${highest}")

        # Classify the best price
        classification = classify_deal(lowest, dest)
        if classification:
            best_result = min(all_results, key=lambda x: x["price"])
            print(f"    🔥 {classification['label'].upper()}: ${lowest} - {classification['action']}")

            return {
                "origin": origin,
                "dest": dest,
                "dest_name": dest_name,
                "region": region,
                "price": best_result["price"],
                "tier": classification["tier"],
                "label": classification["label"],
                "action": classification["action"],
                "urgency": classification["urgency"],
                "normal_price": classification["normal_price"],
                "departure": best_result["departure"],
                "return": best_result["return"],
                "url": best_result["url"],
                "lowest_found": lowest,
                "highest_found": highest,
                "weeks_searched": len(prices_found),
            }

        # No deal found
        print(f"    ${lowest} lowest - not a deal (Good < ${good_threshold})")
    else:
        print(f"    No prices found")

    return None


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
    action = best_deal.get("action", "Book soon.")
    normal_price = best_deal.get("normal_price", 1200)

    # Color coding by urgency
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
            <span style="background: {c['badge_bg']}; color: {c['badge_text']}; padding: 4px 12px; border-radius: 50px; font-size: 12px; font-weight: 700;">{label}. {action}</span>
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
        subject = f"🚨 Rare prices: {', '.join(subject_deals)}"
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
        action = best.get("action", "Book soon.")
        normal = best.get("normal_price", "?")
        plain_body += f"{label}. {action}\n"
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
        header_msg = "Rare prices found — book immediately!"
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


def send_via_buttondown(subject: str, html_body: str) -> bool:
    """
    Send styled HTML email to all Buttondown subscribers.
    Returns True if successful, False otherwise.
    """
    if not BUTTONDOWN_API_KEY:
        return False

    try:
        response = requests.post(
            "https://api.buttondown.email/v1/emails",
            headers={"Authorization": f"Token {BUTTONDOWN_API_KEY}"},
            json={
                "subject": subject,
                "body": html_body,
                "status": "sent",  # Immediately send to all subscribers
            },
            timeout=30,
        )

        if response.status_code == 201:
            data = response.json()
            print(f"\n📧 Email sent via Buttondown (ID: {data.get('id', 'unknown')})")
            return True
        else:
            print(f"\n⚠️ Buttondown error ({response.status_code}): {response.text}")
            return False

    except requests.RequestException as e:
        print(f"\n⚠️ Buttondown request failed: {e}")
        return False


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


def send_to_gsheet_subscribers(subject: str, html_body: str, plain_body: str) -> int:
    """Send to all Google Sheet subscribers. Returns count of successful sends."""
    if not HAS_GSHEET_SUPPORT:
        print("⚠️ Google Sheets support not available")
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


def send_email(deals: list):
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
        count = send_to_gsheet_subscribers(subject, html_body, plain_body)
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
# MAIN
# ============================================================

def main():
    print(f"{'='*60}")
    print(f"Detty Deal Finder - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Mode: {'TEST' if TEST_MODE else 'FULL'}")
    print(f"Routes: {len(ROUTES)} ({len(ORIGINS)} origins × {len(DESTINATIONS)} destinations)")
    print(f"Dates: {SEARCH_WEEKS} weeks ({TRIP_LENGTH_DAYS}-day trips)")
    print(f"Total searches: {len(ROUTES) * SEARCH_WEEKS}")
    print()

    # Show thresholds
    print("Alert thresholds:")
    for dest, info in DESTINATIONS.items():
        print(f"  {info['name']}: ${info['alert_under']}")
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

        deal = check_route(origin, dest, region)
        if deal:
            all_deals.append(deal)

        # Pause between routes
        if i < len(ROUTES):
            time.sleep(random.uniform(1, 2))

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f}s")
    print(f"Found {len(all_deals)} deals under threshold")

    # Only send email for NEW deals (not seen in past 10 days)
    new_deals = [d for d in all_deals if is_new_deal(d, seen_deals)]

    # Record ALL deals as seen
    for deal in all_deals:
        record_deal(deal, seen_deals)
    save_seen_deals(seen_deals)

    if new_deals:
        print(f"\n🔥 {len(new_deals)} NEW deals to send!")
        send_email(new_deals)
    elif all_deals:
        print("\nAll deals already sent recently - no email needed.")
    else:
        print("\nNo deals found this scan.")


if __name__ == "__main__":
    main()
