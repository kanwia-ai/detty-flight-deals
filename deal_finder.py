"""
Detty Flight Deals - Deal Finder
Scrapes Google Flights, finds deals, emails you.
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
import time
import random

# ============================================================
# CONFIGURATION
# ============================================================

# Your email settings (set these as environment variables or GitHub secrets)
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")  # Your Gmail address
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")  # Gmail app password
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)  # Where to send alerts

# Simple price thresholds - alert if price is UNDER this amount
# Set these to what YOU would actually pay

# Origins we're monitoring
ORIGINS = ["JFK", "IAD", "ATL"]  # New York, Washington DC, Atlanta

# Destinations with price thresholds (what's a good deal to you?)
DESTINATIONS = {
    # West Africa
    "LOS": {"name": "Lagos", "region": "West Africa", "max_price": 650},
    "ACC": {"name": "Accra", "region": "West Africa", "max_price": 600},
    "DSS": {"name": "Dakar", "region": "West Africa", "max_price": 600},
    "ABV": {"name": "Abuja", "region": "West Africa", "max_price": 700},

    # East Africa
    "NBO": {"name": "Nairobi", "region": "East Africa", "max_price": 750},
    "ADD": {"name": "Addis Ababa", "region": "East Africa", "max_price": 700},
    "DAR": {"name": "Dar es Salaam", "region": "East Africa", "max_price": 800},
    "EBB": {"name": "Entebbe (Uganda)", "region": "East Africa", "max_price": 800},
    "KGL": {"name": "Kigali", "region": "East Africa", "max_price": 850},

    # Southern Africa
    "JNB": {"name": "Johannesburg", "region": "Southern Africa", "max_price": 800},
    "CPT": {"name": "Cape Town", "region": "Southern Africa", "max_price": 850},
    "HRE": {"name": "Harare", "region": "Southern Africa", "max_price": 900},

    # North Africa
    "CAI": {"name": "Cairo", "region": "North Africa", "max_price": 550},
    "CMN": {"name": "Casablanca", "region": "North Africa", "max_price": 500},

    # Central Africa
    "DLA": {"name": "Douala", "region": "Central Africa", "max_price": 800},
    "FIH": {"name": "Kinshasa", "region": "Central Africa", "max_price": 900},
}

# Build routes from origins x destinations
ROUTES = [
    (origin, dest, info["region"])
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
]

# Price thresholds lookup
PRICE_THRESHOLDS = {
    f"{origin}-{dest}": info["max_price"]
    for origin in ORIGINS
    for dest, info in DESTINATIONS.items()
}


# ============================================================
# SCRAPER
# ============================================================

def get_flight_price(origin: str, dest: str, departure_date: str) -> dict | None:
    """
    Scrape Google Flights for the cheapest price on a route.
    Returns: {"price": int, "airline": str, "stops": int} or None if failed
    """
    url = f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{departure_date}&curr=USD"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # Add some randomness to seem more human
            time.sleep(random.uniform(1, 3))

            page.goto(url, timeout=30000)

            # Wait for prices to load
            page.wait_for_timeout(5000)

            # Try to find the cheapest price
            # Google Flights shows prices in various formats
            price_selectors = [
                '[data-gs="CjR..."] span',  # Main price
                '.YMlIz',  # Price class
                '[aria-label*="$"]',  # Aria label with dollar
                'span:has-text("$")',  # Any span with $
            ]

            # Get all text content and find prices
            content = page.content()

            # Simple regex to find prices like $XXX or $X,XXX
            import re
            prices = re.findall(r'\$(\d{1,2},?\d{3})', content)

            if prices:
                # Clean and get the minimum price
                cleaned_prices = [int(p.replace(',', '')) for p in prices]
                min_price = min(cleaned_prices)

                browser.close()
                return {
                    "price": min_price,
                    "url": url
                }

            browser.close()
            return None

    except Exception as e:
        print(f"Error scraping {origin}-{dest}: {e}")
        return None


def check_route(origin: str, dest: str, region: str) -> dict | None:
    """
    Check a route for deals.
    Returns deal info if price is under threshold, None otherwise.
    """
    route_key = f"{origin}-{dest}"
    max_price = PRICE_THRESHOLDS.get(route_key)
    dest_name = DESTINATIONS.get(dest, {}).get("name", dest)

    if not max_price:
        print(f"No threshold for {route_key}, skipping")
        return None

    # Check price for 2-3 months out
    best_deal = None
    best_price = None

    for months_ahead in [2, 3]:
        departure = (datetime.now() + timedelta(days=30 * months_ahead)).strftime("%Y-%m-%d")

        result = get_flight_price(origin, dest, departure)

        if result and result["price"]:
            price = result["price"]

            # Track best price found
            if best_price is None or price < best_price:
                best_price = price

            # Is it under our threshold?
            if price <= max_price:
                if best_deal is None or price < best_deal["price"]:
                    best_deal = {
                        "origin": origin,
                        "dest": dest,
                        "dest_name": dest_name,
                        "region": region,
                        "price": price,
                        "max_price": max_price,
                        "departure": departure,
                        "url": result["url"]
                    }

        # Be nice to Google
        time.sleep(random.uniform(2, 5))

    # Show what we found
    if best_price:
        status = f"DEAL! (under ${max_price})" if best_price <= max_price else f"too high (want <${max_price})"
        print(f"    ${best_price} → {status}")
    else:
        print(f"    No prices found (looking for <${max_price})")

    return best_deal


# ============================================================
# EMAIL
# ============================================================

def send_email(deals: list):
    """Send email with found deals."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("Email not configured. Deals found:")
        for deal in deals:
            print(f"  {deal['origin']} → {deal['dest_name']}: ${deal['price']}")
        return

    # Build email content
    subject = f"🔥 Detty Deals: {len(deals)} Africa flights under your price!"

    body = "Deals found:\n\n"

    for deal in sorted(deals, key=lambda x: x["price"]):
        body += f"🔥 {deal['origin']} → {deal['dest_name']} ({deal['region']})\n"
        body += f"   ${deal['price']} (you wanted <${deal['max_price']})\n"
        body += f"   Travel: {deal['departure']}\n"
        body += f"   Book: {deal['url']}\n\n"

    body += "\n—\nDetty Flight Deals"

    # Send via Gmail SMTP
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"Email sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Failed to send email: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"Detty Deal Finder - {datetime.now().isoformat()}")
    print(f"Checking {len(ROUTES)} routes...")
    print(f"Threshold: {SAVINGS_THRESHOLD}% off baseline\n")

    deals = []

    for origin, dest, region in ROUTES:
        print(f"Checking {origin} → {dest}...")
        deal = check_route(origin, dest, region)

        if deal:
            print(f"  ✓ DEAL: ${deal['price']} ({deal['savings_pct']}% off)")
            deals.append(deal)
        else:
            print(f"  - No deal")

        # Pause between routes
        time.sleep(random.uniform(3, 8))

    print(f"\n{'='*50}")
    print(f"Found {len(deals)} deals")

    if deals:
        send_email(deals)
    else:
        print("No deals today. Will check again next run.")


if __name__ == "__main__":
    main()
