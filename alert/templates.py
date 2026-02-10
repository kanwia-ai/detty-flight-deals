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

from typing import Dict, Optional, Tuple


# ==========================================================
# CONSTANTS
# ==========================================================

TIER_EMOJIS = {
    "Great": "*",       # Star for great deals
    "WOW": "**",        # Double star for WOW
    "MISTAKE": "!!",    # Warning for mistake fares
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
