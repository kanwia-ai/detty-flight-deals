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

# Deal threshold - only alert if savings >= this percentage
SAVINGS_THRESHOLD = 25  # 25% off baseline = worth alerting

# Routes to monitor (origin, destination, region)
ROUTES = [
    # West Africa
    ("JFK", "LOS", "West Africa"),  # New York to Lagos
    ("EWR", "LOS", "West Africa"),  # Newark to Lagos
    ("LHR", "LOS", "West Africa"),  # London to Lagos
    ("JFK", "ACC", "West Africa"),  # New York to Accra
    ("LHR", "ACC", "West Africa"),  # London to Accra

    # East Africa
    ("JFK", "NBO", "East Africa"),  # New York to Nairobi
    ("LHR", "NBO", "East Africa"),  # London to Nairobi
    ("JFK", "ADD", "East Africa"),  # New York to Addis Ababa

    # Southern Africa
    ("JFK", "JNB", "Southern Africa"),  # New York to Johannesburg
    ("LHR", "JNB", "Southern Africa"),  # London to Johannesburg
    ("JFK", "CPT", "Southern Africa"),  # New York to Cape Town

    # North Africa
    ("JFK", "CAI", "North Africa"),  # New York to Cairo
    ("LHR", "CAI", "North Africa"),  # London to Cairo
]

# Baseline prices (typical/average prices for each route)
# Format: "ORIGIN-DEST": baseline_price_usd
BASELINES = {
    # West Africa (typically expensive)
    "JFK-LOS": 950,
    "EWR-LOS": 950,
    "LHR-LOS": 850,
    "JFK-ACC": 850,
    "LHR-ACC": 700,

    # East Africa
    "JFK-NBO": 1000,
    "LHR-NBO": 650,
    "JFK-ADD": 900,

    # Southern Africa
    "JFK-JNB": 1100,
    "LHR-JNB": 750,
    "JFK-CPT": 1150,

    # North Africa (cheaper)
    "JFK-CAI": 700,
    "LHR-CAI": 400,
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
    Check a route for deals across multiple dates.
    Returns deal info if found, None otherwise.
    """
    route_key = f"{origin}-{dest}"
    baseline = BASELINES.get(route_key)

    if not baseline:
        print(f"No baseline for {route_key}, skipping")
        return None

    # Check prices for dates 1-4 months out
    deals_found = []

    for months_ahead in [1, 2, 3, 4]:
        departure = (datetime.now() + timedelta(days=30 * months_ahead)).strftime("%Y-%m-%d")

        result = get_flight_price(origin, dest, departure)

        if result and result["price"]:
            price = result["price"]
            savings_pct = ((baseline - price) / baseline) * 100

            if savings_pct >= SAVINGS_THRESHOLD:
                deals_found.append({
                    "origin": origin,
                    "dest": dest,
                    "region": region,
                    "price": price,
                    "baseline": baseline,
                    "savings_pct": round(savings_pct),
                    "departure": departure,
                    "url": result["url"]
                })

        # Be nice to Google
        time.sleep(random.uniform(2, 5))

    # Return the best deal for this route
    if deals_found:
        return max(deals_found, key=lambda x: x["savings_pct"])

    return None


# ============================================================
# EMAIL
# ============================================================

def send_email(deals: list):
    """Send email with found deals."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("Email not configured. Deals found:")
        for deal in deals:
            print(f"  {deal['origin']}-{deal['dest']}: ${deal['price']} ({deal['savings_pct']}% off)")
        return

    # Build email content
    subject = f"🔥 Detty Deals: {len(deals)} Africa flight deals found!"

    body = "Deals found:\n\n"

    for deal in sorted(deals, key=lambda x: -x["savings_pct"]):
        flames = "🔥" * (3 if deal["savings_pct"] >= 50 else 2 if deal["savings_pct"] >= 40 else 1)
        body += f"{flames} {deal['origin']} → {deal['dest']} ({deal['region']})\n"
        body += f"   ${deal['price']} (was ${deal['baseline']}) — {deal['savings_pct']}% off\n"
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
