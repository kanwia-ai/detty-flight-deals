"""
Detty Flight Deals - Deal Finder
Scrapes Google Flights for round-trip deals to West & Central Africa.
"""

import os
import smtplib
import re
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ============================================================
# CONFIGURATION
# ============================================================

# Email settings (set as environment variables or GitHub secrets)
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)

# Origins we're monitoring
ORIGINS = ["JFK", "IAD", "ATL"]  # New York, Washington DC, Atlanta

# West & Central Africa only - with ROUND-TRIP price thresholds
DESTINATIONS = {
    # West Africa
    "LOS": {"name": "Lagos", "region": "West Africa", "max_price": 900},
    "ACC": {"name": "Accra", "region": "West Africa", "max_price": 850},
    "DSS": {"name": "Dakar", "region": "West Africa", "max_price": 800},
    "ABV": {"name": "Abuja", "region": "West Africa", "max_price": 950},

    # Central Africa
    "DLA": {"name": "Douala", "region": "Central Africa", "max_price": 1100},
    "FIH": {"name": "Kinshasa", "region": "Central Africa", "max_price": 1200},
}

# Trip length for round-trip searches (days)
TRIP_LENGTH = 10

# How many weeks ahead to search (searches multiple dates for flexibility)
SEARCH_WEEKS_AHEAD = [8, 10, 12, 14]  # ~2-3.5 months out

# Build routes
ALL_ROUTES = [
    (origin, dest, info["region"])
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
]

# For testing: just check 3 routes. Set to False for full run.
TEST_MODE = True
ROUTES = ALL_ROUTES[:3] if TEST_MODE else ALL_ROUTES

# Price thresholds lookup
PRICE_THRESHOLDS = {
    f"{origin}-{dest}": info["max_price"]
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
}


# ============================================================
# SCRAPER
# ============================================================

def get_flight_price(origin: str, dest: str, departure_date: str, return_date: str) -> dict | None:
    """
    Scrape Google Flights for round-trip price.
    Returns: {"price": int, "url": str, "departure": str, "return": str} or None
    """
    # Google Flights round-trip URL format
    url = (
        f"https://www.google.com/travel/flights?"
        f"q=Flights%20from%20{origin}%20to%20{dest}%20"
        f"departing%20{departure_date}%20returning%20{return_date}&curr=USD"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Small random delay
            time.sleep(random.uniform(0.5, 1.5))

            page.goto(url, timeout=30000)
            page.wait_for_timeout(4000)

            # Check for blocking
            current_url = page.url
            title = page.title()

            if "sorry" in current_url.lower() or "captcha" in title.lower():
                print(f"      [BLOCKED] Google showed CAPTCHA")
                browser.close()
                return None

            content = page.content()
            content_len = len(content)

            if content_len < 10000:
                print(f"      [WARN] Page small ({content_len} chars)")

            # Find prices - multiple patterns
            prices = []

            # Pattern: $XXX or $X,XXX
            prices.extend(re.findall(r'\$(\d{1,2},?\d{3})', content))

            # Pattern: aria-label prices
            prices.extend(re.findall(r'aria-label="[^"]*\$(\d{1,2},?\d{3})', content))

            if prices:
                cleaned = [int(p.replace(',', '')) for p in prices]
                # Round-trip to Africa typically $500-$3000
                realistic = [p for p in cleaned if 400 <= p <= 4000]

                if realistic:
                    min_price = min(realistic)
                    browser.close()
                    return {
                        "price": min_price,
                        "url": url,
                        "departure": departure_date,
                        "return": return_date
                    }
                else:
                    print(f"      [DEBUG] Prices not realistic: {cleaned[:5]}")
            else:
                print(f"      [DEBUG] No prices found (page: {content_len} chars)")

            browser.close()
            return None

    except Exception as e:
        print(f"      [ERROR] {e}")
        return None


def check_route(origin: str, dest: str, region: str) -> dict | None:
    """
    Check a route across multiple dates for the best deal.
    Returns deal info if price is under threshold.
    """
    route_key = f"{origin}-{dest}"
    max_price = PRICE_THRESHOLDS.get(route_key)
    dest_name = DESTINATIONS.get(dest, {}).get("name", dest)

    if not max_price:
        print(f"    No threshold for {route_key}")
        return None

    best_result = None

    # Search multiple weeks ahead
    for weeks in SEARCH_WEEKS_AHEAD:
        departure = (datetime.now() + timedelta(weeks=weeks)).strftime("%Y-%m-%d")
        return_date = (datetime.now() + timedelta(weeks=weeks, days=TRIP_LENGTH)).strftime("%Y-%m-%d")

        print(f"      Checking {departure} - {return_date}...", end=" ")

        result = get_flight_price(origin, dest, departure, return_date)

        if result:
            print(f"${result['price']}")
            if best_result is None or result["price"] < best_result["price"]:
                best_result = result
        else:
            print("no price")

        # Be nice to Google
        time.sleep(random.uniform(2, 4))

    # Report findings
    if best_result:
        price = best_result["price"]
        if price <= max_price:
            print(f"    ✓ DEAL: ${price} (want <${max_price})")
            return {
                "origin": origin,
                "dest": dest,
                "dest_name": dest_name,
                "region": region,
                "price": price,
                "max_price": max_price,
                "departure": best_result["departure"],
                "return": best_result["return"],
                "url": best_result["url"]
            }
        else:
            print(f"    ${price} - too high (want <${max_price})")
    else:
        print(f"    No prices found")

    return None


# ============================================================
# EMAIL
# ============================================================

def send_email(deals: list):
    """Send email with found deals."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("\nEmail not configured. Deals found:")
        for deal in deals:
            print(f"  {deal['origin']} → {deal['dest_name']}: ${deal['price']}")
            print(f"    {deal['departure']} to {deal['return']}")
        return

    subject = f"🔥 Detty Deals: {len(deals)} round-trip flights to Africa!"

    body = "Round-trip deals found:\n\n"

    for deal in sorted(deals, key=lambda x: x["price"]):
        body += f"🔥 {deal['origin']} → {deal['dest_name']} ({deal['region']})\n"
        body += f"   ${deal['price']} round-trip (you wanted <${deal['max_price']})\n"
        body += f"   Dates: {deal['departure']} to {deal['return']}\n"
        body += f"   Book: {deal['url']}\n\n"

    body += "\n—\nDetty Flight Deals"

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"\nEmail sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"\nFailed to send email: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"Detty Deal Finder - {datetime.now().isoformat()}")
    print(f"Searching: Round-trip, {TRIP_LENGTH}-day trips")
    print(f"Routes: {len(ROUTES)} ({len(ORIGINS)} origins × {len(DESTINATIONS)} destinations)")
    print(f"Mode: {'TEST' if TEST_MODE else 'FULL'}\n")

    deals = []

    for origin, dest, region in ROUTES:
        dest_name = DESTINATIONS.get(dest, {}).get("name", dest)
        print(f"\n{origin} → {dest_name} ({dest})")

        deal = check_route(origin, dest, region)
        if deal:
            deals.append(deal)

        # Pause between routes
        time.sleep(random.uniform(2, 5))

    print(f"\n{'='*50}")
    print(f"Found {len(deals)} deals")

    if deals:
        send_email(deals)
    else:
        print("No deals today. Will check again next run.")


if __name__ == "__main__":
    main()
