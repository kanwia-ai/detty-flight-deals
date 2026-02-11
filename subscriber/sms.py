"""
Detty Flight Deals - SMS Alert Sender
Sends mistake fare SMS alerts via Twilio to premium subscribers.

Usage:
    from subscriber.sms import send_sms_alert

    success = send_sms_alert("+15551234567", deal_dict)
"""

import os
import logging

logger = logging.getLogger(__name__)


def send_sms_alert(phone: str, deal: dict) -> bool:
    """
    Send a mistake fare SMS alert via Twilio.

    Reads TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER
    from environment variables. If any are missing, logs a warning and
    returns False (graceful degradation).

    Args:
        phone: Recipient phone number (E.164 format, e.g. "+15551234567").
        deal: Deal dict with dest_name, price_cents or price, origin, dest, and url keys.

    Returns:
        True if SMS sent successfully, False otherwise.
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not account_sid or not auth_token or not from_number:
        logger.warning("[SMS] Twilio credentials not configured")
        return False

    try:
        from twilio.rest import Client
    except ImportError:
        logger.warning("[SMS] twilio package not installed, skipping SMS")
        return False

    # Build price from cents or dollars
    if "price_cents" in deal:
        price = deal["price_cents"] // 100
    else:
        price = deal.get("price", 0)

    dest_name = deal.get("dest_name", deal.get("dest", "Unknown"))
    origin = deal.get("origin", "???")
    url = deal.get("url", "")

    body = (
        f"MISTAKE FARE: {dest_name} ${price} from {origin}! "
        f"Book NOW before it disappears. {url}"
    )

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=phone,
        )
        logger.info(f"[SMS] Sent to {phone}: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"[SMS] Failed to send to {phone}: {e}")
        return False
