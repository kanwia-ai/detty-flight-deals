#!/usr/bin/env python3
"""
Send test emails to preview the new formats:
1. Instant WOW Alert
2. Weekly Digest

Usage:
    python3 send_test_emails.py <email_address>
    python3 send_test_emails.py kyra.atekwana@gmail.com
"""

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from email_templates import (
    build_wow_alert_html, build_wow_alert_plain, build_wow_alert_subject,
    build_weekly_digest_html, build_weekly_digest_plain, build_weekly_digest_subject,
)
from mvp0_sender import send_to_subscriber


# Sample WOW deals (for instant alert preview)
SAMPLE_WOW_DEALS = [
    {
        "dest": "FIH",
        "dest_name": "Kinshasa",
        "tier": "WOW",
        "best_price": 749,
        "percent_below": 50,
        "normal_price": 1500,
        "change_reason": "New WOW deal!",
        "origins": {
            "JFK": {"price": 749, "departure": "2026-03-10", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20FIH"},
            "EWR": {"price": 785, "departure": "2026-03-15", "url": "https://www.google.com/travel/flights?q=Flights%20EWR%20to%20FIH"},
        }
    },
    {
        "dest": "ACC",
        "dest_name": "Accra",
        "tier": "WOW",
        "best_price": 520,
        "percent_below": 42,
        "normal_price": 900,
        "change_reason": "Price dropped $150!",
        "origins": {
            "JFK": {"price": 520, "departure": "2026-04-05", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20ACC"},
            "IAD": {"price": 545, "departure": "2026-04-12", "url": "https://www.google.com/travel/flights?q=Flights%20IAD%20to%20ACC"},
            "ATL": {"price": 560, "departure": "2026-04-08", "url": "https://www.google.com/travel/flights?q=Flights%20ATL%20to%20ACC"},
        }
    },
]


# Sample Good/Great deals (for weekly digest preview)
SAMPLE_DIGEST_DEALS = [
    {
        "dest": "DSS",
        "dest_name": "Dakar",
        "tier": "Great",
        "best_price": 628,
        "percent_below": 37,
        "normal_price": 1000,
        "origins": {
            "IAD": {"price": 628, "departure": "2026-03-17", "url": "https://www.google.com/travel/flights?q=Flights%20IAD%20to%20DSS"},
            "JFK": {"price": 695, "departure": "2026-03-20", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20DSS"},
        }
    },
    {
        "dest": "ABJ",
        "dest_name": "Abidjan",
        "tier": "Great",
        "best_price": 885,
        "percent_below": 32,
        "normal_price": 1300,
        "origins": {
            "JFK": {"price": 885, "departure": "2026-03-10", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20ABJ"},
            "EWR": {"price": 899, "departure": "2026-04-07", "url": "https://www.google.com/travel/flights?q=Flights%20EWR%20to%20ABJ"},
        }
    },
    {
        "dest": "LOS",
        "dest_name": "Lagos",
        "tier": "Great",
        "best_price": 720,
        "percent_below": 30,
        "normal_price": 1030,
        "origins": {
            "IAD": {"price": 720, "departure": "2026-05-01", "url": "https://www.google.com/travel/flights?q=Flights%20IAD%20to%20LOS"},
        }
    },
    {
        "dest": "COO",
        "dest_name": "Cotonou",
        "tier": "Good",
        "best_price": 919,
        "percent_below": 23,
        "normal_price": 1200,
        "origins": {
            "JFK": {"price": 919, "departure": "2026-03-10", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20COO"},
            "EWR": {"price": 925, "departure": "2026-03-10", "url": "https://www.google.com/travel/flights?q=Flights%20EWR%20to%20COO"},
        }
    },
    {
        "dest": "DLA",
        "dest_name": "Douala",
        "tier": "Good",
        "best_price": 983,
        "percent_below": 26,
        "normal_price": 1330,
        "origins": {
            "JFK": {"price": 983, "departure": "2026-07-07", "url": "https://www.google.com/travel/flights?q=Flights%20JFK%20to%20DLA"},
        }
    },
]


def send_test_wow_alert(email: str) -> bool:
    """Send test WOW alert email."""
    subject = build_wow_alert_subject(SAMPLE_WOW_DEALS)
    subject = f"[TEST] {subject}"  # Mark as test

    html = build_wow_alert_html(SAMPLE_WOW_DEALS)
    plain = build_wow_alert_plain(SAMPLE_WOW_DEALS)

    print(f"\n📧 Sending TEST WOW Alert to {email}...")
    print(f"   Subject: {subject}")

    return send_to_subscriber(email, subject, html, plain)


def send_test_digest(email: str) -> bool:
    """Send test weekly digest email."""
    subject = build_weekly_digest_subject(SAMPLE_DIGEST_DEALS)
    subject = f"[TEST] {subject}"  # Mark as test

    html = build_weekly_digest_html(SAMPLE_DIGEST_DEALS)
    plain = build_weekly_digest_plain(SAMPLE_DIGEST_DEALS)

    print(f"\n📧 Sending TEST Weekly Digest to {email}...")
    print(f"   Subject: {subject}")

    return send_to_subscriber(email, subject, html, plain)


def send_test_welcome(email: str) -> bool:
    """Send test welcome email."""
    from mvp0_sender import build_welcome_html, build_welcome_plain

    subject = "[TEST] Welcome to Detty Flight Deals! ✈️"
    html = build_welcome_html("")
    plain = build_welcome_plain("")

    print(f"\n📧 Sending TEST Welcome Email to {email}...")
    print(f"   Subject: {subject}")

    return send_to_subscriber(email, subject, html, plain)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 send_test_emails.py <email_address> [type]")
        print("Example: python3 send_test_emails.py kyra.atekwana@gmail.com")
        print("         python3 send_test_emails.py kyra.atekwana@gmail.com welcome")
        print("         python3 send_test_emails.py kyra.atekwana@gmail.com all")
        sys.exit(1)

    email = sys.argv[1]
    email_type = sys.argv[2] if len(sys.argv) > 2 else "all"

    print("=" * 50)
    print("DETTY FLIGHT DEALS - TEST EMAILS")
    print("=" * 50)
    print(f"Target: {email}")
    print(f"Type: {email_type}")

    # Check SMTP credentials
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        print("\n❌ SMTP credentials not set!")
        print("   Set SMTP_EMAIL and SMTP_PASSWORD environment variables.")
        print("\n   Or run via GitHub Actions which has the secrets configured.")
        sys.exit(1)

    results = {}

    if email_type in ["all", "wow"]:
        results["WOW Alert"] = send_test_wow_alert(email)

    if email_type in ["all", "digest"]:
        results["Weekly Digest"] = send_test_digest(email)

    if email_type in ["all", "welcome"]:
        results["Welcome"] = send_test_welcome(email)

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)
    for name, success in results.items():
        print(f"{name:15} {'✅ Sent' if success else '❌ Failed'}")

    if all(results.values()):
        print("\n✅ All test emails sent! Check your inbox.")
    else:
        print("\n⚠️ Some emails failed. Check the errors above.")


if __name__ == "__main__":
    main()
