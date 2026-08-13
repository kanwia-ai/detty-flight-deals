"""
Detty Flight Deals - Mistake Fare Monitor
Monitors deal sites (RSS + secretflying scrape) for Africa mistake fares:
explicitly-labeled error fares, or unlabeled fares ≤45% of normal.
Runs hourly - lightweight feed checking.
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
from html import unescape
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

# Persistent state for deduplication
SEEN_DEALS_FILE = Path(__file__).parent / "seen_mistake_fares.json"
DEAL_EXPIRY_HOURS = 72  # 3 days - mistake fares are time-sensitive

# Email test mode: only send to NOTIFY_EMAIL until this date
# Set to None to send to all subscribers
# 2026-07 revival warm-up: full list opens after this date.
TEST_EMAIL_ONLY_UNTIL = "2026-07-08"

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

# RSS feeds with source names.
# 2026-08-13 audit: secretflying killed RSS (every /feed/ URL serves the site
# HTML — scraped directly instead, see scrape_secretflying()); the
# thepointsguy deals subdomain no longer resolves. Both had been silently
# contributing nothing.
RSS_FEEDS = [
    ("https://www.theflightdeal.com/feed/", "theflightdeal"),
    ("https://www.fly4free.com/feed/", "fly4free"),
    # Dedicated error-fare category — empty most days, high-signal when live
    ("https://www.fly4free.com/flights/error-fares/feed/", "fly4free-error"),
    ("https://www.travelpirates.com/feed", "travelpirates"),
    # Wide nets for sources with no usable RSS of their own. Both verified
    # live 2026-08-13; reddit may throttle cloud IPs — the per-feed
    # try/except treats that as a skipped source, not a failure.
    ("https://news.google.com/rss/search?q=%22error+fare%22+OR+%22mistake+fare%22",
     "googlenews"),
    ("https://www.reddit.com/r/flightdeals/new/.rss", "reddit-flightdeals"),
]

SECRETFLYING_ERROR_PAGE = "https://www.secretflying.com/errorfares/"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DettyFlightDeals/1.0)"}

# Africa matching. The old flat keyword list was substring-matched, which
# meant "Standard Economy" hit "dar" and "additional" hit "add" — every
# theflightdeal US-domestic post passed the Africa filter and then died
# downstream. Names match word-bounded case-insensitive; IATA codes match
# word-bounded CASE-SENSITIVE ("ADD" the airport, not "add a bag";
# "LOS" the airport, not "Los Angeles").
AFRICA_NAMES = [
    # Our tracked cities (accented + plain)
    *[info[0].lower() for info in DESTINATIONS.values()],
    *[info[0].lower().replace("é", "e") for info in DESTINATIONS.values()],

    # West Africa
    "nigeria", "port harcourt", "ghana", "senegal", "sierra leone",
    "ivory coast", "cote d'ivoire", "togo", "benin", "cameroon",
    "gambia", "banjul", "guinea", "conakry", "liberia", "monrovia",
    "mali", "bamako", "mauritania", "niger", "niamey",
    "burkina faso", "ouagadougou",

    # Central Africa
    "congo", "brazzaville", "drc", "gabon", "libreville",
    "equatorial guinea", "chad", "central african republic", "sao tome",

    # East Africa
    "kenya", "nairobi", "tanzania", "dar es salaam", "zanzibar",
    "uganda", "kampala", "entebbe", "rwanda", "kigali",
    "ethiopia", "addis ababa", "djibouti", "somalia", "mogadishu",
    "eritrea", "asmara",

    # Southern Africa
    "south africa", "johannesburg", "joburg", "cape town", "durban",
    "zimbabwe", "harare", "zambia", "lusaka", "botswana", "gaborone",
    "namibia", "windhoek", "mozambique", "maputo", "malawi", "lilongwe",
    "mauritius", "seychelles", "madagascar", "antananarivo",

    # North Africa
    "morocco", "casablanca", "marrakech", "egypt", "cairo",
    "tunisia", "tunis", "algeria", "algiers",

    # General
    "africa", "sub-saharan",
]

AFRICA_CODES = [
    *DESTINATIONS.keys(),
    "NBO", "EBB", "KGL", "ADD", "JNB", "CPT", "DBN", "HRE", "CMN", "RAK",
    "CAI", "DKR", "ZNZ", "DAR", "MRU", "SEZ", "TNR", "LUN", "GBE", "WDH",
]


def _word_re(words, flags=0):
    """Word-bounded alternation, longest-first so 'dar es salaam' wins
    over any shorter overlapping token."""
    longest_first = sorted(words, key=len, reverse=True)
    return re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in longest_first) + r")\b", flags)


AFRICA_NAME_RE = _word_re(AFRICA_NAMES, re.IGNORECASE)
AFRICA_CODE_RE = _word_re(AFRICA_CODES)


def mentions_africa(text: str) -> bool:
    return bool(AFRICA_NAME_RE.search(text) or AFRICA_CODE_RE.search(text))


# Origins: same split — city names case-insensitive, codes case-sensitive
# (the old substring check made "afford" match ORD).
US_ORIGIN_CODES = [
    "JFK", "EWR", "LGA", "IAD", "DCA", "BWI", "ATL", "DFW", "IAH",
    "ORD", "MDW", "LAX", "SFO", "OAK", "SJC", "BOS", "MIA", "FLL",
    "DEN", "SEA", "PHL", "PHX", "MSP", "DTW", "CLT", "LAS",
]
US_ORIGIN_NAMES = [
    "new york", "newark", "washington", "atlanta", "dallas", "houston",
    "chicago", "los angeles", "san francisco", "boston", "miami",
    "denver", "seattle", "philadelphia", "phoenix", "minneapolis",
    "detroit", "charlotte", "las vegas",
    # "US nationwide" phrasings — secretflying/fly4free use these constantly
    "nationwide", "the us", "u.s.", "usa", "united states", "us cities",
]
EU_ORIGIN_CODES = [
    "LHR", "LGW", "STN", "CDG", "ORY", "FRA", "AMS", "MAD", "BCN",
    "FCO", "MXP", "DUB", "LIS", "BRU", "VIE", "ZRH", "MUC", "CPH",
    "OSL", "ARN", "HEL",
]
EU_ORIGIN_NAMES = [
    "london", "paris", "frankfurt", "amsterdam", "madrid", "barcelona",
    "rome", "milan", "dublin", "lisbon", "brussels", "vienna", "zurich",
    "munich", "copenhagen", "oslo", "stockholm", "helsinki",
    "european cities", "europe to",
]

ORIGIN_NAME_RE = _word_re(US_ORIGIN_NAMES + EU_ORIGIN_NAMES, re.IGNORECASE)
ORIGIN_CODE_RE = _word_re(US_ORIGIN_CODES + EU_ORIGIN_CODES)


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
    """Extract origin city/airport from deal text (word-bounded; codes
    must be uppercase in the source text)."""
    match = ORIGIN_NAME_RE.search(text)
    if match:
        return match.group(0)
    match = ORIGIN_CODE_RE.search(text)
    if match:
        return match.group(0)
    return None


def is_valid_origin(text: str) -> bool:
    """Check if deal originates from US or EU."""
    return extract_origin(text) is not None


# ============================================================
# PARSING
# ============================================================

# Approximate, hardcoded — mistake-fare triage doesn't need live FX
EUR_TO_USD = 1.1
GBP_TO_USD = 1.3


def extract_price(text: str) -> int | None:
    """Extract the lowest price in the text, converted to ~USD.

    Handles $520, $1,234, USD 499, 499 USD, €380, 1720€, £790. The old
    regexes required either 4 digits or a trailing "USD", so a "$520
    roundtrip" Lagos error fare — the typical mistake-fare price shape —
    parsed as NO price and the deal was silently dropped."""
    amount = r"(\d{1,4}(?:,\d{3})?)"
    patterns = [
        (rf"[$]\s?{amount}", 1.0),
        (rf"{amount}\s?[$]", 1.0),
        (rf"\bUSD\s?{amount}", 1.0),
        (rf"{amount}\s?USD\b", 1.0),
        (rf"€\s?{amount}", EUR_TO_USD),
        (rf"{amount}\s?€", EUR_TO_USD),
        (rf"\bEUR\s?{amount}", EUR_TO_USD),
        (rf"{amount}\s?EUR\b", EUR_TO_USD),
        (rf"£\s?{amount}", GBP_TO_USD),
        (rf"{amount}\s?£", GBP_TO_USD),
        (rf"\bGBP\s?{amount}", GBP_TO_USD),
        (rf"{amount}\s?GBP\b", GBP_TO_USD),
    ]

    prices = []
    for pattern, rate in patterns:
        for match in re.findall(pattern, text, re.IGNORECASE):
            usd = round(int(match.replace(",", "")) * rate)
            if 100 <= usd <= 5000:  # Realistic flight price range
                prices.append(usd)

    return min(prices) if prices else None


def extract_destination(text: str) -> str | None:
    """First Africa mention in the text — ANY of the continent keywords.
    The old version only recognized the 11 tracked West/Central cities, so
    a Johannesburg or Nairobi mistake fare — exactly what this monitor
    exists to catch — extracted no destination and was dropped."""
    match = AFRICA_NAME_RE.search(text)
    if match:
        return match.group(0).replace("é", "e").title()
    match = AFRICA_CODE_RE.search(text)
    if match:
        return match.group(0)
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


# An unlabeled fare this far below normal is mistake-fare-grade — nobody
# prices 55%+ off on purpose. Labeled error fares pass regardless of price.
MISTAKE_DISCOUNT_RATIO = 0.45


def classify_deal(price: int, destination: str, text: str) -> dict | None:
    """
    Classify a deal — mistake fares only; deal_finder.py owns routine deals.
    Two ways in: the source explicitly calls it a mistake/error fare, or the
    price is ≤45% of the destination's normal (deep enough that "the source
    didn't say error fare" doesn't matter — TheFlightDeal, reddit and the
    aggregators rarely label them).

    Mistake fares can be to ANY African destination, not just tracked cities.
    """
    text_lower = text.lower()
    is_explicit_mistake = any(term in text_lower for term in [
        "mistake fare", "error fare", "pricing error", "glitch fare",
        "mistake-fare", "error-fare"
    ])

    # Get normal price if we have it, otherwise use default
    thresholds = get_thresholds_for_dest(destination)
    normal_price = thresholds["normal"] if thresholds else 1200  # Default for unknown African destinations

    if not is_explicit_mistake and price > round(normal_price * MISTAKE_DISCOUNT_RATIO):
        return None  # Skip - let deal_finder.py handle regular deals

    return {
        "tier": "mistake",
        "label": "OMO!",
        "action": "Drop everything. Book NOW.",
        "urgency": "critical",
        "normal_price": normal_price,
    }


# ============================================================
# RSS MONITORING
# ============================================================

def consider_entry(title: str, summary: str, link: str, source_name: str,
                   seen_deals: dict, deals: list):
    """Run one entry (from RSS or a scrape) through the alert funnel."""
    full_text = f"{title} {summary}"

    # Skip if already seen
    if is_deal_seen(link, seen_deals):
        return

    # Check if it's an Africa deal
    if not mentions_africa(full_text):
        return

    # Check if origin is US or EU
    if not is_valid_origin(full_text):
        return

    # Extract price and destination
    price = extract_price(full_text)
    destination = extract_destination(full_text)

    if not price or not destination:
        return

    # Classify the deal
    classification = classify_deal(price, destination, full_text)
    if classification:
        deals.append({
            "destination": destination,
            "price": price,
            "title": title,
            "url": link,
            "source": source_name,
            "origin": extract_origin(full_text),
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


def scrape_secretflying() -> list:
    """secretflying disabled RSS sometime before Aug 2026 (every /feed/ URL
    now serves the site's HTML), but it's still the single best error-fare
    source and its pages are server-rendered — scrape post links + titles
    off the error-fares category page instead."""
    resp = requests.get(SECRETFLYING_ERROR_PAGE, timeout=20, headers=REQUEST_HEADERS)
    entries, seen_links = [], set()
    for url, title in re.findall(
            r'<a[^>]+href="(https://www\.secretflying\.com/posts/[^"]+)"[^>]*>'
            r'([^<]{10,200})</a>', resp.text):
        if url not in seen_links:
            seen_links.add(url)
            entries.append({"title": unescape(title.strip()), "link": url})
    return entries


def check_rss_feeds(seen_deals: dict) -> list:
    """Check RSS feeds + the secretflying scrape for Africa deals from US/EU."""
    deals = []

    for feed_url, source_name in RSS_FEEDS:
        try:
            # Fetch ourselves with a hard timeout — feedparser's own fetching
            # has no socket timeout, and one stalled feed hung a run for over
            # an hour on Aug 6, clogging the workflow queue behind it.
            resp = requests.get(feed_url, timeout=20, headers=REQUEST_HEADERS)
            feed = feedparser.parse(resp.content)

            for entry in feed.entries[:20]:  # Check last 20 entries
                consider_entry(entry.get('title', ''), entry.get('summary', ''),
                               entry.get('link', ''), source_name,
                               seen_deals, deals)

        except Exception as e:
            print(f"Error checking {feed_url}: {e}")

    try:
        for entry in scrape_secretflying()[:20]:
            consider_entry(entry["title"], "", entry["link"], "secretflying",
                           seen_deals, deals)
    except Exception as e:
        print(f"Error scraping secretflying: {e}")

    return deals


# ============================================================
# EMAIL
# ============================================================

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

        <!-- Fine print for mistake fares -->
        {'<div style="background:#F5F5F5;border-radius:8px;padding:12px;margin-top:8px;font-size:12px;color:#666;text-align:center;">⚠️ Mistake fares may not be honored by the airline. Book at your own risk.</div>' if best_tier == "mistake" else ''}

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

    # 1. Send via Google Sheets subscribers
    if HAS_GSHEET_SUPPORT:
        gsheet_count = send_to_gsheet_subscribers(subject, html_body, plain_body)
        if gsheet_count > 0:
            sent = True

    # 2. Fallback to single SMTP recipient
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
    print(f"Checking {len(RSS_FEEDS)} RSS feeds + secretflying scrape...")
    print(f"Origins: US + EU | Destinations: anywhere in Africa")
    print(f"Looking for labeled error fares, or unlabeled fares ≤45% of normal\n")

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
