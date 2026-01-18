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
# Price tiers based on market research (see pm-docs/pricing-tiers.md)
# - normal: typical market price (don't alert)
# - good: 20-30% below normal (alert free + premium)
# - great: 35-50% below normal (alert premium, occasional free)
# - wow: 50%+ below normal / mistake fare territory (alert premium only)
DESTINATIONS = {
    # West Africa - Nigeria
    "LOS": {"name": "Lagos", "region": "West Africa", "normal": 1200, "good": 900, "great": 700, "wow": 700},
    "ABV": {"name": "Abuja", "region": "West Africa", "normal": 1200, "good": 900, "great": 700, "wow": 700},

    # West Africa - Ghana
    "ACC": {"name": "Accra", "region": "West Africa", "normal": 1100, "good": 850, "great": 650, "wow": 650},

    # West Africa - Senegal
    "DSS": {"name": "Dakar", "region": "West Africa", "normal": 1000, "good": 750, "great": 550, "wow": 550},

    # West Africa - Sierra Leone
    "FNA": {"name": "Freetown", "region": "West Africa", "normal": 1100, "good": 900, "great": 700, "wow": 700},

    # West Africa - Ivory Coast
    "ABJ": {"name": "Abidjan", "region": "West Africa", "normal": 1300, "good": 1000, "great": 800, "wow": 800},

    # West Africa - Togo
    "LFW": {"name": "Lomé", "region": "West Africa", "normal": 1300, "good": 1000, "great": 750, "wow": 750},

    # West Africa - Benin
    "COO": {"name": "Cotonou", "region": "West Africa", "normal": 1200, "good": 900, "great": 700, "wow": 700},

    # Central Africa - Cameroon
    "DLA": {"name": "Douala", "region": "Central Africa", "normal": 1000, "good": 800, "great": 600, "wow": 600},
    "NSI": {"name": "Yaoundé", "region": "Central Africa", "normal": 1000, "good": 800, "great": 600, "wow": 600},

    # Central Africa - DRC
    "FIH": {"name": "Kinshasa", "region": "Central Africa", "normal": 1500, "good": 1100, "great": 850, "wow": 850},
}

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

# Price thresholds - alert if price is at or below "good" tier
PRICE_THRESHOLDS = {
    f"{origin}-{dest}": info["good"]
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
}

# Deal tracking
SEEN_DEALS_FILE = Path(__file__).parent / "seen_deals.json"
DEAL_EXPIRY_DAYS = 10  # Only consider deals "new" if not seen in past 10 days


# ============================================================
# DEAL TIER CLASSIFICATION
# ============================================================

def classify_deal_tier(price: int, dest: str) -> tuple[str, int]:
    """
    Classify a deal into tiers based on price.
    Returns: (tier_name, percent_below_normal)

    Tiers:
    - WOW: Below the "wow" threshold (50%+ below normal, mistake fare territory)
    - Great: Below the "great" threshold (35-50% below normal)
    - Good: Below the "good" threshold (20-30% below normal)
    - Normal: At or above normal price (don't alert)
    """
    thresholds = DESTINATIONS.get(dest, {})
    normal = thresholds.get("normal", 1200)
    good = thresholds.get("good", 900)
    great = thresholds.get("great", 700)
    wow = thresholds.get("wow", 600)

    percent_below = round((1 - price / normal) * 100)

    if price < wow:
        return ("WOW", percent_below)
    elif price < great:
        return ("Great", percent_below)
    elif price <= good:
        return ("Good", percent_below)
    else:
        return ("Normal", percent_below)


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
    Returns the best deal found (if under threshold).
    """
    route_key = f"{origin}-{dest}"
    max_price = PRICE_THRESHOLDS.get(route_key)
    dest_name = DESTINATIONS.get(dest, {}).get("name", dest)

    if not max_price:
        print(f"    No threshold for {route_key}")
        return None

    best_result = None
    prices_found = []

    print(f"    Searching {SEARCH_WEEKS} weeks...")

    # Search every week for the next 6 months
    for week in range(1, SEARCH_WEEKS + 1):
        departure_date = (datetime.now() + timedelta(weeks=week)).strftime("%Y-%m-%d")
        return_date = (datetime.now() + timedelta(weeks=week, days=TRIP_LENGTH_DAYS)).strftime("%Y-%m-%d")

        result = search_flight(origin, dest, departure_date, return_date)

        if result:
            prices_found.append(result["price"])
            if best_result is None or result["price"] < best_result["price"]:
                best_result = result

        # Small delay between requests
        time.sleep(random.uniform(0.3, 0.8))

    # Report findings
    if prices_found:
        lowest = min(prices_found)
        highest = max(prices_found)
        print(f"    Found {len(prices_found)} prices: ${lowest} - ${highest}")

        if best_result and best_result["price"] <= max_price:
            tier, percent_below = classify_deal_tier(best_result["price"], dest)
            normal_price = DESTINATIONS.get(dest, {}).get("normal", 1200)
            emoji = get_tier_emoji(tier)
            print(f"    {emoji} {tier} DEAL: ${best_result['price']} ({percent_below}% below ${normal_price})")
            return {
                "origin": origin,
                "dest": dest,
                "dest_name": dest_name,
                "region": region,
                "price": best_result["price"],
                "max_price": max_price,
                "tier": tier,
                "percent_below": percent_below,
                "normal_price": normal_price,
                "departure": best_result["departure"],
                "return": best_result["return"],
                "url": best_result["url"],
                "lowest_found": lowest,
                "highest_found": highest,
                "weeks_searched": len(prices_found),
            }
        else:
            print(f"    ${lowest} lowest - above ${max_price} threshold")
    else:
        print(f"    No prices found")

    return None


# ============================================================
# EMAIL
# ============================================================

def format_deal_for_email(deal: dict) -> str:
    """Format a single deal for the email body (plain text)."""
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


def build_email_content(deals: list) -> tuple[str, str]:
    """Build email subject and body from deals. Returns (subject, body)."""
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

    # Build email body
    body = "=" * 50 + "\n"
    body += "        DETTY FLIGHT DEALS\n"
    body += "=" * 50 + "\n\n"

    body += f"Found {len(deals)} deal(s) across {len(set(d['dest'] for d in deals))} destinations.\n"
    body += "Deals sorted by value (best first).\n\n"

    for deal in sorted_deals:
        body += format_deal_for_email(deal)

    body += "\n"
    body += "—" * 50 + "\n"
    body += "Detty Flight Deals\n"
    body += "Your personal flight radar for Africa\n"
    body += "\n"
    body += "Tip: WOW deals are mistake fare territory - book fast!\n"

    return subject, body


def send_via_buttondown(subject: str, body: str) -> bool:
    """
    Send email to all Buttondown subscribers.
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
                "body": body,
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
    Tries Buttondown first (multi-user), falls back to SMTP (single user).
    """
    if not deals:
        return

    # Build email content
    subject, body = build_email_content(deals)

    # Try Buttondown first (if configured)
    if BUTTONDOWN_API_KEY:
        if send_via_buttondown(subject, body):
            return  # Success via Buttondown

    # Fall back to SMTP
    if SMTP_EMAIL and SMTP_PASSWORD:
        if send_via_smtp(subject, body):
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
