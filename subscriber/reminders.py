"""
Detty Flight Deals - Payment Reminder System

Sends payment reminder emails to premium subscribers approaching quarterly
expiry. Reminders are sent 7 days before expiry, with a more urgent
follow-up 1 day before if the subscriber hasn't renewed.

The get_subscribers_needing_reminder() query in db/client.py handles
the 6-day gap between reminders to prevent spam.

Pipeline:
  1. Initialize database connection
  2. Query subscribers with premium_expiry within 7 days
  3. For each subscriber, build personalized reminder email
  4. Send via Gmail SMTP (using mvp0_sender)
  5. Update payment_reminder_sent timestamp to prevent duplicates

Usage:
    python -m subscriber.reminders

    Called by the weekly_digest.yml GitHub Actions workflow (Plan 05).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ==========================================================
# EMAIL TEMPLATES
# ==========================================================

def _build_reminder_html(name: str, days_until: int, expiry_date: str, urgent: bool = False) -> str:
    """
    Build payment reminder email HTML.

    Follows the Detty email design system: Pan-African gradient header,
    rounded cards, consistent color scheme.

    Args:
        name: Subscriber display name (or "").
        days_until: Days until premium expiry.
        expiry_date: Formatted expiry date string.
        urgent: If True, uses more urgent styling and copy.

    Returns:
        Complete HTML document string.
    """
    greeting = f"Hey {name}!" if name else "Hey there!"

    if urgent:
        message = (
            f"Your Detty Premium subscription expires <strong>tomorrow</strong> "
            f"({expiry_date}). After that, you'll lose access to:"
        )
        banner_bg = "#FEF2F2"
        banner_border = "#DC2626"
        banner_text = "LAST DAY -- renew now to keep your Premium benefits"
    else:
        message = (
            f"Your Detty Premium subscription expires in <strong>{days_until} days</strong> "
            f"(on {expiry_date}). After that, you'll lose access to:"
        )
        banner_bg = "#FEF9C3"
        banner_border = "#F59E0B"
        banner_text = "Your Premium subscription is expiring soon"

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
                Premium Renewal
            </div>
        </div>

        <!-- Banner -->
        <div style="background:{banner_bg};border:2px solid {banner_border};border-radius:12px;padding:16px;margin-bottom:24px;text-align:center;">
            <div style="font-size:14px;font-weight:700;color:{banner_border};">
                {banner_text}
            </div>
        </div>

        <!-- Message -->
        <div style="background:#FFFFFF;border-radius:12px;padding:24px;margin-bottom:24px;">
            <div style="font-size:20px;font-weight:700;color:#0D0D0D;margin-bottom:12px;">
                {greeting}
            </div>
            <div style="font-size:15px;color:#525252;line-height:1.6;margin-bottom:20px;">
                {message}
            </div>

            <!-- What you'll lose -->
            <div style="margin-bottom:24px;">
                <div style="padding:12px 16px;background:#FEF2F2;border-radius:8px;margin-bottom:8px;">
                    <span style="color:#DC2626;font-weight:600;">Instant WOW and mistake fare alerts</span>
                </div>
                <div style="padding:12px 16px;background:#FEF2F2;border-radius:8px;margin-bottom:8px;">
                    <span style="color:#DC2626;font-weight:600;">SMS notifications for mistake fares</span>
                </div>
                <div style="padding:12px 16px;background:#FEF2F2;border-radius:8px;margin-bottom:8px;">
                    <span style="color:#DC2626;font-weight:600;">Historical price context</span>
                </div>
                <div style="padding:12px 16px;background:#FEF2F2;border-radius:8px;">
                    <span style="color:#DC2626;font-weight:600;">Unlimited metro preferences</span>
                </div>
            </div>

            <!-- Payment instructions -->
            <div style="background:#DCFCE7;border:2px solid #009639;border-radius:12px;padding:20px;margin-bottom:20px;">
                <div style="font-size:18px;font-weight:700;color:#009639;margin-bottom:12px;">
                    Renew for $15/quarter ($5/month)
                </div>
                <div style="font-size:15px;color:#0D0D0D;line-height:1.8;">
                    <strong>Venmo:</strong> @DettyFlightDeals<br>
                    <strong>Zelle:</strong> dettyflightdeals@gmail.com
                </div>
            </div>

            <div style="font-size:14px;color:#525252;line-height:1.6;">
                Once you've sent payment, just reply to this email and we'll renew your subscription right away.
            </div>
        </div>

        <!-- Footer -->
        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;margin-top:24px;">
            <div style="font-size:12px;color:#909090;">
                You signed up for Detty Flight Deals Premium.
            </div>
            <div style="font-size:12px;color:#909090;margin-top:8px;">
                <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe%20from%20Detty%20Flight%20Deals&body=Please%20unsubscribe%20me%20from%20Detty%20Flight%20Deals." style="color:#909090;text-decoration:underline;">Unsubscribe</a>
            </div>
        </div>

    </div>
</body>
</html>'''


def _build_reminder_plain(name: str, days_until: int, expiry_date: str, urgent: bool = False) -> str:
    """
    Build payment reminder email plain text.

    Args:
        name: Subscriber display name (or "").
        days_until: Days until premium expiry.
        expiry_date: Formatted expiry date string.
        urgent: If True, uses more urgent copy.

    Returns:
        Plain text email body string.
    """
    greeting = f"Hey {name}!" if name else "Hey there!"

    if urgent:
        headline = "LAST DAY -- your Premium expires tomorrow"
        message = f"Your Detty Premium subscription expires tomorrow ({expiry_date})."
    else:
        headline = "Your Premium subscription is expiring soon"
        message = f"Your Detty Premium subscription expires in {days_until} days (on {expiry_date})."

    return f"""{headline}
{"=" * 40}

{greeting}

{message}

After that, you'll lose access to:
  - Instant WOW and mistake fare alerts
  - SMS notifications for mistake fares
  - Historical price context
  - Unlimited metro preferences

RENEW FOR $15/QUARTER ($5/MONTH)
{"-" * 40}
  Venmo: @DettyFlightDeals
  Zelle: dettyflightdeals@gmail.com

Once you've sent payment, just reply to this email and we'll
renew your subscription right away.

---
You signed up for Detty Flight Deals Premium.
To unsubscribe, reply with 'Unsubscribe'.
"""


# ==========================================================
# SEND PIPELINE
# ==========================================================

def send_payment_reminders() -> dict:
    """
    Send payment reminders to premium subscribers approaching expiry.

    Checks for subscribers whose premium_expiry is within 7 days.
    Sends reminder email with Venmo/Zelle payment instructions.
    Updates payment_reminder_sent timestamp after sending.

    The get_subscribers_needing_reminder() query in db/client.py
    handles the 6-day gap between reminders, so calling with
    days_before=7 gets both 7-day and 1-day reminders (the 1-day
    reminders are subscribers whose last reminder was >6 days ago
    and premium_expiry is within 1 day).

    Returns:
        Dict with {"reminders_sent": N, "errors": N}
    """
    from db.client import TursoClient
    from mvp0_sender import send_to_subscriber

    print("=" * 50)
    print("DETTY PAYMENT REMINDERS")
    print("=" * 50)

    # Initialize database
    db = TursoClient()
    if not db._turso_available:
        print("[REMINDERS] Turso database not available. Skipping reminders.")
        return {"reminders_sent": 0, "errors": 0}

    # Get subscribers needing reminders (7-day window, 6-day gap)
    subscribers = db.get_subscribers_needing_reminder(days_before=7)

    if not subscribers:
        print("No payment reminders needed.")
        return {"reminders_sent": 0, "errors": 0}

    print(f"Found {len(subscribers)} subscriber(s) needing payment reminders.")

    sent = 0
    errors = 0

    for i, subscriber in enumerate(subscribers, 1):
        email = subscriber.get("email", "unknown")
        name = subscriber.get("name", "")
        premium_expiry = subscriber.get("premium_expiry", "")

        # Calculate days until expiry
        try:
            expiry_dt = datetime.fromisoformat(premium_expiry.replace("Z", "+00:00"))
            now = datetime.now(expiry_dt.tzinfo) if expiry_dt.tzinfo else datetime.now()
            days_until = (expiry_dt - now).days
        except (ValueError, TypeError, AttributeError):
            days_until = 7  # Default to 7 if parsing fails
            logger.warning(f"[REMINDERS] Could not parse expiry date: {premium_expiry}")

        # Format expiry date for display
        try:
            expiry_display = datetime.fromisoformat(
                premium_expiry.replace("Z", "+00:00")
            ).strftime("%B %d, %Y")
        except (ValueError, TypeError, AttributeError):
            expiry_display = premium_expiry or "soon"

        # Determine urgency
        urgent = days_until <= 1

        # Build subject
        if urgent:
            subject = "LAST DAY: Your Detty Premium expires tomorrow"
        else:
            subject = "Your Detty Premium subscription renews soon"

        # Build email
        html_body = _build_reminder_html(name, days_until, expiry_display, urgent=urgent)
        plain_body = _build_reminder_plain(name, days_until, expiry_display, urgent=urgent)

        # Send
        print(f"  [{i}/{len(subscribers)}] {email} (expires in {days_until} day(s))...", end=" ")
        success = send_to_subscriber(email, subject, html_body, plain_body)

        if success:
            # Update payment_reminder_sent to prevent duplicate reminders
            db.update_subscriber(
                email,
                payment_reminder_sent=datetime.now().isoformat(),
            )
            sent += 1
            print("OK")
        else:
            errors += 1
            print("FAILED")

    # Summary
    print()
    print(f"Payment Reminder Summary:")
    print(f"  Sent: {sent}")
    print(f"  Errors: {errors}")

    return {"reminders_sent": sent, "errors": errors}


# ==========================================================
# CLI ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    result = send_payment_reminders()
    print(f"\nPayment Reminders: {result}")
