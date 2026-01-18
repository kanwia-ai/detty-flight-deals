"""
Detty Flight Deals - Mistake Fare Monitor
Monitors deal sites for exceptional Africa fares (25%+ below threshold).
Runs frequently (every 30 min) - lightweight RSS/web scraping.
"""

import os
import re
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError

# ============================================================
# CONFIGURATION
# ============================================================

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)

# WOW thresholds from pricing-tiers.md - mistake fare = 25% below these
# These are already the "wow" tier prices, so mistake fare = even lower
THRESHOLDS = {
    # Tier 1 cities (from pricing-tiers.md "wow" thresholds)
    "lagos": 700,
    "abuja": 700,
    "accra": 650,
    "dakar": 550,
    "freetown": 700,
    "abidjan": 800,
    "lome": 750,
    "lomé": 750,
    "cotonou": 700,
    "douala": 600,
    "yaounde": 600,
    "yaoundé": 600,
    "kinshasa": 850,
    # Countries (use lowest threshold for country)
    "nigeria": 700,
    "ghana": 650,
    "senegal": 550,
    "sierra leone": 700,
    "ivory coast": 800,
    "cote d'ivoire": 800,
    "togo": 750,
    "benin": 700,
    "cameroon": 600,
    "congo": 850,
    "drc": 850,
}

# 25% below threshold = mistake fare territory
MISTAKE_FARE_DISCOUNT = 0.25

# RSS feeds and sites to monitor
RSS_FEEDS = [
    "https://www.secretflying.com/feed/",
    "https://www.theflightdeal.com/feed/",
    "https://www.fly4free.com/feed/",
]

# Keywords to filter for Africa deals (Tier 1 cities + countries)
AFRICA_KEYWORDS = [
    # Cities (priority - check first)
    "lagos", "abuja", "accra", "dakar", "freetown", "abidjan",
    "lome", "lomé", "cotonou", "douala", "yaounde", "yaoundé", "kinshasa",
    # Countries
    "nigeria", "ghana", "senegal", "sierra leone", "ivory coast",
    "cote d'ivoire", "togo", "benin", "cameroon", "congo", "drc",
    # General
    "africa", "west africa", "central africa",
]

# Track seen deals to avoid duplicates (in-memory, resets each run)
seen_urls = set()


# ============================================================
# PARSING
# ============================================================

def extract_price(text: str) -> int | None:
    """Extract the lowest USD price from text."""
    # Match patterns like $499, $1,234, USD 499, etc.
    patterns = [
        r'\$(\d{1,2},?\d{3})',  # $499, $1,234
        r'USD\s*(\d{1,2},?\d{3})',  # USD 499
        r'(\d{3,4})\s*(?:USD|\$)',  # 499 USD
    ]

    prices = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                price = int(match.replace(',', ''))
                if 100 <= price <= 5000:  # Realistic flight price range
                    prices.append(price)
            except ValueError:
                continue

    return min(prices) if prices else None


def extract_destination(text: str) -> str | None:
    """Extract Africa destination from text."""
    text_lower = text.lower()
    # Check city names first (first 13 keywords are cities)
    for keyword in AFRICA_KEYWORDS[:13]:
        if keyword in text_lower:
            # Normalize accented characters
            return keyword.replace("é", "e").title()
    return None


def is_mistake_fare(price: int, destination: str) -> bool:
    """Check if price qualifies as a mistake fare (25%+ below threshold)."""
    dest_lower = destination.lower()
    threshold = THRESHOLDS.get(dest_lower)

    if not threshold:
        # Try to match by country
        for key, thresh in THRESHOLDS.items():
            if key in dest_lower or dest_lower in key:
                threshold = thresh
                break

    if not threshold:
        return False

    mistake_fare_price = threshold * (1 - MISTAKE_FARE_DISCOUNT)
    return price <= mistake_fare_price


# ============================================================
# RSS MONITORING
# ============================================================

def check_rss_feeds() -> list:
    """Check RSS feeds for Africa deals."""
    deals = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:20]:  # Check last 20 entries
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')

                # Skip if already seen
                if link in seen_urls:
                    continue

                # Check if it's an Africa deal
                full_text = f"{title} {summary}".lower()
                is_africa = any(kw in full_text for kw in AFRICA_KEYWORDS)

                if not is_africa:
                    continue

                # Extract price and destination
                price = extract_price(f"{title} {summary}")
                destination = extract_destination(f"{title} {summary}")

                if not price or not destination:
                    continue

                # Check if it's a mistake fare
                if is_mistake_fare(price, destination):
                    seen_urls.add(link)
                    deals.append({
                        "destination": destination,
                        "price": price,
                        "title": title,
                        "url": link,
                        "source": feed_url.split('/')[2],
                    })

        except Exception as e:
            print(f"Error checking {feed_url}: {e}")

    return deals


# ============================================================
# EMAIL
# ============================================================

def send_alert(deals: list):
    """Send email alert for mistake fares."""
    if not deals:
        return

    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("\n🚨 MISTAKE FARES FOUND (email not configured):")
        for deal in deals:
            print(f"  💰 {deal['destination']}: ${deal['price']}")
            print(f"     {deal['title']}")
            print(f"     {deal['url']}")
        return

    subject = f"🚨 MISTAKE FARE: {len(deals)} Africa deal(s) found!"

    body = "POTENTIAL MISTAKE FARES - ACT FAST!\n\n"
    body += "These prices are 25%+ below normal. Book immediately if interested.\n\n"

    for deal in deals:
        body += f"💰 {deal['destination'].upper()}: ${deal['price']}\n"
        body += f"   {deal['title']}\n"
        body += f"   Source: {deal['source']}\n"
        body += f"   Link: {deal['url']}\n\n"

    body += "\n⚠️ Mistake fares can disappear in minutes. Book first, ask questions later.\n"
    body += "\n—\nDetty Flight Deals - Mistake Fare Monitor"

    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"🚨 Mistake fare alert sent to {NOTIFY_EMAIL}")
    except Exception as e:
        print(f"Failed to send alert: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*60}")
    print(f"Mistake Fare Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Checking {len(RSS_FEEDS)} RSS feeds...")
    print(f"Looking for: 25%+ below WOW threshold (e.g., Lagos < $525, Accra < $487)\n")

    deals = check_rss_feeds()

    print(f"\nFound {len(deals)} potential mistake fares")

    if deals:
        send_alert(deals)
    else:
        print("No mistake fares right now. Will check again next run.")


if __name__ == "__main__":
    main()
