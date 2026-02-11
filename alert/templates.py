"""
Detty Flight Deals - Alert Email Templates

Email formatting helpers for the tier-escalation alert system.
Generates subject lines, escalation context, and mistake fare urgency
messaging based on deal tier and FSM state.

Tier emoji system (text-compatible indicators for email subjects):
    *  = Great deal
    ** = WOW deal
    !! = Mistake fare
"""

import json
from typing import Dict, List, Optional, Tuple


# ==========================================================
# CONSTANTS
# ==========================================================

TIER_EMOJIS = {
    "Great": "*",       # Star for great deals
    "WOW": "**",        # Double star for WOW
    "MISTAKE": "!!",    # Warning for mistake fares
}

CABIN_CLASS_DISPLAY = {
    "BUSINESS": {"label": "Business Class", "badge_bg": "#1E40AF", "badge_text": "#FFF", "emoji": "BIZ"},
    "FIRST": {"label": "First Class", "badge_bg": "#7C2D12", "badge_text": "#FFF", "emoji": "1ST"},
    "PREMIUM_ECONOMY": {"label": "Premium Economy", "badge_bg": "#065F46", "badge_text": "#FFF", "emoji": "PE"},
}

MISTAKE_FARE_URGENCY = """
!! MISTAKE FARE -- Book NOW, may disappear in hours

This price is likely an error. Airlines sometimes honor these,
sometimes cancel within 24-72 hours. If you book:
- Use a credit card with good travel protection
- Don't book non-refundable hotels until fare is confirmed
- Most mistake fares ARE honored (~70%)
""".strip()

# Mapping from anomaly detection tiers to display tiers
# Per CONTEXT.md: only 2 tiers -- Great (free) and WOW (premium)
# "good" from anomaly maps to Great (no separate Good tier)
_TIER_MAP = {
    "good": ("Great", "*"),
    "great": ("Great", "*"),
    "wow": ("WOW", "**"),
    "exceptional": ("WOW", "**"),
}


# ==========================================================
# PUBLIC FUNCTIONS
# ==========================================================

def get_tier_label(tier: str, is_mistake_fare: bool = False) -> Tuple[str, str]:
    """
    Get the display label and emoji for a deal tier.

    Maps anomaly detection tiers to the two-tier display system.
    Mistake fare flag overrides any tier to MISTAKE.

    Args:
        tier: Tier from anomaly detection ("good", "great", "wow", "exceptional")
              or display tier ("Great", "WOW", "MISTAKE")
        is_mistake_fare: If True, always returns MISTAKE tier

    Returns:
        Tuple of (label, emoji) e.g. ("Great", "*") or ("MISTAKE", "!!")
    """
    if is_mistake_fare:
        return ("MISTAKE", "!!")

    tier_lower = tier.lower() if tier else "great"

    # Check direct display tier names first
    if tier_lower == "mistake":
        return ("MISTAKE", "!!")

    # Map anomaly tiers to display tiers
    if tier_lower in _TIER_MAP:
        return _TIER_MAP[tier_lower]

    # Default to Great for unknown tiers
    return ("Great", "*")


def format_alert_subject(
    route: str,
    dest_name: str,
    price_cents: int,
    tier: str,
    tier_emoji: str,
    is_escalation: bool,
    last_price_cents: Optional[int] = None,
) -> str:
    """
    Format an email subject line with tier emoji and pricing context.

    Subject formats:
        Normal:     "[* Great] Lagos from $650"
        Escalation: "[** WOW] Price DROP: Lagos now $580 (was $720)"
        Mistake:    "[!! MISTAKE FARE] Book NOW: Lagos $400"

    Args:
        route: Route string e.g. "JFK-LOS" (used for context)
        dest_name: Destination city name e.g. "Lagos"
        price_cents: Current price in cents
        tier: Display tier ("Great", "WOW", "MISTAKE")
        tier_emoji: Tier emoji string ("*", "**", "!!")
        is_escalation: Whether this is a tier escalation (price dropped further)
        last_price_cents: Previous alert price in cents (for escalation context)

    Returns:
        Formatted subject line string
    """
    price = price_cents // 100

    # Mistake fare: urgency-first subject
    if tier == "MISTAKE" or tier_emoji == "!!":
        return f"[!! MISTAKE FARE] Book NOW: {dest_name} ${price}"

    # Escalation: show price drop
    if is_escalation and last_price_cents is not None:
        last_price = last_price_cents // 100
        return f"[{tier_emoji} {tier}] Price DROP: {dest_name} now ${price} (was ${last_price})"

    # Normal: destination and price
    return f"[{tier_emoji} {tier}] {dest_name} from ${price}"


def format_escalation_body(
    current_price_cents: int,
    last_alert_price_cents: int,
    normal_price_cents: int,
) -> str:
    """
    Format escalation context showing both drop from last alert AND savings vs normal.

    Per CONTEXT.md: show BOTH contexts for escalation emails.
    Example: "$580 (down $140 since our last alert, saves $340 vs normal $920)"

    Args:
        current_price_cents: Current deal price in cents
        last_alert_price_cents: Price when we last alerted in cents
        normal_price_cents: Baseline normal price for this route in cents

    Returns:
        Formatted price context string
    """
    current = current_price_cents // 100
    last = last_alert_price_cents // 100
    normal = normal_price_cents // 100

    drop_from_last = last - current
    savings_vs_normal = normal - current

    return (
        f"${current} (down ${drop_from_last} since our last alert, "
        f"saves ${savings_vs_normal} vs normal ${normal})"
    )


def format_mistake_fare_alert(
    dest_name: str,
    price_cents: int,
    normal_price_cents: int,
    booking_url: str,
) -> Dict[str, str]:
    """
    Format a complete mistake fare alert with urgency messaging.

    Returns a dict with all components needed for the email template.
    Subject includes savings percentage to convey urgency.

    Args:
        dest_name: Destination city name e.g. "Lagos"
        price_cents: Current mistake fare price in cents
        normal_price_cents: Baseline normal price in cents
        booking_url: URL to book the flight

    Returns:
        Dict with keys: subject, urgency_banner, price_line, cta
    """
    price = price_cents // 100
    normal = normal_price_cents // 100

    # Calculate savings percentage
    if normal > 0:
        savings_pct = round((normal - price) / normal * 100)
    else:
        savings_pct = 0

    savings_amount = normal - price

    subject = f"[!! MISTAKE FARE] Book NOW: {dest_name} ${price} ({savings_pct}% off)"

    urgency_banner = MISTAKE_FARE_URGENCY

    price_line = (
        f"${price} (saves ${savings_amount} vs normal ${normal} -- "
        f"{savings_pct}% off)"
    )

    cta = f"Book NOW before it disappears: {booking_url}"

    return {
        "subject": subject,
        "urgency_banner": urgency_banner,
        "price_line": price_line,
        "cta": cta,
    }


# ==========================================================
# WEEKLY DIGEST TEMPLATES (Phase 5: Freemium Infrastructure)
# ==========================================================

MAX_DIGEST_DEALS = 15  # Cap per subscriber email to prevent unbounded growth


def format_historical_context(
    z_score: float,
    observation_count: int,
    drop_pct: float = None,
) -> str:
    """
    Format historical price context for premium subscribers (SUBS-04).

    Returns a human-readable string describing how this fare compares
    to historical pricing data.

    Args:
        z_score: Z-score from anomaly detection (negative = below average).
        observation_count: Number of price observations in the window.
        drop_pct: Percentage drop below normal pricing.

    Returns:
        Context string, or "" if no context available.
    """
    if z_score is not None and observation_count > 0:
        return (
            f"This fare is {abs(z_score):.1f} standard deviations below "
            f"the 90-day average ({observation_count} price checks)"
        )
    if drop_pct is not None:
        return f"This fare is {abs(drop_pct):.0f}% below normal pricing"
    return ""


def build_fomo_teaser_html(
    teaser_deals: List[dict],
    max_teasers: int = 3,
) -> str:
    """
    Build FOMO teaser section for weekly digest (FRML-01).

    Shows 2-3 WOW/mistake fares that free users missed.
    Tone: urgency-driven per CONTEXT.md.

    Args:
        teaser_deals: List of deal dicts from digest_queue.
        max_teasers: Max number of teasers to show (default 3).

    Returns:
        HTML string for the teaser section, or "" if no teasers.
    """
    if not teaser_deals:
        return ""

    selected = teaser_deals[:max_teasers]

    teaser_cards = ""
    for deal in selected:
        # Parse deal data
        deal_data = deal.get("deal_data_json", "{}")
        if isinstance(deal_data, str):
            try:
                deal_data = json.loads(deal_data)
            except (json.JSONDecodeError, TypeError):
                deal_data = {}

        # Get price -- prefer price_cents field, fall back to parsed data
        price_cents = deal.get("price_cents", 0)
        if price_cents:
            price = price_cents // 100
        else:
            price = deal_data.get("price", 0)

        dest_name = deal.get("dest_name") or deal_data.get("dest_name", "Unknown")
        origin = deal.get("origin") or deal_data.get("origin", "")
        tier = (deal.get("tier") or deal_data.get("tier", "wow")).lower()

        # Tier-specific urgency messaging
        if tier == "mistake":
            subtext = (
                "MISTAKE FARE -- gone in hours. "
                "Premium members were alerted by SMS."
            )
            border_color = "#DC2626"
            bg_color = "#FEF2F2"
        else:
            subtext = (
                "This WOW deal came and went this week. "
                "Premium members got it instantly."
            )
            border_color = "#EA580C"
            bg_color = "#FFF7ED"

        teaser_cards += f'''
        <div style="background:{bg_color};border-left:4px solid {border_color};border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="font-size:16px;font-weight:700;color:{border_color};margin-bottom:4px;">
                You MISSED ${price} {dest_name} from {origin}
            </div>
            <div style="font-size:13px;color:#525252;">
                {subtext}
            </div>
        </div>'''

    return f'''
    <div style="margin-top:32px;margin-bottom:24px;">
        <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:16px;">
            What Premium Members Got This Week
        </div>
        {teaser_cards}
        <div style="text-align:center;margin-top:20px;">
            <a href="#premium" style="display:inline-block;background:#E31C25;color:#FFF;padding:14px 28px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">
                Upgrade to Premium -- never miss a deal
            </a>
        </div>
    </div>'''


def _build_digest_deal_card(deal: dict) -> str:
    """
    Build a single deal card for the weekly digest email.

    Follows the existing Detty email design system: Pan-African colors,
    rounded cards, booking link button.

    Args:
        deal: Deal dict from digest_queue with deal_data_json.

    Returns:
        HTML string for one deal card.
    """
    deal_data = deal.get("deal_data_json", "{}")
    if isinstance(deal_data, str):
        try:
            deal_data = json.loads(deal_data)
        except (json.JSONDecodeError, TypeError):
            deal_data = {}

    # Extract fields
    price_cents = deal.get("price_cents", 0)
    price = price_cents // 100 if price_cents else deal_data.get("price", 0)

    dest_name = deal.get("dest_name") or deal_data.get("dest_name", "Unknown")
    origin = deal.get("origin") or deal_data.get("origin", "")
    dest = deal.get("dest") or deal_data.get("dest", "")
    tier = (deal.get("tier") or deal_data.get("tier", "great")).lower()

    normal_price = deal_data.get("normal_price", 0)
    departure = deal_data.get("departure", "")
    booking_url = deal_data.get(
        "url",
        f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}",
    )

    # Tier-specific styling (Great = green, Good = green)
    bg_color = "#DCFCE7"
    border_color = "#009639"
    badge_style = "background:#009639;color:#FFF;"
    tier_label = "GREAT DEAL" if tier == "great" else "GOOD DEAL"

    # Normal price strikethrough
    normal_html = ""
    if normal_price and normal_price > price:
        normal_html = (
            f'<span style="font-size:14px;font-weight:400;color:#909090;'
            f'text-decoration:line-through;margin-left:8px;">'
            f"${normal_price}</span>"
        )

    # Departure date line
    date_html = ""
    if departure:
        return_date = deal_data.get("return", "")
        if return_date:
            date_html = f'<div style="font-size:14px;color:#525252;margin-bottom:12px;">Departs {departure} - Returns {return_date}</div>'
        else:
            date_html = f'<div style="font-size:14px;color:#525252;margin-bottom:12px;">Departs {departure}</div>'

    return f'''
    <div style="background:{bg_color};border:2px solid {border_color};border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="margin-bottom:12px;">
            <span style="{badge_style}padding:4px 12px;border-radius:50px;font-size:12px;font-weight:700;">{tier_label}</span>
        </div>
        <div style="font-size:24px;font-weight:800;color:#009639;margin-bottom:4px;">
            ${price} {normal_html}
            <span style="font-size:14px;font-weight:400;color:#525252;"> round-trip</span>
        </div>
        <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
            {origin} &rarr; {dest_name}
        </div>
        {date_html}
        <a href="{booking_url}" style="display:inline-block;background:#E31C25;color:#FFF;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">Book Now &rarr;</a>
    </div>'''


def build_weekly_digest_html(
    subscriber_name: str,
    great_deals: List[dict],
    fomo_teasers: List[dict],
    metro_name: str,
) -> str:
    """
    Build complete weekly digest email HTML for a free subscriber.

    Follows the existing Detty email design system:
    - Same header (gradient Detty Flight Deals branding)
    - Same color scheme (green/yellow/red Pan-African)
    - Same card layout for deals
    - Added FOMO teaser section
    - Added footer with upgrade CTA

    Args:
        subscriber_name: Subscriber display name (or "").
        great_deals: List of Great/Good tier deal dicts from digest_queue.
        fomo_teasers: List of WOW/mistake tier deal dicts for FOMO section.
        metro_name: Metro group name (e.g. "NYC") for personalization.

    Returns:
        Complete HTML document string.
    """
    greeting = f"Hey {subscriber_name}!" if subscriber_name else "Hey there!"

    # Summary line
    if great_deals:
        summary = f"Here are this week's Great flight deals from {metro_name}."
    elif fomo_teasers:
        summary = (
            f"No Great deals matched {metro_name} this week, "
            "but here's what Premium members got."
        )
    else:
        summary = "No deals matched your metro this week. We're watching!"

    # Build deal cards (capped at MAX_DIGEST_DEALS)
    deals_html = ""
    capped_deals = great_deals[:MAX_DIGEST_DEALS]
    for deal in capped_deals:
        deals_html += _build_digest_deal_card(deal)

    # Deal count badge
    deal_count_text = ""
    if capped_deals:
        deal_count_text = f"Found {len(capped_deals)} deal(s) this week"

    # FOMO teaser section
    fomo_html = build_fomo_teaser_html(fomo_teasers)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">

        <!-- Header -->
        <div style="text-align:center;padding:24px 0;margin-bottom:24px;">
            <div style="font-size:28px;font-weight:800;margin-bottom:8px;">
                <span style="background:linear-gradient(90deg,#009639,#FCD116,#E31C25);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Detty</span> <span style="color:#262626;">Flight Deals</span>
            </div>
            <div style="font-size:16px;font-weight:600;color:#525252;">
                Weekly Digest
            </div>
            <div style="font-size:14px;color:#909090;">
                {deal_count_text}
            </div>
        </div>

        <!-- Greeting -->
        <div style="background:#FFFFFF;border-radius:12px;padding:24px;margin-bottom:24px;">
            <div style="font-size:20px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
                {greeting}
            </div>
            <div style="font-size:15px;color:#525252;line-height:1.5;">
                {summary}
            </div>
        </div>

        <!-- Deal Cards -->
        {deals_html}

        <!-- FOMO Teasers -->
        {fomo_html}

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;margin-top:24px;">
            <div style="font-size:12px;color:#525252;margin-bottom:8px;">
                You're on the <strong>Free</strong> plan. Upgrade to Premium for instant alerts + SMS notifications.
            </div>
            <div style="font-size:12px;color:#909090;">
                You signed up for Detty Flight Deals.
            </div>
            <div style="font-size:12px;color:#909090;margin-top:8px;">
                <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe%20from%20Detty%20Flight%20Deals&body=Please%20unsubscribe%20me%20from%20Detty%20Flight%20Deals." style="color:#909090;text-decoration:underline;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>'''


def build_weekly_digest_plain(
    subscriber_name: str,
    great_deals: List[dict],
    fomo_teasers: List[dict],
    metro_name: str,
) -> str:
    """
    Build plain text version of weekly digest.

    Args:
        subscriber_name: Subscriber display name (or "").
        great_deals: List of Great/Good tier deal dicts.
        fomo_teasers: List of WOW/mistake tier deal dicts for FOMO section.
        metro_name: Metro group name for personalization.

    Returns:
        Plain text email body string.
    """
    greeting = f"Hey {subscriber_name}!" if subscriber_name else "Hey there!"

    lines = [
        "DETTY FLIGHT DEALS - WEEKLY DIGEST",
        "=" * 40,
        "",
        greeting,
        "",
    ]

    # Summary
    if great_deals:
        lines.append(f"Here are this week's Great flight deals from {metro_name}.")
    elif fomo_teasers:
        lines.append(f"No Great deals matched {metro_name} this week.")
    else:
        lines.append("No deals matched your metro this week. We're watching!")
    lines.append("")

    # Deals
    capped = great_deals[:MAX_DIGEST_DEALS]
    for deal in capped:
        deal_data = deal.get("deal_data_json", "{}")
        if isinstance(deal_data, str):
            try:
                deal_data = json.loads(deal_data)
            except (json.JSONDecodeError, TypeError):
                deal_data = {}

        price_cents = deal.get("price_cents", 0)
        price = price_cents // 100 if price_cents else deal_data.get("price", 0)
        dest_name = deal.get("dest_name") or deal_data.get("dest_name", "Unknown")
        origin = deal.get("origin") or deal_data.get("origin", "")
        dest = deal.get("dest") or deal_data.get("dest", "")
        departure = deal_data.get("departure", "")
        booking_url = deal_data.get(
            "url",
            f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}",
        )

        lines.append(f"GREAT DEAL: {origin} -> {dest_name}")
        lines.append(f"  ${price} round-trip")
        if departure:
            lines.append(f"  Departs: {departure}")
        lines.append(f"  Book: {booking_url}")
        lines.append("-" * 40)
        lines.append("")

    # FOMO teasers
    if fomo_teasers:
        lines.append("")
        lines.append("WHAT PREMIUM MEMBERS GOT THIS WEEK")
        lines.append("-" * 40)
        for deal in fomo_teasers[:3]:
            deal_data = deal.get("deal_data_json", "{}")
            if isinstance(deal_data, str):
                try:
                    deal_data = json.loads(deal_data)
                except (json.JSONDecodeError, TypeError):
                    deal_data = {}

            price_cents = deal.get("price_cents", 0)
            price = price_cents // 100 if price_cents else deal_data.get("price", 0)
            dest_name = deal.get("dest_name") or deal_data.get("dest_name", "Unknown")
            origin = deal.get("origin") or deal_data.get("origin", "")
            tier = (deal.get("tier") or "wow").lower()

            lines.append(f"  You MISSED ${price} {dest_name} from {origin}")
            if tier == "mistake":
                lines.append(
                    "    MISTAKE FARE -- gone in hours. Premium members were alerted by SMS."
                )
            else:
                lines.append(
                    "    This WOW deal came and went. Premium members got it instantly."
                )
            lines.append("")

        lines.append("Upgrade to Premium -- never miss a deal: #premium")
        lines.append("")

    # Footer
    lines.extend([
        "",
        "---",
        "You're on the Free plan. Upgrade to Premium for instant alerts + SMS.",
        "You signed up for Detty Flight Deals.",
        "To unsubscribe, reply with 'Unsubscribe'.",
    ])

    return "\n".join(lines)


def build_weekly_digest_subject(
    deal_count: int,
    best_dest: str = None,
    best_price: int = None,
) -> str:
    """
    Build weekly digest email subject line.

    Args:
        deal_count: Number of deals included in the digest.
        best_dest: Name of the best destination (lowest price).
        best_price: Price in dollars of the best deal.

    Returns:
        Subject line string.
    """
    if deal_count > 1 and best_dest and best_price:
        return (
            f"This week's deals: {best_dest} from ${best_price} "
            f"+ {deal_count - 1} more"
        )
    if deal_count == 1 and best_dest and best_price:
        return f"This week's deal: {best_dest} from ${best_price}"
    return "Your Weekly Africa Flight Deals Roundup"


# ==========================================================
# PREMIUM CABIN ALERT TEMPLATES (Phase 6: Business/First Class)
# ==========================================================


def format_premium_cabin_subject(
    dest_name: str,
    price_cents: int,
    cabin_class: str,
    normal_price_cents: Optional[int] = None,
) -> str:
    """
    Format an email subject line for a premium cabin deal.

    Subject formats:
        Normal:       "[BIZ] Business Class Deal: Lagos from $2,400"
        With savings: "[BIZ] Business Class Deal: Lagos $2,400 (40% off)"
        First class:  "[1ST] First Class Deal: Lagos from $4,000"
        Premium econ: "[PE] Premium Economy Deal: Accra from $960"

    Args:
        dest_name: Destination city name e.g. "Lagos"
        price_cents: Current price in cents
        cabin_class: Cabin class key ("BUSINESS", "FIRST", "PREMIUM_ECONOMY")
        normal_price_cents: Baseline normal price in cents for savings calculation

    Returns:
        Formatted subject line string
    """
    price = price_cents // 100
    display = CABIN_CLASS_DISPLAY.get(
        cabin_class.upper(), CABIN_CLASS_DISPLAY["BUSINESS"]
    )
    emoji = display["emoji"]
    label = display["label"]

    # Calculate savings percentage if normal price is provided
    if normal_price_cents and normal_price_cents > 0 and normal_price_cents > price_cents:
        savings_pct = round((normal_price_cents - price_cents) / normal_price_cents * 100)
        return f"[{emoji}] {label} Deal: {dest_name} ${price:,} ({savings_pct}% off)"

    return f"[{emoji}] {label} Deal: {dest_name} from ${price:,}"


def format_premium_cabin_card_html(deal: dict) -> str:
    """
    Build an HTML deal card for a premium cabin alert.

    Follows the existing Detty email design system (same border-radius,
    padding, font-family as _build_digest_deal_card) but with:
    - Cabin class badge at top (colored pill)
    - Price prominently displayed with normal price strikethrough
    - Savings percentage
    - Route (origin -> dest_name)
    - Departure date
    - Book Now button (red CTA, same as existing)
    - Urgency messaging for premium cabin rarity

    Args:
        deal: Deal dict with origin, dest, dest_name, price, cabin_class,
              normal_price, departure_date, url.

    Returns:
        HTML string for one premium cabin deal card.
    """
    cabin_class = deal.get("cabin_class", "BUSINESS").upper()
    display = CABIN_CLASS_DISPLAY.get(cabin_class, CABIN_CLASS_DISPLAY["BUSINESS"])
    badge_bg = display["badge_bg"]
    badge_text = display["badge_text"]
    label = display["label"]

    price = deal.get("price", 0)
    if isinstance(price, float):
        price = int(price)
    normal_price = deal.get("normal_price", 0)
    if isinstance(normal_price, float):
        normal_price = int(normal_price)

    origin = deal.get("origin", "")
    dest_name = deal.get("dest_name", deal.get("dest", ""))
    departure_date = deal.get("departure_date", "")
    booking_url = deal.get("url", "")

    # Normal price strikethrough and savings
    normal_html = ""
    savings_html = ""
    if normal_price and normal_price > price:
        savings_pct = round((normal_price - price) / normal_price * 100)
        normal_html = (
            f'<span style="font-size:16px;font-weight:400;color:#909090;'
            f'text-decoration:line-through;margin-left:10px;">'
            f"${normal_price:,}</span>"
        )
        savings_html = (
            f'<div style="font-size:14px;font-weight:600;color:#059669;margin-bottom:8px;">'
            f"Save {savings_pct}% vs normal pricing</div>"
        )

    # Departure date line
    date_html = ""
    if departure_date:
        return_date = deal.get("return_date", "")
        if return_date:
            date_html = (
                f'<div style="font-size:14px;color:#525252;margin-bottom:12px;">'
                f"Departs {departure_date} - Returns {return_date}</div>"
            )
        else:
            date_html = (
                f'<div style="font-size:14px;color:#525252;margin-bottom:12px;">'
                f"Departs {departure_date}</div>"
            )

    return f'''
    <div style="background:#FAFAFA;border:2px solid {badge_bg};border-radius:12px;padding:20px;margin-bottom:16px;">
        <div style="margin-bottom:12px;">
            <span style="background:{badge_bg};color:{badge_text};padding:5px 14px;border-radius:50px;font-size:12px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;">{label}</span>
        </div>
        <div style="font-size:28px;font-weight:800;color:{badge_bg};margin-bottom:4px;">
            ${price:,} {normal_html}
            <span style="font-size:14px;font-weight:400;color:#525252;"> round-trip</span>
        </div>
        {savings_html}
        <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
            {origin} &rarr; {dest_name}
        </div>
        {date_html}
        <div style="font-size:13px;color:#6B7280;font-style:italic;margin-bottom:14px;">
            Premium cabin deals are rare. This price may not last.
        </div>
        <a href="{booking_url}" style="display:inline-block;background:#E31C25;color:#FFF;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">Book Now &rarr;</a>
    </div>'''


def build_premium_cabin_alert_html(
    subscriber_name: str,
    deal: dict,
) -> str:
    """
    Build a complete standalone HTML email for a single premium cabin deal.

    Structure:
    - Detty header (same gradient branding as weekly digest)
    - "Premium Cabin Alert" subheader
    - Personalized greeting
    - Single deal card (from format_premium_cabin_card_html)
    - Footer with "You're a Premium member" messaging

    Args:
        subscriber_name: Subscriber display name (or "").
        deal: Deal dict with origin, dest, dest_name, price, cabin_class,
              normal_price, departure_date, url.

    Returns:
        Complete HTML document string.
    """
    greeting = f"Hey {subscriber_name}!" if subscriber_name else "Hey there!"
    cabin_class = deal.get("cabin_class", "BUSINESS").upper()
    display = CABIN_CLASS_DISPLAY.get(cabin_class, CABIN_CLASS_DISPLAY["BUSINESS"])
    label = display["label"]

    deal_card = format_premium_cabin_card_html(deal)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">

        <!-- Header -->
        <div style="text-align:center;padding:24px 0;margin-bottom:24px;">
            <div style="font-size:28px;font-weight:800;margin-bottom:8px;">
                <span style="background:linear-gradient(90deg,#009639,#FCD116,#E31C25);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Detty</span> <span style="color:#262626;">Flight Deals</span>
            </div>
            <div style="font-size:16px;font-weight:600;color:{display["badge_bg"]};">
                {label} Alert
            </div>
        </div>

        <!-- Greeting -->
        <div style="background:#FFFFFF;border-radius:12px;padding:24px;margin-bottom:24px;">
            <div style="font-size:20px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
                {greeting}
            </div>
            <div style="font-size:15px;color:#525252;line-height:1.5;">
                We found a {label.lower()} deal you need to see.
            </div>
        </div>

        <!-- Deal Card -->
        {deal_card}

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;margin-top:24px;">
            <div style="font-size:12px;color:#525252;margin-bottom:8px;">
                You're a <strong>Premium</strong> member. Premium cabin alerts are exclusive to your tier.
            </div>
            <div style="font-size:12px;color:#909090;">
                You signed up for Detty Flight Deals.
            </div>
            <div style="font-size:12px;color:#909090;margin-top:8px;">
                <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe%20from%20Detty%20Flight%20Deals&body=Please%20unsubscribe%20me%20from%20Detty%20Flight%20Deals." style="color:#909090;text-decoration:underline;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>'''


def build_premium_cabin_alert_plain(
    subscriber_name: str,
    deal: dict,
) -> str:
    """
    Build plain text version of a premium cabin deal alert email.

    Args:
        subscriber_name: Subscriber display name (or "").
        deal: Deal dict with origin, dest, dest_name, price, cabin_class,
              normal_price, departure_date, url.

    Returns:
        Plain text email body string.
    """
    greeting = f"Hey {subscriber_name}!" if subscriber_name else "Hey there!"
    cabin_class = deal.get("cabin_class", "BUSINESS").upper()
    display = CABIN_CLASS_DISPLAY.get(cabin_class, CABIN_CLASS_DISPLAY["BUSINESS"])
    label = display["label"]

    price = deal.get("price", 0)
    if isinstance(price, float):
        price = int(price)
    normal_price = deal.get("normal_price", 0)
    if isinstance(normal_price, float):
        normal_price = int(normal_price)

    origin = deal.get("origin", "")
    dest_name = deal.get("dest_name", deal.get("dest", ""))
    departure_date = deal.get("departure_date", "")
    return_date = deal.get("return_date", "")
    booking_url = deal.get("url", "")

    lines = [
        f"DETTY FLIGHT DEALS - {label.upper()} ALERT",
        "=" * 50,
        "",
        greeting,
        "",
        f"We found a {label} deal you need to see.",
        "",
        "-" * 50,
        f"{label}",
        f"  {origin} -> {dest_name}",
        f"  ${price:,} round-trip",
    ]

    if normal_price and normal_price > price:
        savings_pct = round((normal_price - price) / normal_price * 100)
        lines.append(f"  Normal price: ${normal_price:,} (Save {savings_pct}%)")

    if departure_date:
        date_line = f"  Departs: {departure_date}"
        if return_date:
            date_line += f" - Returns: {return_date}"
        lines.append(date_line)

    lines.extend([
        "",
        "Premium cabin deals are rare. This price may not last.",
        "",
        f"Book now: {booking_url}",
        "-" * 50,
        "",
        "---",
        "You're a Premium member. Premium cabin alerts are exclusive to your tier.",
        "You signed up for Detty Flight Deals.",
        "To unsubscribe, reply with 'Unsubscribe'.",
    ])

    return "\n".join(lines)


def build_premium_cabin_email(deal: dict) -> Tuple[str, str, str]:
    """
    Convenience function that returns everything needed for sending a premium cabin alert.

    Builds subject, plain text body, and HTML body from a single deal dict.
    This is the function that premium_cabin_monitor.py calls.

    Args:
        deal: Deal dict with origin, dest, dest_name, price, cabin_class,
              normal_price, departure_date, url. Optionally price_cents
              and normal_price_cents (in cents).

    Returns:
        Tuple of (subject, plain_body, html_body) ready for sending.
    """
    cabin_class = deal.get("cabin_class", "BUSINESS").upper()
    dest_name = deal.get("dest_name", deal.get("dest", "Unknown"))

    # Resolve price in cents for the subject
    price_cents = deal.get("price_cents")
    if price_cents is None:
        price = deal.get("price", 0)
        price_cents = int(price * 100) if isinstance(price, (int, float)) else 0

    # Resolve normal price in cents (optional)
    normal_price_cents = deal.get("normal_price_cents")
    if normal_price_cents is None:
        normal_price = deal.get("normal_price", 0)
        if normal_price:
            normal_price_cents = int(normal_price * 100) if isinstance(normal_price, (int, float)) else None
        else:
            normal_price_cents = None

    subject = format_premium_cabin_subject(
        dest_name=dest_name,
        price_cents=price_cents,
        cabin_class=cabin_class,
        normal_price_cents=normal_price_cents,
    )

    # Use empty subscriber name (the router provides subscriber context)
    plain_body = build_premium_cabin_alert_plain("", deal)
    html_body = build_premium_cabin_alert_html("", deal)

    return (subject, plain_body, html_body)
