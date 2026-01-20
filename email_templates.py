"""
Detty Flight Deals - Email Templates

Two types:
1. Instant WOW Alert - Urgent, for WOW deals with meaningful changes
2. Weekly Digest - Calm summary of Good + Great deals (Sundays)
"""

from datetime import datetime


def format_departure_short(departure: str) -> str:
    """Format '2026-03-30' as 'Mar 30'."""
    try:
        dt = datetime.strptime(departure, "%Y-%m-%d")
        return dt.strftime("%b %d")
    except:
        return departure


# ============================================================
# INSTANT WOW ALERT (Urgent - Book Now!)
# ============================================================

def build_wow_alert_html(deals: list) -> str:
    """
    Build urgent WOW alert email.
    Emphasizes scarcity and urgency.
    """
    num_deals = len(deals)

    # Build deal cards
    deals_html = ""
    for deal in deals:
        dest_name = deal.get("dest_name", deal.get("dest", "Unknown"))
        best_price = deal.get("best_price", deal.get("price", 0))
        percent = deal.get("percent_below", 0)
        normal = deal.get("normal_price", 1000)

        # Origins list
        origins = deal.get("origins", {})
        if not origins and "origin" in deal:
            origins = {deal["origin"]: {"price": deal["price"], "departure": deal.get("departure", ""), "url": deal.get("url", "")}}

        origins_html = ""
        for origin, info in sorted(origins.items(), key=lambda x: x[1].get("price", 9999)):
            dep_short = format_departure_short(info.get("departure", ""))
            url = info.get("url", "#")
            origins_html += f'''
            <a href="{url}" style="display:inline-block;background:#E31C25;color:#FFF;border-radius:8px;padding:12px 16px;margin:4px;text-decoration:none;font-size:14px;font-weight:600;">
                {origin} ${info.get("price", best_price)} → <span style="opacity:0.9;">({dep_short})</span>
            </a>'''

        # Change reason if present
        change_html = ""
        if deal.get("change_reason"):
            change_html = f'<div style="font-size:12px;color:#009639;font-weight:600;margin-bottom:8px;">✨ {deal["change_reason"]}</div>'

        deals_html += f'''
        <div style="background:#FEF9C3;border:3px solid #FCD116;border-radius:16px;padding:24px;margin-bottom:20px;">
            {change_html}
            <div style="font-size:28px;font-weight:900;color:#0D0D0D;margin-bottom:4px;">
                {dest_name}
            </div>
            <div style="font-size:16px;color:#525252;margin-bottom:16px;">
                From <strong style="color:#E31C25;font-size:24px;">${best_price}</strong> · {percent}% below normal (${normal})
            </div>
            <div>{origins_html}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#FEF9C3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">

        <!-- Urgent Header -->
        <div style="text-align:center;padding:32px 20px;margin-bottom:24px;background:#E31C25;border-radius:16px;">
            <div style="font-size:14px;color:#FFF;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px;">
                🚨 WOW DEAL ALERT 🚨
            </div>
            <div style="font-size:32px;font-weight:900;color:#FFF;margin-bottom:8px;">
                Mistake Fare Territory
            </div>
            <div style="font-size:16px;color:rgba(255,255,255,0.9);">
                {num_deals} destination{"s" if num_deals > 1 else ""} at historic lows — book first, ask questions later!
            </div>
        </div>

        <!-- Deals -->
        {deals_html}

        <!-- Urgency Footer -->
        <div style="background:#FFFFFF;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
            <div style="font-size:18px;font-weight:700;color:#E31C25;margin-bottom:8px;">
                ⚡ These prices won't last
            </div>
            <div style="font-size:14px;color:#525252;">
                WOW deals typically disappear within 24-48 hours. Airlines fix pricing errors fast.
            </div>
        </div>

        <!-- Feedback -->
        <div style="background:#FFFFFF;border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:14px;color:#525252;margin-bottom:12px;">
                Booked this deal? Let us know!
            </div>
            <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display:inline-block;background:#009639;color:#FFF;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;margin:4px;">I booked!</a>
            <a href="mailto:?subject=INSANE%20flight%20deal%20to%20Africa&body=Check%20this%20out%20-%20flights%20to%20Africa%20are%20crazy%20cheap%20right%20now!" style="display:inline-block;background:#FFF;color:#0D0D0D;border:2px solid #0D0D0D;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;margin:4px;">Share with friend</a>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;font-size:12px;color:#909090;">
            You're receiving this because you signed up for Detty Flight Deals.<br>
            <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe&body=Please%20unsubscribe%20me." style="color:#909090;">Unsubscribe</a>
        </div>

    </div>
</body>
</html>'''


def build_wow_alert_plain(deals: list) -> str:
    """Plain text version of WOW alert."""
    lines = [
        "🚨 WOW DEAL ALERT 🚨",
        "=" * 50,
        "MISTAKE FARE TERRITORY",
        "Book first, ask questions later!",
        "",
    ]

    for deal in deals:
        dest_name = deal.get("dest_name", deal.get("dest", "Unknown"))
        best_price = deal.get("best_price", deal.get("price", 0))
        percent = deal.get("percent_below", 0)

        lines.append(f"{dest_name}")
        lines.append(f"  ${best_price} ({percent}% below normal)")

        origins = deal.get("origins", {})
        if origins:
            for origin, info in origins.items():
                lines.append(f"  → {origin}: ${info.get('price', best_price)} - {info.get('url', '')}")
        lines.append("")

    lines.append("⚡ These prices won't last! Book NOW.")
    return "\n".join(lines)


def build_wow_alert_subject(deals: list) -> str:
    """Subject line for WOW alert."""
    if len(deals) == 1:
        dest = deals[0].get("dest_name", "Africa")
        price = deals[0].get("best_price", deals[0].get("price", "???"))
        return f"🚨 MISTAKE FARE: {dest} from ${price}!"
    else:
        dests = [d.get("dest_name", "")[:6] for d in deals[:3]]
        return f"🚨 MISTAKE FARES: {', '.join(dests)} at historic lows!"


# ============================================================
# WEEKLY DIGEST (Calm - Here's what's on sale)
# ============================================================

def build_weekly_digest_html(deals: list) -> str:
    """
    Build calm weekly digest email.
    Informational, not urgent.
    """
    # Separate Great and Good
    great_deals = [d for d in deals if d.get("tier") == "Great"]
    good_deals = [d for d in deals if d.get("tier") == "Good"]

    def build_tier_section(tier_deals: list, tier_name: str, emoji: str, bg_color: str, border_color: str) -> str:
        if not tier_deals:
            return ""

        cards_html = ""
        for deal in sorted(tier_deals, key=lambda x: x.get("best_price", x.get("price", 9999))):
            dest_name = deal.get("dest_name", deal.get("dest", "Unknown"))
            best_price = deal.get("best_price", deal.get("price", 0))
            percent = deal.get("percent_below", 0)
            normal = deal.get("normal_price", 1000)

            # Origins
            origins = deal.get("origins", {})
            if not origins and "origin" in deal:
                origins = {deal["origin"]: {"price": deal["price"], "departure": deal.get("departure", ""), "url": deal.get("url", "")}}

            origins_html = ""
            for origin, info in sorted(origins.items(), key=lambda x: x[1].get("price", 9999)):
                dep_short = format_departure_short(info.get("departure", ""))
                url = info.get("url", "#")
                origins_html += f'''
                <a href="{url}" style="display:inline-block;background:#525252;color:#FFF;border-radius:6px;padding:8px 12px;margin:3px;text-decoration:none;font-size:12px;font-weight:500;">
                    {origin} ${info.get("price", best_price)} ({dep_short})
                </a>'''

            cards_html += f'''
            <div style="background:{bg_color};border:1px solid {border_color};border-radius:10px;padding:16px;margin-bottom:12px;">
                <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:4px;">{dest_name}</div>
                <div style="font-size:13px;color:#525252;margin-bottom:10px;">
                    From <strong style="color:#009639;">${best_price}</strong> · {percent}% off (usually ${normal})
                </div>
                <div>{origins_html}</div>
            </div>'''

        return f'''
        <div style="margin-bottom:24px;">
            <div style="font-size:14px;font-weight:700;color:#525252;margin-bottom:12px;text-transform:uppercase;letter-spacing:1px;">
                {emoji} {tier_name}
            </div>
            {cards_html}
        </div>'''

    great_html = build_tier_section(great_deals, "Great Deals", "✨", "#DCFCE7", "#009639")
    good_html = build_tier_section(good_deals, "Good Deals", "💰", "#F5F5F5", "#D4D4D4")

    total = len(deals)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#F5F5F5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
    <div style="max-width:600px;margin:0 auto;padding:20px;">

        <!-- Calm Header -->
        <div style="text-align:center;padding:24px 0;margin-bottom:24px;">
            <div style="font-size:28px;font-weight:800;margin-bottom:8px;">
                ✈️ <span style="background:linear-gradient(90deg,#009639,#FCD116,#E31C25);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Detty</span> <span style="color:#262626;">Weekly Digest</span>
            </div>
            <div style="font-size:14px;color:#525252;">
                {total} destinations on sale this week
            </div>
        </div>

        <!-- Intro -->
        <div style="background:#FFFFFF;border-radius:12px;padding:20px;margin-bottom:24px;text-align:center;">
            <div style="font-size:16px;color:#525252;">
                Here's what's on sale for Africa flights this week. These aren't flash deals — they'll likely be available for a few days.
            </div>
        </div>

        <!-- Great Deals -->
        {great_html}

        <!-- Good Deals -->
        {good_html}

        <!-- Tier Explanation -->
        <div style="background:#FFFEF7;border:1px solid #FCD116;border-radius:10px;padding:16px;margin-bottom:24px;">
            <div style="font-size:13px;color:#525252;">
                <strong>✨ Great</strong> = 30-39% below normal — solid savings<br>
                <strong>💰 Good</strong> = 20-29% below normal — worth booking if dates work
            </div>
        </div>

        <!-- Feedback -->
        <div style="background:#FFFFFF;border-radius:12px;padding:20px;text-align:center;">
            <div style="font-size:14px;color:#525252;margin-bottom:12px;">
                Planning a trip? Let us know if you book!
            </div>
            <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display:inline-block;background:#009639;color:#FFF;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:600;font-size:13px;margin:4px;">Share feedback</a>
            <a href="mailto:?subject=Africa%20flight%20deals&body=Found%20some%20good%20deals%20on%20Detty%20Flight%20Deals!" style="display:inline-block;background:#FFF;color:#0D0D0D;border:1px solid #D4D4D4;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:600;font-size:13px;margin:4px;">Share with friend</a>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;font-size:12px;color:#909090;">
            Weekly digest sent every Sunday.<br>
            You'll still get instant alerts for WOW deals (40%+ off).<br><br>
            <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe&body=Please%20unsubscribe%20me." style="color:#909090;">Unsubscribe</a>
        </div>

    </div>
</body>
</html>'''


def build_weekly_digest_plain(deals: list) -> str:
    """Plain text version of weekly digest."""
    lines = [
        "DETTY WEEKLY DIGEST",
        "=" * 40,
        f"{len(deals)} destinations on sale this week",
        "",
    ]

    great = [d for d in deals if d.get("tier") == "Great"]
    good = [d for d in deals if d.get("tier") == "Good"]

    if great:
        lines.append("✨ GREAT DEALS (30-39% off)")
        lines.append("-" * 30)
        for deal in great:
            lines.append(f"  {deal.get('dest_name', deal.get('dest'))}: ${deal.get('best_price', deal.get('price'))}")
        lines.append("")

    if good:
        lines.append("💰 GOOD DEALS (20-29% off)")
        lines.append("-" * 30)
        for deal in good:
            lines.append(f"  {deal.get('dest_name', deal.get('dest'))}: ${deal.get('best_price', deal.get('price'))}")
        lines.append("")

    lines.append("Weekly digest sent every Sunday.")
    return "\n".join(lines)


def build_weekly_digest_subject(deals: list) -> str:
    """Subject line for weekly digest."""
    great = len([d for d in deals if d.get("tier") == "Great"])
    good = len([d for d in deals if d.get("tier") == "Good"])

    parts = []
    if great:
        parts.append(f"{great} Great")
    if good:
        parts.append(f"{good} Good")

    return f"✈️ Weekly Digest: {' + '.join(parts)} deals to Africa"
