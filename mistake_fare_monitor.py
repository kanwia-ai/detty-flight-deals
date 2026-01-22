"""
Detty Flight Deals - Mistake Fare Monitor
Monitors deal sites for exceptional Africa fares (25%+ below threshold).
Runs frequently (every 30 min) - lightweight RSS checking.
"""

import json
import os
import re
import smtplib
import time
import feedparser
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Import Google Sheets subscriber functions from mvp0_sender
try:
    from mvp0_sender import get_subscribers, send_to_subscriber
    HAS_GSHEET_SUPPORT = True
except ImportError:
    HAS_GSHEET_SUPPORT = False

# ============================================================
# CONFIGURATION
# ============================================================

SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", SMTP_EMAIL)
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY")

# Persistent state for deduplication
SEEN_DEALS_FILE = Path(__file__).parent / "seen_mistake_fares.json"
DEAL_EXPIRY_HOURS = 72  # 3 days - mistake fares are time-sensitive

# Email test mode: only send to NOTIFY_EMAIL until this date
# Set to None to send to all subscribers
TEST_EMAIL_ONLY_UNTIL = "2026-01-29"  # One week test period

# Destinations with thresholds - synced with deal_finder.py research
# Format: code -> (name, normal_price, good, great, wow)
DESTINATIONS = {
    "LOS": ("Lagos", 1200, 900, 700, 700),
    "ABV": ("Abuja", 1200, 900, 700, 700),
    "ACC": ("Accra", 1100, 850, 650, 650),
    "DSS": ("Dakar", 1000, 750, 550, 550),
    "FNA": ("Freetown", 1100, 900, 700, 700),
    "ABJ": ("Abidjan", 1300, 1000, 800, 800),
    "LFW": ("Lomé", 1300, 1000, 750, 750),
    "COO": ("Cotonou", 1200, 900, 700, 700),
    "DLA": ("Douala", 1000, 800, 600, 600),
    "NSI": ("Yaoundé", 1000, 800, 600, 600),
    "FIH": ("Kinshasa", 1500, 1100, 850, 850),
}

# Build lookup by city name and country
CITY_THRESHOLDS = {
    info[0].lower(): {"normal": info[1], "good": info[2], "great": info[3], "wow": info[4]}
    for info in DESTINATIONS.values()
}
CITY_THRESHOLDS.update({
    info[0].lower().replace("é", "e"): {"normal": info[1], "good": info[2], "great": info[3], "wow": info[4]}
    for info in DESTINATIONS.values()
})
# IATA codes
CITY_THRESHOLDS.update({
    code.lower(): {"normal": info[1], "good": info[2], "great": info[3], "wow": info[4]}
    for code, info in DESTINATIONS.items()
})
# Countries (use Nigeria thresholds as default)
COUNTRY_THRESHOLDS = {
    "nigeria": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    "ghana": {"normal": 1100, "good": 850, "great": 650, "wow": 650},
    "senegal": {"normal": 1000, "good": 750, "great": 550, "wow": 550},
    "sierra leone": {"normal": 1100, "good": 900, "great": 700, "wow": 700},
    "ivory coast": {"normal": 1300, "good": 1000, "great": 800, "wow": 800},
    "cote d'ivoire": {"normal": 1300, "good": 1000, "great": 800, "wow": 800},
    "togo": {"normal": 1300, "good": 1000, "great": 750, "wow": 750},
    "benin": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    "cameroon": {"normal": 1000, "good": 800, "great": 600, "wow": 600},
    "congo": {"normal": 1500, "good": 1100, "great": 850, "wow": 850},
    "drc": {"normal": 1500, "good": 1100, "great": 850, "wow": 850},
}

# RSS feeds with source names
RSS_FEEDS = [
    ("https://www.secretflying.com/feed/", "secretflying"),
    ("https://www.theflightdeal.com/feed/", "theflightdeal"),
    ("https://www.fly4free.com/feed/", "fly4free"),
    ("https://www.travelpirates.com/feed", "travelpirates"),
    ("https://deals.thepointsguy.com/feed", "thepointsguy"),
]

# Keywords to filter for Africa deals
AFRICA_KEYWORDS = [
    # Cities from DESTINATIONS
    *[info[0].lower() for info in DESTINATIONS.values()],
    *[info[0].lower().replace("é", "e") for info in DESTINATIONS.values()],
    # IATA codes
    *[code.lower() for code in DESTINATIONS.keys()],
    # Countries
    "nigeria", "ghana", "senegal", "sierra leone", "ivory coast",
    "cote d'ivoire", "togo", "benin", "cameroon", "congo", "drc",
    # General
    "africa", "west africa", "central africa",
]

# US origins (airports & cities)
US_ORIGINS = {
    # Major airports
    "jfk", "ewr", "lga", "iad", "dca", "bwi", "atl", "dfw", "iah",
    "ord", "mdw", "lax", "sfo", "oak", "sjc", "bos", "mia", "fll",
    "den", "sea", "phl", "phx", "msp", "dtw", "clt", "las",
    # Cities
    "new york", "newark", "washington", "atlanta", "dallas", "houston",
    "chicago", "los angeles", "san francisco", "boston", "miami",
    "denver", "seattle", "philadelphia", "phoenix", "minneapolis",
    "detroit", "charlotte", "las vegas",
}

# EU origins (airports & cities)
EU_ORIGINS = {
    # Major airports
    "lhr", "lgw", "stn", "cdg", "ory", "fra", "ams", "mad", "bcn",
    "fco", "mxp", "dub", "lis", "bru", "vie", "zrh", "muc", "cph",
    "osl", "arn", "hel",
    # Cities
    "london", "paris", "frankfurt", "amsterdam", "madrid", "barcelona",
    "rome", "milan", "dublin", "lisbon", "brussels", "vienna", "zurich",
    "munich", "copenhagen", "oslo", "stockholm", "helsinki",
}

VALID_ORIGINS = US_ORIGINS | EU_ORIGINS


# ============================================================
# PERSISTENT DEDUPLICATION
# ============================================================

def load_seen_deals() -> dict:
    """Load seen deals from JSON file."""
    if not SEEN_DEALS_FILE.exists():
        return {}
    try:
        with open(SEEN_DEALS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_seen_deals(seen: dict):
    """Save seen deals to JSON file."""
    with open(SEEN_DEALS_FILE, 'w') as f:
        json.dump(seen, f, indent=2)


def is_deal_seen(url: str, seen: dict) -> bool:
    """Check if deal was seen in past 72 hours."""
    if url not in seen:
        return False
    try:
        last_seen = datetime.fromisoformat(seen[url]["last_seen"])
        return (datetime.now() - last_seen).total_seconds() < DEAL_EXPIRY_HOURS * 3600
    except (KeyError, ValueError):
        return False


# ============================================================
# ORIGIN FILTERING
# ============================================================

def extract_origin(text: str) -> str | None:
    """Extract origin city/airport from deal text."""
    text_lower = text.lower()

    # Pattern: "from [origin] to" or "[origin] – [destination]"
    patterns = [
        r'from\s+([a-z\s]+?)\s+to\b',
        r'^([a-z\s]+?)\s*[-–]\s*[a-z]',
        r'\bfrom\s+([a-z]{3})\b',  # IATA code
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            origin = match.group(1).strip()
            if origin in VALID_ORIGINS or any(v in origin for v in VALID_ORIGINS):
                return origin

    # Fallback: check if any valid origin appears in text
    for origin in VALID_ORIGINS:
        if origin in text_lower:
            return origin

    return None


def is_valid_origin(text: str) -> bool:
    """Check if deal originates from US or EU."""
    return extract_origin(text) is not None


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


def get_thresholds_for_dest(destination: str) -> dict | None:
    """Get price thresholds for a destination."""
    dest_lower = destination.lower()

    # Try city name first
    if dest_lower in CITY_THRESHOLDS:
        return CITY_THRESHOLDS[dest_lower]

    # Try country
    for country, thresholds in COUNTRY_THRESHOLDS.items():
        if country in dest_lower or dest_lower in country:
            return thresholds

    return None


def classify_deal(price: int, destination: str, text: str) -> dict | None:
    """
    Classify a deal based on price thresholds.
    Returns dict with tier info, or None if not a deal.

    - "wow": WOW. Book immediately. (Also if RSS explicitly says mistake/error fare)
    - "great": Great deal. Book soon.
    - "good": Good deal. Worth booking.
    """
    thresholds = get_thresholds_for_dest(destination)
    if not thresholds:
        return None

    # ONLY alert on explicit mistake/error fares from RSS
    # Regular Good/Great/WOW deals are handled by deal_finder.py
    text_lower = text.lower()
    is_explicit_mistake = any(term in text_lower for term in [
        "mistake fare", "error fare", "pricing error", "glitch fare",
        "mistake-fare", "error-fare"
    ])

    if not is_explicit_mistake:
        return None  # Skip - let deal_finder.py handle regular deals

    return {
        "tier": "mistake",
        "label": "OMO!",
        "action": "Book NOW. May not be honored.",
        "urgency": "critical",
        "normal_price": thresholds["normal"],
    }


# ============================================================
# RSS MONITORING
# ============================================================

def check_rss_feeds(seen_deals: dict) -> list:
    """Check RSS feeds for Africa deals from US/EU."""
    deals = []

    for feed_url, source_name in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:20]:  # Check last 20 entries
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                full_text = f"{title} {summary}"

                # Skip if already seen
                if is_deal_seen(link, seen_deals):
                    continue

                # Check if it's an Africa deal
                if not any(kw in full_text.lower() for kw in AFRICA_KEYWORDS):
                    continue

                # Check if origin is US or EU
                if not is_valid_origin(full_text):
                    continue

                # Extract price and destination
                price = extract_price(full_text)
                destination = extract_destination(full_text)

                if not price or not destination:
                    continue

                # Classify the deal
                classification = classify_deal(price, destination, full_text)
                if classification:
                    origin = extract_origin(full_text)
                    deals.append({
                        "destination": destination,
                        "price": price,
                        "title": title,
                        "url": link,
                        "source": source_name,
                        "origin": origin,
                        "tier": classification["tier"],
                        "label": classification["label"],
                        "action": classification["action"],
                        "urgency": classification["urgency"],
                        "normal_price": classification["normal_price"],
                    })
                    # Mark as seen
                    seen_deals[link] = {
                        "last_seen": datetime.now().isoformat(),
                        "destination": destination,
                        "price": price,
                        "tier": classification["tier"],
                    }

        except Exception as e:
            print(f"Error checking {feed_url}: {e}")

    return deals


# ============================================================
# EMAIL
# ============================================================

def send_via_buttondown(subject: str, body: str) -> bool:
    """Send email to all Buttondown subscribers."""
    if not BUTTONDOWN_API_KEY:
        return False

    try:
        response = requests.post(
            "https://api.buttondown.email/v1/emails",
            headers={"Authorization": f"Token {BUTTONDOWN_API_KEY}"},
            json={
                "subject": subject,
                "body": body,
                "status": "sent",
            },
            timeout=30,
        )

        if response.status_code == 201:
            print(f"🚨 Mistake fare alert sent via Buttondown")
            return True
        else:
            print(f"⚠️ Buttondown error ({response.status_code}): {response.text}")
            return False

    except requests.RequestException as e:
        print(f"⚠️ Buttondown request failed: {e}")
        return False


def send_via_smtp(subject: str, body: str) -> bool:
    """Send email via Gmail SMTP."""
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
        print(f"🚨 Mistake fare alert sent via SMTP to {NOTIFY_EMAIL}")
        return True
    except Exception as e:
        print(f"❌ SMTP failed: {e}")
        return False


def build_deal_card_html(deal: dict) -> str:
    """Build HTML card for a single deal."""
    tier = deal.get("tier", "good")
    label = deal.get("label", "Deal")
    action = deal.get("action", "Book soon.")
    normal_price = deal.get("normal_price", 1200)

    # Color coding by tier
    colors = {
        "mistake": {"bg": "#F3E8FF", "border": "#7C3AED", "badge_bg": "#7C3AED", "badge_text": "#FFF"},  # Purple
        "wow": {"bg": "#FEE2E2", "border": "#E31C25", "badge_bg": "#E31C25", "badge_text": "#FFF"},
        "great": {"bg": "#FFFDE7", "border": "#FCD116", "badge_bg": "#FCD116", "badge_text": "#000"},
        "good": {"bg": "#F0FDF4", "border": "#009639", "badge_bg": "#009639", "badge_text": "#FFF"},
    }
    c = colors.get(tier, colors["good"])

    title_truncated = deal['title'][:100] + "..." if len(deal['title']) > 100 else deal['title']

    return f'''
    <div style="background:{c['bg']};border:2px solid {c['border']};border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="margin-bottom:12px;">
            <span style="background:{c['badge_bg']};color:{c['badge_text']};padding:4px 12px;border-radius:50px;font-size:12px;font-weight:700;">{label}. {action}</span>
        </div>
        <div style="font-size:24px;font-weight:800;color:#0D0D0D;margin-bottom:4px;">
            ${deal['price']} <span style="font-size:14px;font-weight:400;color:#525252;">to {deal['destination'].title()}</span>
            <span style="font-size:14px;text-decoration:line-through;color:#909090;">${normal_price}</span>
        </div>
        <div style="font-size:14px;color:#525252;margin-bottom:8px;">
            From: {deal.get('origin', 'US/EU').upper()} | Source: {deal['source']}
        </div>
        <div style="font-size:14px;color:#0D0D0D;margin-bottom:16px;">
            {title_truncated}
        </div>
        <a href="{deal['url']}" style="display:inline-block;background:{c['border']};color:#FFF;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">Book NOW →</a>
    </div>
    '''


def build_deals_html(deals: list) -> str:
    """Build HTML email for deal alerts."""
    # Sort by tier priority (mistake > wow > great > good)
    tier_priority = {"mistake": 0, "wow": 1, "great": 2, "good": 3}
    sorted_deals = sorted(deals, key=lambda d: (tier_priority.get(d.get("tier", "good"), 3), d["price"]))

    # Build cards
    deals_html = ""
    for deal in sorted_deals:
        deals_html += build_deal_card_html(deal)

    # Determine header style based on best deal
    best_tier = sorted_deals[0].get("tier", "good") if sorted_deals else "good"

    if best_tier == "mistake":
        header_bg = "#7C3AED"  # Purple for mistake fares
        header_title = "🚨 OMO! Mistake Fare"
        header_sub = "Book NOW — airline may fix this anytime!"
    elif best_tier == "wow":
        header_bg = "#E31C25"
        header_title = "🚨 WOW Deals Found"
        header_sub = "Book immediately — these won't last!"
    elif best_tier == "great":
        header_bg = "#FCD116"
        header_title = "🔥 Great deals found"
        header_sub = "Book soon — prices this good don't last long"
    else:
        header_bg = "#009639"
        header_title = "✈️ Deals found"
        header_sub = "Good deals worth booking"

    header_text_color = "#000" if best_tier == "great" else "#FFF"

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">

        <!-- Header -->
        <div style="text-align:center;padding:24px 0;margin-bottom:24px;background:{header_bg};border-radius:12px;">
            <div style="font-size:24px;font-weight:800;color:{header_text_color};margin-bottom:8px;">
                {header_title}
            </div>
            <div style="font-size:14px;color:{header_text_color};opacity:0.9;">
                {header_sub}
            </div>
        </div>

        <!-- Deals -->
        {deals_html}

        <!-- Feedback -->
        <div style="background:#FFF;border:1px solid #E5E5E5;border-radius:12px;padding:20px;margin-top:16px;text-align:center;">
            <div style="font-size:16px;font-weight:700;color:#0D0D0D;margin-bottom:12px;">
                Booked this deal? Let us know!
            </div>
            <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display:inline-block;background:#009639;color:#FFF;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:600;font-size:13px;">I booked!</a>
            <a href="mailto:?subject=Check%20out%20this%20Africa%20flight%20deal&body=Found%20this%20on%20Detty%20Flight%20Deals!" style="display:inline-block;background:#FFF;color:#0D0D0D;border:2px solid #0D0D0D;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:600;font-size:13px;margin-left:8px;">Share with friend</a>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;margin-top:24px;">
            <div style="font-size:12px;color:#909090;">
                Detty Flight Deals<br>
                <a href="mailto:dettyflightdeals@gmail.com?subject=Unsubscribe" style="color:#909090;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>'''


def send_to_gsheet_subscribers(subject: str, html_body: str, plain_body: str) -> int:
    """Send to all Google Sheet subscribers. Returns count of successful sends."""
    if not HAS_GSHEET_SUPPORT:
        print("⚠️ Google Sheets support not available")
        return 0

    # Check if we're in email test mode (only send to NOTIFY_EMAIL)
    if TEST_EMAIL_ONLY_UNTIL:
        today = datetime.now().strftime("%Y-%m-%d")
        if today <= TEST_EMAIL_ONLY_UNTIL:
            print(f"🧪 TEST MODE: Only sending to {NOTIFY_EMAIL} (until {TEST_EMAIL_ONLY_UNTIL})")
            if send_to_subscriber(NOTIFY_EMAIL, subject, html_body, plain_body):
                print(f"  ✓ {NOTIFY_EMAIL}")
                return 1
            else:
                print(f"  ✗ {NOTIFY_EMAIL}")
                return 0

    subscribers = get_subscribers()
    if not subscribers:
        print("⚠️ No Google Sheet subscribers found")
        return 0

    print(f"📧 Sending to {len(subscribers)} Google Sheet subscribers...")
    success_count = 0

    for i, email in enumerate(subscribers):
        if send_to_subscriber(email, subject, html_body, plain_body):
            success_count += 1
        # Rate limit: 1 email per second
        if i < len(subscribers) - 1:
            time.sleep(1)

    print(f"✓ Sent to {success_count}/{len(subscribers)} subscribers")
    return success_count


def send_alert(deals: list):
    """Send email alert for deals to all channels."""
    if not deals:
        return

    # Sort by tier priority
    tier_priority = {"mistake": 0, "wow": 1, "great": 2, "good": 3}
    sorted_deals = sorted(deals, key=lambda d: (tier_priority.get(d.get("tier", "good"), 3), d["price"]))
    best_deal = sorted_deals[0]
    best_tier = best_deal.get("tier", "good")

    # Build subject line based on best deal
    dest = best_deal['destination'].title()
    price = best_deal['price']

    if best_tier == "mistake":
        subject = f"🚨 OMO! {dest} from ${price} — MISTAKE FARE"
    elif best_tier == "wow":
        subject = f"🚨 WOW: {dest} from ${price}!"
    elif best_tier == "great":
        subject = f"🔥 Great deal: {dest} from ${price}!"
    else:
        subject = f"✈️ Deal found: {dest} from ${price}"

    # Plain text version
    plain_body = "DETTY FLIGHT DEALS\n\n"

    for deal in sorted_deals:
        label = deal.get("label", "Deal")
        action = deal.get("action", "Book soon.")
        normal = deal.get("normal_price", "?")
        plain_body += f"{label}. {action}\n"
        plain_body += f"✈️ {deal['destination'].upper()}: ${deal['price']} (usually ${normal})\n"
        plain_body += f"   {deal['title']}\n"
        plain_body += f"   Source: {deal['source']}\n"
        plain_body += f"   Link: {deal['url']}\n\n"

    plain_body += "\n—\nDetty Flight Deals"

    # HTML version
    html_body = build_deals_html(deals)

    sent = False

    # 1. Send via Buttondown (all subscribers)
    if BUTTONDOWN_API_KEY:
        if send_via_buttondown(subject, html_body):
            sent = True

    # 2. Send via Google Sheets subscribers
    if HAS_GSHEET_SUPPORT:
        gsheet_count = send_to_gsheet_subscribers(subject, html_body, plain_body)
        if gsheet_count > 0:
            sent = True

    # 3. Fallback to single SMTP recipient
    if not sent and SMTP_EMAIL and SMTP_PASSWORD:
        if send_via_smtp(subject, plain_body):
            sent = True

    # No email configured - print to console
    if not sent:
        print("\n🚨 MISTAKE FARES FOUND (email not configured):")
        for deal in deals:
            print(f"  💰 {deal['destination']}: ${deal['price']}")
            print(f"     {deal['title']}")
            print(f"     {deal['url']}")


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"{'='*60}")
    print(f"Deal Monitor - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Checking {len(RSS_FEEDS)} RSS feeds...")
    print(f"Origins: US + EU | Destinations: {len(DESTINATIONS)} cities")
    print(f"Looking for deals below 'Good' thresholds\n")

    # Load persistent state
    seen_deals = load_seen_deals()
    initial_count = len(seen_deals)

    deals = check_rss_feeds(seen_deals)

    # Save updated state
    save_seen_deals(seen_deals)
    print(f"State: {initial_count} -> {len(seen_deals)} tracked deals")

    # Count by tier
    wow_deals = [d for d in deals if d.get("tier") == "wow"]
    great_deals = [d for d in deals if d.get("tier") == "great"]
    good_deals = [d for d in deals if d.get("tier") == "good"]

    print(f"\nFound {len(deals)} deals ({len(wow_deals)} rare, {len(great_deals)} great, {len(good_deals)} good)")

    if deals:
        for deal in deals:
            tier = deal.get("tier", "good")
            emoji = {"wow": "🚨", "great": "🔥", "good": "✈️"}.get(tier, "✈️")
            label = deal.get("label", "Deal")
            print(f"  {emoji} [{label}] {deal['destination']} ${deal['price']} from {deal.get('origin', 'unknown')} ({deal['source']})")
        send_alert(deals)
    else:
        print("No deals found this scan. Will check again next run.")


if __name__ == "__main__":
    main()
