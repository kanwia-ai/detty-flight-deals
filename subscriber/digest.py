"""
Detty Flight Deals - Weekly Digest Generation

Generates and sends personalized weekly digest emails for free subscribers.
Each digest includes metro-filtered Great deals and 2-3 FOMO teasers of
WOW/mistake fares that free users missed.

Pipeline:
  1. Expire any overdue trials (lazy check per RESEARCH.md pitfall #2)
  2. Fetch pending deals from digest_queue (max 7 days old)
  3. For each free subscriber:
     a. Filter Great deals by subscriber's metro group
     b. Select 2-3 random WOW/mistake deals as FOMO teasers
     c. Build personalized HTML + plain text email
     d. Send via Gmail SMTP
  4. Mark all pending deals as sent in digest_queue

Usage:
    python -m subscriber.digest

    Called by the weekly_digest.yml GitHub Actions workflow (Plan 05).
"""

import json
import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)


# ==========================================================
# CONSTANTS
# ==========================================================

MAX_DIGEST_DEALS = 15   # Cap per subscriber email (prevents unbounded growth)
MAX_FOMO_TEASERS = 3    # FOMO teaser count per CONTEXT.md
MAX_AGE_DAYS = 7        # Only include deals from past 7 days
GMAIL_DAILY_LIMIT = 90  # Safety cap (Gmail hard limit is 100/day)


# ==========================================================
# DIGEST GENERATION
# ==========================================================

def generate_digest(db_client, subscriber: dict) -> Optional[dict]:
    """
    Generate a personalized digest for a single subscriber.

    Fetches pending deals from the digest queue, filters by the
    subscriber's metro preference, caps at MAX_DIGEST_DEALS, and
    selects random FOMO teasers from WOW/mistake fares.

    Args:
        db_client: TursoClient instance with get_pending_digest_deals().
        subscriber: Subscriber dict with at least 'email', 'name',
                    'metro_group', and 'tier' fields.

    Returns:
        Dict with {subject, html_body, plain_body, deal_count, teaser_count}
        or None if no content for this subscriber.
    """
    from subscriber.metro_groups import airport_matches_subscriber
    from alert.templates import (
        build_weekly_digest_html,
        build_weekly_digest_plain,
        build_weekly_digest_subject,
    )

    # Get pending deals from digest queue
    deals = db_client.get_pending_digest_deals(max_age_days=MAX_AGE_DAYS)
    if not deals:
        return None

    # Separate deals by type
    great_deals = [
        d for d in deals
        if d.get("tier", "").lower() in ("great", "good")
        and d.get("expired", 0) == 0
    ]
    teaser_deals = [
        d for d in deals
        if d.get("tier", "").lower() in ("wow", "mistake")
        or d.get("expired", 0) == 1
    ]

    # Filter great deals by subscriber metro preference
    filtered_great = [
        d for d in great_deals
        if airport_matches_subscriber(d.get("origin", ""), subscriber)
    ]

    # Cap at MAX_DIGEST_DEALS
    filtered_great = filtered_great[:MAX_DIGEST_DEALS]

    # Select random FOMO teasers
    selected_teasers = random.sample(
        teaser_deals, min(MAX_FOMO_TEASERS, len(teaser_deals))
    ) if teaser_deals else []

    # Nothing for this subscriber
    if not filtered_great and not selected_teasers:
        return None

    # Subscriber info
    name = subscriber.get("name", "")
    metro = subscriber.get("metro_group", "your area")

    # Build email content
    best_dest = None
    best_price = None
    if filtered_great:
        first = filtered_great[0]
        best_dest = first.get("dest_name")
        price_cents = first.get("price_cents", 0)
        best_price = price_cents // 100 if price_cents else None

    subject = build_weekly_digest_subject(
        deal_count=len(filtered_great),
        best_dest=best_dest,
        best_price=best_price,
    )
    html_body = build_weekly_digest_html(name, filtered_great, selected_teasers, metro)
    plain_body = build_weekly_digest_plain(name, filtered_great, selected_teasers, metro)

    return {
        "subject": subject,
        "html_body": html_body,
        "plain_body": plain_body,
        "deal_count": len(filtered_great),
        "teaser_count": len(selected_teasers),
    }


# ==========================================================
# SEND PIPELINE
# ==========================================================

def send_weekly_digests() -> dict:
    """
    Main entry point: generate and send weekly digests to all free subscribers.

    Pipeline steps:
      1. Initialize database connection
      2. Expire overdue trials (lazy check)
      3. Get all free-tier subscribers
      4. Generate personalized digest per subscriber
      5. Send via Gmail SMTP with 90/day safety cap
      6. Mark digest queue deals as sent

    Returns:
        Summary dict with {subscribers_sent, subscribers_skipped,
        total_deals, total_teasers, errors}.
    """
    from db.client import TursoClient
    from subscriber.manager import SubscriberManager
    from subscriber.trial import expire_all_trials

    print("=" * 50)
    print("DETTY WEEKLY DIGEST")
    print("=" * 50)

    # Initialize database
    db = TursoClient()
    if not db._turso_available:
        print("[DIGEST] ERROR: Turso database not available. Cannot generate digests.")
        return {
            "subscribers_sent": 0,
            "subscribers_skipped": 0,
            "total_deals": 0,
            "total_teasers": 0,
            "errors": 0,
        }

    # Expire overdue trials (lazy check per RESEARCH.md pitfall #2)
    manager = SubscriberManager(db)
    expired = expire_all_trials(manager)
    if expired:
        print(f"  Expired {expired} trial(s)")

    # Get free tier subscribers
    free_subs = db.get_active_subscribers(tier="free")
    print(f"Generating digests for {len(free_subs)} free subscriber(s)...")

    if not free_subs:
        print("  No free subscribers found. Nothing to send.")
        return {
            "subscribers_sent": 0,
            "subscribers_skipped": 0,
            "total_deals": 0,
            "total_teasers": 0,
            "errors": 0,
        }

    # Import sender
    try:
        from mvp0_sender import send_to_subscriber
    except ImportError:
        print("[DIGEST] ERROR: mvp0_sender not available. Cannot send emails.")
        return {
            "subscribers_sent": 0,
            "subscribers_skipped": len(free_subs),
            "total_deals": 0,
            "total_teasers": 0,
            "errors": 1,
        }

    # Track metrics
    sent = 0
    skipped = 0
    errors = 0
    email_count = 0
    total_deals = 0
    total_teasers = 0

    for i, subscriber in enumerate(free_subs, 1):
        email = subscriber.get("email", "unknown")

        # Generate personalized digest
        digest = generate_digest(db, subscriber)
        if digest is None:
            skipped += 1
            logger.debug(f"  [{i}] {email}: no content, skipped")
            continue

        # Gmail safety limit (SUBS-05)
        if email_count >= GMAIL_DAILY_LIMIT:
            print(
                f"  WARNING: Gmail daily limit ({GMAIL_DAILY_LIMIT}) approaching, "
                f"stopping sends. {len(free_subs) - i} subscribers not sent."
            )
            skipped += len(free_subs) - i
            break

        # Send email
        print(f"  [{i}/{len(free_subs)}] {email}...", end=" ")
        success = send_to_subscriber(
            email, digest["subject"], digest["html_body"], digest["plain_body"]
        )

        if success:
            sent += 1
            email_count += 1
            total_deals += digest["deal_count"]
            total_teasers += digest["teaser_count"]
            print(f"OK ({digest['deal_count']} deals, {digest['teaser_count']} teasers)")
        else:
            errors += 1
            print("FAILED")

        # Delay between sends (match mvp0_sender pattern)
        time.sleep(0.5)

    # Mark all pending deals as sent (prevents re-sending next week)
    all_pending = db.get_pending_digest_deals(max_age_days=MAX_AGE_DAYS)
    deal_ids = [d["id"] for d in all_pending if "id" in d]
    if deal_ids:
        db.mark_digest_deals_sent(deal_ids)
        print(f"  Marked {len(deal_ids)} deal(s) as sent in digest_queue")

    # Summary
    summary = {
        "subscribers_sent": sent,
        "subscribers_skipped": skipped,
        "total_deals": total_deals,
        "total_teasers": total_teasers,
        "errors": errors,
    }

    print()
    print(f"Digest Summary:")
    print(f"  Sent: {sent}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total deals included: {total_deals}")
    print(f"  Total FOMO teasers included: {total_teasers}")

    return summary


# ==========================================================
# CLI ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    result = send_weekly_digests()
    print(f"\nDigest Result: {result}")
