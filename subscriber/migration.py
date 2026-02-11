"""
Detty Flight Deals - Google Sheets to Turso Migration
One-time idempotent migration of subscriber emails from Google Sheets to Turso.

Uses INSERT OR IGNORE to handle duplicates safely. Running this script
multiple times is safe -- existing subscribers are skipped.

Existing Google Sheets subscribers are migrated as free tier WITHOUT
auto-trial (only new signups get 7-day trials per FRML-04).

Usage:
    python -m subscriber.migration
"""

import logging
import sys

logger = logging.getLogger(__name__)


def migrate_from_sheets() -> dict:
    """
    Migrate subscriber emails from Google Sheets to Turso database.

    Reads emails from the existing Google Sheets subscriber list
    (via mvp0_sender.get_subscribers) and inserts each as a free-tier
    subscriber in Turso. Uses INSERT OR IGNORE for idempotency.

    Existing subscribers (those already in Turso) are skipped silently.
    Migrated subscribers do NOT get auto-trial (start_trial=False)
    because they are existing users, not new signups.

    Returns:
        Dict with migration results:
            - migrated: count of newly inserted subscribers
            - skipped: count of emails already in Turso
            - total: total active subscribers in Turso after migration
            - errors: count of errors during migration
    """
    # Import Google Sheets reader with graceful fallback
    try:
        from mvp0_sender import get_subscribers
    except ImportError as e:
        logger.error(
            f"[Migration] Cannot import mvp0_sender: {e}. "
            "Make sure gspread and google-auth are installed."
        )
        return {"migrated": 0, "skipped": 0, "total": 0, "errors": 1}

    # Initialize database client and manager
    from db.client import TursoClient
    from subscriber.manager import SubscriberManager

    db = TursoClient()
    if not db._turso_available:
        logger.error(
            "[Migration] Turso not available. Set TURSO_DATABASE_URL and "
            "TURSO_AUTH_TOKEN environment variables."
        )
        return {"migrated": 0, "skipped": 0, "total": 0, "errors": 1}

    manager = SubscriberManager(db)

    # Read emails from Google Sheets
    logger.info("[Migration] Reading subscribers from Google Sheets...")
    emails = get_subscribers()

    if not emails:
        logger.warning("[Migration] No subscribers found in Google Sheets")
        return {"migrated": 0, "skipped": 0, "total": 0, "errors": 0}

    logger.info(f"[Migration] Found {len(emails)} emails in Google Sheets")

    # Migrate each subscriber
    migrated = 0
    skipped = 0
    errors = 0

    for email in emails:
        try:
            # Check if subscriber already exists in Turso
            existing = manager.get_by_email(email)
            if existing:
                skipped += 1
                continue

            # Add as free tier, NO auto-trial for existing users
            result = manager.add(
                email=email,
                tier="free",
                start_trial=False,
            )

            if result:
                migrated += 1
                logger.debug(f"[Migration] Migrated: {email}")
            else:
                # INSERT OR IGNORE means this could be a dupe we missed
                skipped += 1

        except Exception as e:
            logger.error(f"[Migration] Error migrating {email}: {e}")
            errors += 1

    # Get total count after migration
    total_subscribers = len(manager.get_all_active())

    summary = {
        "migrated": migrated,
        "skipped": skipped,
        "total": total_subscribers,
        "errors": errors,
    }

    logger.info(
        f"[Migration] Complete. "
        f"Migrated: {migrated}, Skipped: {skipped}, "
        f"Errors: {errors}, Total in Turso: {total_subscribers}"
    )

    return summary


if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    print("Detty Flight Deals - Google Sheets to Turso Migration")
    print("=" * 55)

    results = migrate_from_sheets()

    print(f"\nResults:")
    print(f"  Migrated: {results['migrated']}")
    print(f"  Skipped:  {results['skipped']}")
    print(f"  Errors:   {results['errors']}")
    print(f"  Total:    {results['total']}")

    # Exit with error code if there were errors
    if results["errors"] > 0:
        sys.exit(1)
