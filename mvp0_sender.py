"""
Detty Flight Deals - MVP0 Email Sender
Reads subscribers from Google Sheet, sends HTML emails via Gmail SMTP.
Cap: 200 subscribers. Includes feedback form link.
"""

import os
import json
import smtplib
import time
import gspread
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials

# ============================================================
# CONFIGURATION
# ============================================================

# Gmail SMTP
SMTP_EMAIL = os.environ.get("SMTP_EMAIL")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

# Google Sheets (subscriber list)
GOOGLE_SHEETS_CREDS = os.environ.get("GOOGLE_SHEETS_CREDS")  # JSON string
GOOGLE_SHEETS_CREDS_FILE = os.environ.get("GOOGLE_SHEETS_CREDS_FILE")  # Or path to JSON file
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")  # From sheet URL
MAX_SUBSCRIBERS = 200

# Feedback form (Google Form URL)
FEEDBACK_FORM_URL = os.environ.get("FEEDBACK_FORM_URL", "https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform")


# ============================================================
# GOOGLE SHEETS
# ============================================================

def get_subscribers() -> list[str]:
    """Get subscriber emails from Google Sheet, capped at 200."""
    # Read env vars at runtime (not module load time)
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDS")
    creds_file = os.environ.get("GOOGLE_SHEETS_CREDS_FILE")

    if not sheet_id:
        print("⚠️ Google Sheet ID not configured")
        return []

    if not creds_json and not creds_file:
        print("⚠️ Google Sheets credentials not configured")
        return []

    try:
        # Load credentials from file or JSON string
        if creds_file and os.path.exists(creds_file):
            with open(creds_file, 'r') as f:
                creds_dict = json.load(f)
        else:
            creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )

        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(sheet_id).sheet1

        # Find email column (usually column 2 or 3 in form responses)
        headers = sheet.row_values(1)
        email_col = 1  # default
        for i, header in enumerate(headers, 1):
            if 'email' in header.lower():
                email_col = i
                break

        all_values = sheet.col_values(email_col)

        emails = []
        for val in all_values:
            val = val.strip().lower()
            if "@" in val and "." in val and val != "email":
                emails.append(val)

        # Cap at MAX_SUBSCRIBERS
        if len(emails) > MAX_SUBSCRIBERS:
            print(f"⚠️ {len(emails)} subscribers, capping at {MAX_SUBSCRIBERS}")
            emails = emails[:MAX_SUBSCRIBERS]

        print(f"📋 Loaded {len(emails)} subscribers")
        return emails

    except Exception as e:
        print(f"❌ Error reading sheet: {e}")
        return []


# ============================================================
# EMAIL TEMPLATES
# ============================================================

def build_html_email(deals: list) -> str:
    """Build styled HTML email body."""

    # Build deal cards
    deals_html = ""
    for deal in deals:
        tier = deal.get("tier", "Good")

        # Tier-specific colors
        if tier == "WOW":
            bg, border, badge_style = "#FEF9C3", "#FCD116", "background:#FCD116;color:#000;"
        elif tier == "Great":
            bg, border, badge_style = "#DCFCE7", "#009639", "background:#009639;color:#FFF;"
        else:
            bg, border, badge_style = "#F5F5F5", "#525252", "background:#525252;color:#FFF;"

        deals_html += f'''
        <div style="background:{bg};border:2px solid {border};border-radius:12px;padding:20px;margin-bottom:16px;">
            <div style="margin-bottom:12px;">
                <span style="{badge_style}padding:4px 12px;border-radius:50px;font-size:12px;font-weight:700;">{tier.upper()} DEAL</span>
            </div>
            <div style="font-size:24px;font-weight:800;color:#009639;margin-bottom:4px;">
                ${deal['price']} <span style="font-size:14px;font-weight:400;color:#525252;">round-trip</span>
            </div>
            <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
                {deal['origin']} → {deal['dest_name']}
            </div>
            <div style="font-size:14px;color:#525252;margin-bottom:12px;">
                {deal.get('percent_below', 0)}% below normal (usually ${deal.get('normal_price', 1200)})
            </div>
            <div style="font-size:14px;color:#525252;margin-bottom:16px;">
                📅 {deal['departure']} to {deal['return']}<br>
                💰 Prices found: ${deal['lowest_found']} - ${deal['highest_found']}
            </div>
            <a href="{deal['url']}" style="display:inline-block;background:#E31C25;color:#FFF;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">Book Now →</a>
        </div>
        '''

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
                ✈️ <span style="background:linear-gradient(90deg,#009639,#FCD116,#E31C25);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Detty</span> <span style="color:#262626;">Flight Deals</span>
            </div>
            <div style="font-size:14px;color:#525252;">
                Found {len(deals)} deal(s) to Africa
            </div>
        </div>

        <!-- Deals -->
        {deals_html}

        <!-- Feedback CTA -->
        <div style="padding:32px 24px;background:#FFFEF7;border-radius:12px;margin-top:24px;border:1px solid #E5E5E5;">
            <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">
                Booked this deal? Let us know.
            </div>
            <div style="font-size:14px;color:#525252;margin-bottom:20px;">
                We'd love to hear if you booked a trip! Know someone who'd love these deals? Share with them.
            </div>
            <div>
                <a href="{FEEDBACK_FORM_URL}" style="display:inline-block;background:#009639;color:#FFF;padding:14px 28px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;margin-right:12px;margin-bottom:8px;">I booked this deal</a>
                <a href="mailto:?subject=Check%20out%20these%20Africa%20flight%20deals&body=I%20found%20cheap%20flights%20to%20Africa%20on%20Detty%20Flight%20Deals.%20Sign%20up%20here%3A%20https%3A%2F%2Fdettyflightdeals.com" style="display:inline-block;background:transparent;color:#0D0D0D;padding:14px 28px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;border:2px solid #0D0D0D;margin-right:12px;margin-bottom:8px;">Share with a friend</a>
                <a href="{FEEDBACK_FORM_URL}" style="display:inline-block;background:#FCD116;color:#000;padding:14px 28px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;margin-bottom:8px;">Give feedback</a>
            </div>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;margin-top:24px;">
            <div style="font-size:12px;color:#525252;margin-bottom:8px;">
                💡 <strong>WOW deals</strong> are mistake fare territory — book first, ask questions later!
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


def build_plain_email(deals: list) -> str:
    """Build plain text email (fallback)."""
    body = "DETTY FLIGHT DEALS\n"
    body += "=" * 40 + "\n\n"

    for deal in deals:
        tier = deal.get("tier", "Good")
        body += f"{tier.upper()} DEAL: {deal['origin']} → {deal['dest_name']}\n"
        body += f"${deal['price']} round-trip\n"
        body += f"{deal.get('percent_below', 0)}% below normal\n"
        body += f"Dates: {deal['departure']} to {deal['return']}\n"
        body += f"Book: {deal['url']}\n"
        body += "-" * 40 + "\n\n"

    body += f"\nFeedback? {FEEDBACK_FORM_URL}\n"
    body += "\nTo unsubscribe, reply to this email with 'Unsubscribe'.\n"
    return body


# ============================================================
# EMAIL SENDING
# ============================================================

def send_to_subscriber(email: str, subject: str, html_body: str, plain_body: str) -> bool:
    """Send email to a single subscriber via Gmail SMTP."""
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        print("⚠️ SMTP credentials not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_email
    msg["To"] = email
    msg["Subject"] = subject

    # Attach both plain and HTML versions
    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, email, msg.as_string())
        return True
    except Exception as e:
        print(f"  ❌ Failed to send to {email}: {e}")
        return False


# ============================================================
# WELCOME EMAIL
# ============================================================

def build_welcome_html(name: str = "") -> str:
    """Build welcome email HTML."""
    greeting = f"Hey {name}!" if name else "Hey there!"

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
                ✈️ <span style="background:linear-gradient(90deg,#009639,#FCD116,#E31C25);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Detty</span> <span style="color:#262626;">Flight Deals</span>
            </div>
        </div>

        <!-- Welcome Message -->
        <div style="background:#FFFFFF;border-radius:12px;padding:32px;margin-bottom:24px;">
            <div style="font-size:24px;font-weight:700;color:#0D0D0D;margin-bottom:16px;">
                {greeting} Welcome to the family! 🎉
            </div>
            <div style="font-size:16px;color:#525252;line-height:1.6;">
                <p>You're now on the list for cheap flights to Africa. We monitor prices to Lagos, Accra, Dakar, Kinshasa, and 7 more cities so you don't have to.</p>
            </div>
        </div>

        <!-- What you'll receive -->
        <div style="margin-bottom:24px;">
            <div style="font-size:14px;font-weight:700;color:#525252;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">
                What you'll receive
            </div>

            <!-- Rare Price -->
            <div style="background:#FEE2E2;border:2px solid #DC2626;border-radius:12px;padding:20px;margin-bottom:12px;">
                <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:4px;">
                    🚨 "Rare price. Book immediately."
                </div>
                <div style="font-size:14px;color:#525252;">
                    Exceptional deals that don't come around often. When you see this, act fast — these prices can disappear within hours.
                </div>
            </div>

            <!-- Great Deal -->
            <div style="background:#FEF9C3;border:2px solid #F59E0B;border-radius:12px;padding:20px;margin-bottom:12px;">
                <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:4px;">
                    🔥 "Great deal. Book soon."
                </div>
                <div style="font-size:14px;color:#525252;">
                    Significantly below typical prices. You have a bit more time, but don't wait too long.
                </div>
            </div>

            <!-- Solid Price -->
            <div style="background:#DCFCE7;border:2px solid #009639;border-radius:12px;padding:20px;">
                <div style="font-size:18px;font-weight:700;color:#0D0D0D;margin-bottom:4px;">
                    ✈️ "Solid price. Worth considering."
                </div>
                <div style="font-size:14px;color:#525252;">
                    Better than usual — a good opportunity if you're flexible on dates.
                </div>
            </div>
        </div>

        <!-- How it works -->
        <div style="background:#FFFFFF;border-radius:12px;padding:20px;margin-bottom:24px;">
            <div style="font-size:14px;color:#525252;line-height:1.6;">
                <strong>How it works:</strong> We scan prices daily. You'll only hear from us when a route drops into a new price tier — no spam from small fluctuations.
            </div>
        </div>

        <!-- Beta Notice -->
        <div style="background:#F5F5F5;border:1px solid #E5E5E5;border-radius:12px;padding:20px;margin-bottom:24px;">
            <div style="font-size:14px;font-weight:700;color:#0D0D0D;margin-bottom:4px;">
                🚧 We're in beta
            </div>
            <div style="font-size:13px;color:#525252;margin-bottom:12px;">
                Your feedback helps us build something great.
            </div>
            <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display:inline-block;background:#FCD116;color:#000;padding:10px 20px;border-radius:50px;text-decoration:none;font-weight:600;font-size:13px;">Share Feedback</a>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;">
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


def build_welcome_plain(name: str = "") -> str:
    """Build welcome email plain text."""
    greeting = f"Hey {name}!" if name else "Hey there!"

    return f'''{greeting} Welcome to the family!

You're now on the list for cheap flights to Africa. We monitor prices to Lagos, Accra, Dakar, Kinshasa, and 7 more cities so you don't have to.

WHAT YOU'LL RECEIVE
==================

🚨 "Rare price. Book immediately."
Exceptional deals that don't come around often. When you see this, act fast — these prices can disappear within hours.

🔥 "Great deal. Book soon."
Significantly below typical prices. You have a bit more time, but don't wait too long.

✈️ "Solid price. Worth considering."
Better than usual — a good opportunity if you're flexible on dates.

How it works: We scan prices daily. You'll only hear from us when a route drops into a new price tier — no spam from small fluctuations.

---
WE'RE IN BETA
Your feedback helps us build something great.
Share feedback: https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform

---
You signed up for Detty Flight Deals.
To unsubscribe, reply with "Unsubscribe".
'''


def send_welcome_email(email: str, name: str = "") -> bool:
    """Send welcome email to a new subscriber."""
    subject = "Welcome to Detty Flight Deals! ✈️"
    html_body = build_welcome_html(name)
    plain_body = build_welcome_plain(name)

    print(f"📧 Sending welcome email to {email}...")
    if send_to_subscriber(email, subject, html_body, plain_body):
        print(f"  ✅ Welcome email sent!")
        return True
    return False


def send_deals_to_all(deals: list):
    """Send deals to all subscribers from Google Sheet."""
    if not deals:
        print("No deals to send")
        return

    # Get subscribers
    subscribers = get_subscribers()
    if not subscribers:
        print("No subscribers found")
        return

    # Build subject
    tier_counts = {}
    for deal in deals:
        tier = deal.get("tier", "Good")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    subject_parts = []
    if tier_counts.get("WOW", 0):
        subject_parts.append(f"{tier_counts['WOW']} WOW")
    if tier_counts.get("Great", 0):
        subject_parts.append(f"{tier_counts['Great']} Great")
    if tier_counts.get("Good", 0):
        subject_parts.append(f"{tier_counts['Good']} Good")

    subject = f"🔥 Detty Deals: {' + '.join(subject_parts)} deal(s) to Africa!"

    # Build email bodies
    html_body = build_html_email(deals)
    plain_body = build_plain_email(deals)

    # Send to each subscriber
    print(f"\n📧 Sending to {len(subscribers)} subscribers...")
    success = 0
    failed = 0

    for i, email in enumerate(subscribers, 1):
        print(f"  [{i}/{len(subscribers)}] {email}...", end=" ")
        if send_to_subscriber(email, subject, html_body, plain_body):
            print("✓")
            success += 1
        else:
            failed += 1

        # Small delay to avoid rate limiting
        if i < len(subscribers):
            time.sleep(0.5)

    print(f"\n✅ Sent: {success} | ❌ Failed: {failed}")


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    import sys

    # Test with sample deals
    sample_deals = [
        {
            "origin": "IAD",
            "dest": "ABJ",
            "dest_name": "Abidjan",
            "price": 649,
            "tier": "WOW",
            "percent_below": 50,
            "normal_price": 1300,
            "departure": "2026-02-15",
            "return": "2026-02-25",
            "lowest_found": 649,
            "highest_found": 1150,
            "url": "https://www.google.com/travel/flights?q=Flights%20from%20IAD%20to%20ABJ"
        },
        {
            "origin": "JFK",
            "dest": "LOS",
            "dest_name": "Lagos",
            "price": 623,
            "tier": "Great",
            "percent_below": 48,
            "normal_price": 1200,
            "departure": "2026-02-20",
            "return": "2026-03-02",
            "lowest_found": 623,
            "highest_found": 980,
            "url": "https://www.google.com/travel/flights?q=Flights%20from%20JFK%20to%20LOS"
        },
    ]

    print("MVP0 Email Sender")
    print("=" * 40)

    # Check for command line args
    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "welcome":
            # Send welcome email to a specific address
            email = sys.argv[2] if len(sys.argv) > 2 else None
            name = sys.argv[3] if len(sys.argv) > 3 else ""
            if email:
                send_welcome_email(email, name)
            else:
                print("Usage: python3 mvp0_sender.py welcome <email> [name]")

        elif cmd == "deals":
            # Send deals to all subscribers
            send_deals_to_all(sample_deals)

        else:
            print("Commands:")
            print("  python3 mvp0_sender.py welcome <email> [name]  - Send welcome email")
            print("  python3 mvp0_sender.py deals                   - Send deals to all subscribers")
    else:
        # Default: show subscribers
        subs = get_subscribers()
        print(f"Subscribers: {subs}")
        print("\nCommands:")
        print("  python3 mvp0_sender.py welcome <email> [name]  - Send welcome email")
        print("  python3 mvp0_sender.py deals                   - Send deals to all subscribers")
