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

# Tier 1 Destinations - West & Central Africa
# Seasonal baselines based on market research (see docs/plans/2026-01-19-pricing-tiers-design.md)
# Baselines represent typical prices when booking 60-90 days out
# Three seasons: off_peak, jul_peak (Jul 1 - Aug 15), dec_peak (Dec 1 - Jan 7)
DESTINATIONS = {
    # West Africa - Nigeria (high diaspora demand, big Dec premium)
    "LOS": {"name": "Lagos", "region": "West Africa", "off_peak": 900, "jul_peak": 1400, "dec_peak": 1800},
    "ABV": {"name": "Abuja", "region": "West Africa", "off_peak": 900, "jul_peak": 1450, "dec_peak": 1850},

    # West Africa - Ghana (moderate Dec premium)
    "ACC": {"name": "Accra", "region": "West Africa", "off_peak": 900, "jul_peak": 1150, "dec_peak": 1400},

    # West Africa - Senegal (less diaspora-driven)
    "DSS": {"name": "Dakar", "region": "West Africa", "off_peak": 1000, "jul_peak": 1150, "dec_peak": 1250},

    # West Africa - Sierra Leone
    "FNA": {"name": "Freetown", "region": "West Africa", "off_peak": 1100, "jul_peak": 1400, "dec_peak": 1600},

    # West Africa - Ivory Coast (Francophone, less Dec spike)
    "ABJ": {"name": "Abidjan", "region": "West Africa", "off_peak": 1300, "jul_peak": 1400, "dec_peak": 1500},

    # West Africa - Togo
    "LFW": {"name": "Lomé", "region": "West Africa", "off_peak": 1200, "jul_peak": 1350, "dec_peak": 1500},

    # West Africa - Benin
    "COO": {"name": "Cotonou", "region": "West Africa", "off_peak": 1200, "jul_peak": 1350, "dec_peak": 1500},

    # Central Africa - Cameroon (high diaspora demand, big Dec premium)
    "DLA": {"name": "Douala", "region": "Central Africa", "off_peak": 1000, "jul_peak": 1400, "dec_peak": 1800},
    "NSI": {"name": "Yaoundé", "region": "Central Africa", "off_peak": 1000, "jul_peak": 1400, "dec_peak": 1800},

    # Central Africa - DRC (stable pricing year-round)
    "FIH": {"name": "Kinshasa", "region": "Central Africa", "off_peak": 1500, "jul_peak": 1500, "dec_peak": 1500},
}

# Alert windows: only alert when booking is within appropriate window for that season
# This prevents spam from early-booking "deals" that are actually normal prices
ALERT_WINDOWS = {
    "dec_peak": (90, 240),   # 3-8 months out for December travel
    "jul_peak": (60, 180),   # 2-6 months out for July travel
    "off_peak": (45, 150),   # 1.5-5 months out for off-peak travel
}

# Tier thresholds as percentage below seasonal baseline
TIER_THRESHOLDS = {
    "wow": 0.40,    # 40%+ below = WOW (mistake fare territory)
    "great": 0.30,  # 30-39% below = Great
    "good": 0.20,   # 20-29% below = Good
}


# ============================================================
# SEASONAL PRICING LOGIC
# ============================================================

def get_season(travel_date: datetime) -> str:
    """
    Determine the travel season based on travel date.
    Returns: "dec_peak", "jul_peak", or "off_peak"
    """
    month, day = travel_date.month, travel_date.day

    # December Peak: Dec 1 - Jan 7 (Detty December + New Year)
    if month == 12 or (month == 1 and day <= 7):
        return "dec_peak"

    # July Peak: Jul 1 - Aug 15 (US summer holidays)
    if month == 7 or (month == 8 and day <= 15):
        return "jul_peak"

    return "off_peak"


def in_alert_window(days_out: int, season: str) -> bool:
    """
    Check if we're in the appropriate booking window to alert for this season.
    Prevents spam from early-booking "deals" that are actually normal prices.
    """
    min_days, max_days = ALERT_WINDOWS.get(season, (45, 150))
    return min_days <= days_out <= max_days


def get_seasonal_baseline(dest: str, travel_date: datetime) -> int:
    """Get the baseline price for a destination based on travel season."""
    season = get_season(travel_date)
    dest_info = DESTINATIONS.get(dest, {})
    return dest_info.get(season, dest_info.get("off_peak", 1000))


def should_alert(price: int, dest: str, travel_date: datetime, search_date: datetime = None) -> tuple[bool, str, int]:
    """
    Determine if we should alert for this price.
    Returns: (should_alert, tier, percent_below)

    Checks:
    1. Is the travel date within our alert window for this season?
    2. Is the price at least 20% below seasonal baseline (Good tier or better)?
    """
    if search_date is None:
        search_date = datetime.now()

    days_out = (travel_date - search_date).days
    season = get_season(travel_date)

    # Check if we're in the appropriate booking window
    if not in_alert_window(days_out, season):
        return (False, "Normal", 0)

    # Get seasonal baseline and classify
    baseline = get_seasonal_baseline(dest, travel_date)
    percent_below = (baseline - price) / baseline

    if percent_below >= TIER_THRESHOLDS["wow"]:
        return (True, "WOW", round(percent_below * 100))
    elif percent_below >= TIER_THRESHOLDS["great"]:
        return (True, "Great", round(percent_below * 100))
    elif percent_below >= TIER_THRESHOLDS["good"]:
        return (True, "Good", round(percent_below * 100))
    else:
        return (False, "Normal", round(percent_below * 100))


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
DEAL_EXPIRY_DAYS = 10  # Only consider deals "new" if not seen in past 10 days


# ============================================================
# DEAL TIER CLASSIFICATION
# ============================================================

def classify_deal_tier(price: int, dest: str, travel_date: datetime = None) -> tuple[str, int]:
    """
    Classify a deal into tiers based on price and seasonal baseline.
    Returns: (tier_name, percent_below_baseline)

    Tiers (% below seasonal baseline):
    - WOW: 40%+ below (mistake fare territory)
    - Great: 30-39% below
    - Good: 20-29% below
    - Normal: <20% below (don't alert)
    """
    # Default to off-peak if no travel date provided
    if travel_date is None:
        travel_date = datetime.now() + timedelta(days=60)

    baseline = get_seasonal_baseline(dest, travel_date)
    percent_below = (baseline - price) / baseline
    percent_below_int = round(percent_below * 100)

    if percent_below >= TIER_THRESHOLDS["wow"]:
        return ("WOW", percent_below_int)
    elif percent_below >= TIER_THRESHOLDS["great"]:
        return ("Great", percent_below_int)
    elif percent_below >= TIER_THRESHOLDS["good"]:
        return ("Good", percent_below_int)
    else:
        return ("Normal", percent_below_int)


def get_tier_emoji(tier: str) -> str:
    """Get emoji for deal tier."""
    return {
        "WOW": "🚨",
        "Great": "✨",
        "Good": "💰",
        "Normal": "📊",
    }.get(tier, "📊")


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


def make_deal_key(origin: str, dest: str, price: int) -> str:
    """Create a unique key for a deal (route + price range)."""
    # Group prices into $50 buckets to avoid spam from minor fluctuations
    price_bucket = (price // 50) * 50
    return f"{origin}-{dest}-{price_bucket}"


def is_new_deal(deal: dict, seen_deals: dict) -> bool:
    """Check if this deal is new (not seen in past 10 days)."""
    key = make_deal_key(deal["origin"], deal["dest"], deal["price"])
    return key not in seen_deals


def record_deal(deal: dict, seen_deals: dict):
    """Record a deal as seen."""
    key = make_deal_key(deal["origin"], deal["dest"], deal["price"])
    seen_deals[key] = {
        "price": deal["price"],
        "last_seen": datetime.now().strftime("%Y-%m-%d"),
        "dest_name": deal["dest_name"],
    }


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
    Returns the best deal found (if it qualifies as Good tier or better).
    Uses seasonal baselines and alert windows to determine deal quality.
    """
    dest_name = DESTINATIONS.get(dest, {}).get("name", dest)
    search_date = datetime.now()

    best_deal = None
    prices_found = []
    all_results = []

    print(f"    Searching {SEARCH_WEEKS} weeks...")

    # Search every week for the next 6 months
    for week in range(1, SEARCH_WEEKS + 1):
        departure_dt = datetime.now() + timedelta(weeks=week)
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

        # Find the best deal that qualifies (within alert window + Good tier or better)
        for result in sorted(all_results, key=lambda x: x["price"]):
            travel_date = result["departure_dt"]
            alert, tier, percent_below = should_alert(
                result["price"], dest, travel_date, search_date
            )

            if alert:
                season = get_season(travel_date)
                baseline = get_seasonal_baseline(dest, travel_date)
                emoji = get_tier_emoji(tier)
                print(f"    {emoji} {tier} DEAL: ${result['price']} ({percent_below}% below ${baseline} {season})")

                return {
                    "origin": origin,
                    "dest": dest,
                    "dest_name": dest_name,
                    "region": region,
                    "price": result["price"],
                    "tier": tier,
                    "percent_below": percent_below,
                    "normal_price": baseline,
                    "season": season,
                    "departure": result["departure"],
                    "return": result["return"],
                    "url": result["url"],
                    "lowest_found": lowest,
                    "highest_found": highest,
                    "weeks_searched": len(prices_found),
                }

        # No qualifying deals found
        print(f"    ${lowest} lowest - no deals within alert window or below threshold")
    else:
        print(f"    No prices found")

    return None


# ============================================================
# EMAIL
# ============================================================

def format_deal_for_email(deal: dict) -> str:
    """Format a single deal for the email body (plain text fallback)."""
    emoji = get_tier_emoji(deal.get("tier", "Good"))
    tier = deal.get("tier", "Good")
    percent = deal.get("percent_below", 0)
    normal = deal.get("normal_price", deal.get("max_price", 1000))

    lines = [
        f"{emoji} {tier.upper()} DEAL: {deal['origin']} → {deal['dest_name']}",
        f"",
        f"   ${deal['price']} round-trip",
        f"   {percent}% below normal (avg ${normal})",
        f"",
        f"   📅 Best dates: {deal['departure']} to {deal['return']}",
        f"   💰 Price range found: ${deal['lowest_found']} - ${deal['highest_found']}",
        f"",
        f"   🔗 Book now: {deal['url']}",
        f"",
        f"   {'─' * 40}",
        f"",
    ]
    return "\n".join(lines)


def get_tier_colors(tier: str) -> tuple[str, str, str]:
    """Get colors for deal tier (bg_color, text_color, border_color)."""
    colors = {
        "WOW": ("#FEF9C3", "#000000", "#FCD116"),      # Yellow bg
        "Great": ("#DCFCE7", "#000000", "#009639"),    # Green bg
        "Good": ("#F5F5F5", "#000000", "#525252"),     # Gray bg
        "Normal": ("#FFFFFF", "#525252", "#E5E5E5"),   # White bg
    }
    return colors.get(tier, colors["Normal"])


def format_deal_html(deal: dict) -> str:
    """Format a single deal as styled HTML."""
    tier = deal.get("tier", "Good")
    percent = deal.get("percent_below", 0)
    normal = deal.get("normal_price", deal.get("max_price", 1000))
    bg_color, text_color, border_color = get_tier_colors(tier)

    # Badge colors
    badge_colors = {
        "WOW": ("background: #FCD116; color: #000000;"),
        "Great": ("background: #009639; color: #FFFFFF;"),
        "Good": ("background: #525252; color: #FFFFFF;"),
    }
    badge_style = badge_colors.get(tier, badge_colors["Good"])

    return f'''
    <div style="background: {bg_color}; border: 2px solid {border_color}; border-radius: 12px; padding: 20px; margin-bottom: 16px;">
        <div style="margin-bottom: 12px;">
            <span style="{badge_style} padding: 4px 12px; border-radius: 50px; font-size: 12px; font-weight: 700;">{tier.upper()} DEAL</span>
        </div>
        <div style="font-size: 24px; font-weight: 800; color: #009639; margin-bottom: 4px;">
            ${deal['price']} <span style="font-size: 14px; font-weight: 400; color: #525252;">round-trip</span>
        </div>
        <div style="font-size: 18px; font-weight: 700; color: #0D0D0D; margin-bottom: 8px;">
            {deal['origin']} → {deal['dest_name']}
        </div>
        <div style="font-size: 14px; color: #525252; margin-bottom: 12px;">
            {percent}% below normal (usually ${normal})
        </div>
        <div style="font-size: 14px; color: #525252; margin-bottom: 16px;">
            📅 {deal['departure']} to {deal['return']}<br>
            💰 Prices found: ${deal['lowest_found']} - ${deal['highest_found']}
        </div>
        <a href="{deal['url']}" style="display: inline-block; background: #E31C25; color: #FFFFFF; padding: 12px 24px; border-radius: 50px; text-decoration: none; font-weight: 600; font-size: 14px;">Book Now →</a>
    </div>
    '''


def build_email_content(deals: list) -> tuple[str, str, str]:
    """Build email subject and body from deals. Returns (subject, plain_body, html_body)."""
    # Sort by tier priority (WOW > Great > Good), then by price
    tier_order = {"WOW": 0, "Great": 1, "Good": 2, "Normal": 3}
    sorted_deals = sorted(deals, key=lambda x: (tier_order.get(x.get("tier", "Good"), 3), x["price"]))

    # Count deals by tier
    tier_counts = {}
    for deal in deals:
        tier = deal.get("tier", "Good")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Build subject with tier highlights
    subject_parts = []
    if tier_counts.get("WOW", 0) > 0:
        subject_parts.append(f"{tier_counts['WOW']} WOW")
    if tier_counts.get("Great", 0) > 0:
        subject_parts.append(f"{tier_counts['Great']} Great")
    if tier_counts.get("Good", 0) > 0:
        subject_parts.append(f"{tier_counts['Good']} Good")

    if subject_parts:
        subject = f"🔥 Detty Deals: {' + '.join(subject_parts)} deal(s) to Africa!"
    else:
        subject = f"🔥 Detty Deals: {len(deals)} Africa flight deal(s)!"

    # Build plain text body (fallback)
    plain_body = "=" * 50 + "\n"
    plain_body += "        DETTY FLIGHT DEALS\n"
    plain_body += "=" * 50 + "\n\n"

    plain_body += f"Found {len(deals)} deal(s) across {len(set(d['dest'] for d in deals))} destinations.\n"
    plain_body += "Deals sorted by value (best first).\n\n"

    for deal in sorted_deals:
        plain_body += format_deal_for_email(deal)

    plain_body += "\n"
    plain_body += "—" * 50 + "\n"
    plain_body += "Detty Flight Deals\n"
    plain_body += "Your personal flight radar for Africa\n"
    plain_body += "\n"
    plain_body += "Tip: WOW deals are mistake fare territory - book fast!\n"

    # Build HTML body
    deals_html = "".join(format_deal_html(deal) for deal in sorted_deals)

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
                Found {len(deals)} deal(s) across {len(set(d['dest'] for d in deals))} destinations
            </div>
        </div>

        <!-- Deals -->
        {deals_html}

        <!-- Footer -->
        <div style="text-align: center; padding: 24px 0; border-top: 1px solid #E5E5E5; margin-top: 24px;">
            <div style="font-size: 12px; color: #525252; margin-bottom: 8px;">
                💡 <strong>WOW deals</strong> are mistake fare territory — book first, ask questions later!
            </div>
            <div style="font-size: 12px; color: #909090;">
                You're receiving this because you signed up for Detty Flight Deals.<br>
                <a href="{{{{unsubscribe_url}}}}" style="color: #909090;">Unsubscribe</a>
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


def send_email(deals: list):
    """
    Send email with found deals.
    Tries Buttondown first (multi-user, HTML), falls back to SMTP (single user, plain text).
    """
    if not deals:
        return

    # Build email content (subject, plain text, HTML)
    subject, plain_body, html_body = build_email_content(deals)

    # Try Buttondown first (if configured) - sends styled HTML
    if BUTTONDOWN_API_KEY:
        if send_via_buttondown(subject, html_body):
            return  # Success via Buttondown

    # Fall back to SMTP (plain text)
    if SMTP_EMAIL and SMTP_PASSWORD:
        if send_via_smtp(subject, plain_body):
            return  # Success via SMTP

    # No email method configured - print to console
    print("\n📧 No email delivery configured. Deals found:")
    for deal in deals:
        emoji = get_tier_emoji(deal.get("tier", "Good"))
        print(f"  {emoji} {deal.get('tier', 'Good')}: {deal['origin']} → {deal['dest_name']}: ${deal['price']}")
        print(f"     {deal.get('percent_below', 0)}% below normal")
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

    # Load and clean seen deals
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

    # Filter to only NEW deals
    new_deals = [d for d in all_deals if is_new_deal(d, seen_deals)]
    print(f"New deals (not seen in {DEAL_EXPIRY_DAYS} days): {len(new_deals)}")

    # Record ALL deals (new and old) as seen
    for deal in all_deals:
        record_deal(deal, seen_deals)
    save_seen_deals(seen_deals)
    print(f"Updated seen_deals.json ({len(seen_deals)} entries)")

    if new_deals:
        send_email(new_deals)
    else:
        print("No NEW deals today. Will check again next run.")


if __name__ == "__main__":
    main()
