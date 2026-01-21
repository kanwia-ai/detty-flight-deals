#!/usr/bin/env python3
"""
Send test emails to preview the deal alert format.

Usage:
    python3 send_test_emails.py <email_address>
    python3 send_test_emails.py kyra.atekwana@gmail.com
    python3 send_test_emails.py kyra.atekwana@gmail.com welcome
"""

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from deal_finder import build_email_content
from mvp0_sender import send_to_subscriber


# Sample deals for testing (below threshold)
SAMPLE_DEALS = [
    {
        "origin": "JFK",
        "dest": "LOS",
        "dest_name": "Lagos",
        "region": "West Africa",
        "price": 789,
        "threshold": 850,
        "departure": "2026-03-15",
        "return": "2026-03-25",
        "url": "https://www.google.com/travel/flights?q=Flights%20from%20JFK%20to%20LOS",
    },
    {
        "origin": "IAD",
        "dest": "LOS",
        "dest_name": "Lagos",
        "region": "West Africa",
        "price": 820,
        "threshold": 850,
        "departure": "2026-04-01",
        "return": "2026-04-11",
        "url": "https://www.google.com/travel/flights?q=Flights%20from%20IAD%20to%20LOS",
    },
    {
        "origin": "JFK",
        "dest": "ACC",
        "dest_name": "Accra",
        "region": "West Africa",
        "price": 695,
        "threshold": 800,
        "departure": "2026-03-20",
        "return": "2026-03-30",
        "url": "https://www.google.com/travel/flights?q=Flights%20from%20JFK%20to%20ACC",
    },
    {
        "origin": "ATL",
        "dest": "ACC",
        "dest_name": "Accra",
        "region": "West Africa",
        "price": 745,
        "threshold": 800,
        "departure": "2026-04-10",
        "return": "2026-04-20",
        "url": "https://www.google.com/travel/flights?q=Flights%20from%20ATL%20to%20ACC",
    },
    {
        "origin": "JFK",
        "dest": "DSS",
        "dest_name": "Dakar",
        "region": "West Africa",
        "price": 620,
        "threshold": 700,
        "departure": "2026-05-01",
        "return": "2026-05-11",
        "url": "https://www.google.com/travel/flights?q=Flights%20from%20JFK%20to%20DSS",
    },
]


def send_test_deal_alert(email: str) -> bool:
    """Send test deal alert email."""
    subject, plain, html = build_email_content(SAMPLE_DEALS)
    subject = f"[TEST] {subject}"  # Mark as test

    print(f"\n📧 Sending TEST Deal Alert to {email}...")
    print(f"   Subject: {subject}")

    return send_to_subscriber(email, subject, html, plain)


def send_test_welcome(email: str) -> bool:
    """Send test welcome email."""
    from mvp0_sender import build_welcome_html, build_welcome_plain

    subject = "[TEST] Welcome to Detty Flight Deals!"
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
        print("         python3 send_test_emails.py kyra.atekwana@gmail.com deal")
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

    if email_type in ["all", "deal"]:
        results["Deal Alert"] = send_test_deal_alert(email)

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
