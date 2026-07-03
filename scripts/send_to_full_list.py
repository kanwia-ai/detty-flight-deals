"""
Resend today's deals to the FULL subscriber list, bypassing every warm-up /
catch-up gate. Manual tool — run via the "Resend Today's Deals" workflow.

Rebuilds the deal dicts from committed state (seen_deals.json entries touched
today + matching price_history.jsonl rows), regenerates the same email the
daily run built, and sends it to every Google Sheet subscriber.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from deal_finder import (  # noqa: E402
    DESTINATIONS, build_email_content, classify_deal, in_detty_window,
)
from mvp0_sender import get_subscribers, send_to_subscriber  # noqa: E402

ROOT = Path(__file__).parent.parent
SEEN_DEALS_FILE = ROOT / "seen_deals.json"
PRICE_HISTORY_FILE = ROOT / "price_history.jsonl"

TIER_LABELS = {"wow": "WOW", "great": "Great", "good": "Good"}


def parse_key(key: str):
    """'JFK-LOS-good-detty-2026' -> (JFK, LOS, good, detty-2026)."""
    parts = key.split("-")
    return parts[0], parts[1], parts[2], "-".join(parts[3:])


def load_today_history() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    with open(PRICE_HISTORY_FILE) as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("searched_at", "").startswith(today):
                rows.append(row)
    return rows


def rebuild_deals() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    with open(SEEN_DEALS_FILE) as f:
        seen = json.load(f)
    history = load_today_history()

    deals = []
    for key, entry in seen.items():
        if entry.get("last_seen") != today:
            continue
        origin, dest, tier, bucket = parse_key(key)
        want_detty = bucket.startswith("detty")

        # Find today's history row matching route + price + season bucket
        match = None
        for row in history:
            if row["origin"] != origin or row["destination"] != dest:
                continue
            if row["price"] != entry["price"]:
                continue
            dt = datetime.strptime(row["travel_date"], "%Y-%m-%d")
            if in_detty_window(dt) == want_detty:
                match = row
                break
        if not match:
            print(f"  ⚠️ no history row for {key} (${entry['price']}) — skipping")
            continue

        travel_dt = datetime.strptime(match["travel_date"], "%Y-%m-%d")
        classification = classify_deal(entry["price"], dest, travel_dt) or {
            "tier": tier,
            "label": TIER_LABELS.get(tier, "Deal"),
            "normal_price": DESTINATIONS.get(dest, {}).get("normal", 1200),
        }
        deals.append({
            "origin": origin,
            "dest": dest,
            "dest_name": entry.get("dest_name", dest),
            "region": DESTINATIONS.get(dest, {}).get("region", "West Africa"),
            "price": entry["price"],
            "tier": tier,
            "label": classification["label"],
            "normal_price": classification["normal_price"],
            "departure": match["travel_date"],
            "return": match["return_date"],
            "url": (
                f"https://www.google.com/travel/flights?"
                f"q=Flights%20from%20{origin}%20to%20{dest}%20"
                f"departing%20{match['travel_date']}%20returning%20{match['return_date']}&curr=USD"
            ),
        })
    return deals


def main():
    deals = rebuild_deals()
    if not deals:
        print("No deals recorded today — nothing to resend.")
        sys.exit(1)

    print(f"Rebuilt {len(deals)} deals from today's state")
    subject, plain_body, html_body = build_email_content(deals)
    print(f"Subject: {subject}")

    subscribers = get_subscribers()
    if not subscribers:
        print("❌ No subscribers loaded — aborting")
        sys.exit(1)

    print(f"\n📧 Sending to FULL list: {len(subscribers)} subscribers")
    sent = 0
    for i, email in enumerate(subscribers, 1):
        if send_to_subscriber(email, subject, html_body, plain_body):
            sent += 1
            print(f"  ✓ [{i}/{len(subscribers)}] {email}")
        else:
            print(f"  ✗ [{i}/{len(subscribers)}] {email}")
        if i < len(subscribers):
            time.sleep(0.5)

    print(f"\nDone: {sent}/{len(subscribers)} delivered")
    if sent == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
