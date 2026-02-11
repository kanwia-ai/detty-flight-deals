"""
Detty Flight Deals - Trial Management
7-day premium trial lifecycle: start, check expiry, bulk expire, active check.

Trial flow:
  1. New subscriber signs up -> start_trial() sets tier="trial" for 7 days
  2. During routing, expire_all_trials() checks and downgrades expired trials
  3. is_trial_active() used for instant checks on a subscriber dict

Usage:
    from subscriber.trial import start_trial, check_trial_expiry, is_trial_active

    start_trial(manager, "user@example.com")
    expired = check_trial_expiry(manager, "user@example.com")
    active = is_trial_active(subscriber_dict)
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def start_trial(manager, email: str) -> bool:
    """
    Start a 7-day premium trial for a subscriber.

    Sets tier to "trial" with trial_start and trial_expiry timestamps.
    Trial subscribers get premium-level access (instant alerts, multiple
    metros) for 7 days.

    Args:
        manager: SubscriberManager instance (or any object with db attribute).
        email: Subscriber email address.

    Returns:
        True if trial started successfully, False otherwise.
    """
    now = datetime.now()
    trial_expiry = now + timedelta(days=7)

    result = manager.db.update_subscriber(
        email,
        tier="trial",
        trial_start=now.isoformat(),
        trial_expiry=trial_expiry.isoformat(),
    )

    if result:
        logger.info(
            f"[TRIAL] Started 7-day trial for {email}, "
            f"expires {trial_expiry.isoformat()}"
        )
    else:
        logger.error(f"[TRIAL] Failed to start trial for {email}")

    return result


def check_trial_expiry(manager, email: str) -> bool:
    """
    Check if a subscriber's trial has expired and downgrade if so.

    If the trial has expired (trial_expiry <= now), downgrades the
    subscriber to free tier and clears trial fields.

    Args:
        manager: SubscriberManager instance.
        email: Subscriber email address.

    Returns:
        True if trial was expired and subscriber was downgraded.
        False if trial is still active, subscriber not found, or not on trial.
    """
    subscriber = manager.get_by_email(email)
    if subscriber is None:
        return False

    if subscriber.get("tier") != "trial":
        return False

    trial_expiry = subscriber.get("trial_expiry")
    if trial_expiry is None:
        return False

    try:
        expiry_dt = datetime.fromisoformat(trial_expiry)
    except (ValueError, TypeError):
        logger.warning(
            f"[TRIAL] Invalid trial_expiry for {email}: {trial_expiry}"
        )
        return False

    if expiry_dt <= datetime.now():
        # Trial expired -- downgrade to free
        result = manager.db.update_subscriber(
            email,
            tier="free",
            trial_start=None,
            trial_expiry=None,
        )
        if result:
            logger.info(
                f"[TRIAL] Expired trial for {email}, downgraded to free"
            )
        return result

    return False


def expire_all_trials(manager) -> int:
    """
    Check all trial subscribers and expire those past their trial_expiry.

    Called lazily during deal routing (not on a separate cron).
    Iterates through all active trial subscribers and downgrades
    any whose trial has expired.

    Args:
        manager: SubscriberManager instance.

    Returns:
        Count of expired trials that were downgraded.
    """
    trial_subscribers = manager.get_all_active(tier="trial")
    expired_count = 0

    for subscriber in trial_subscribers:
        email = subscriber.get("email")
        if email and check_trial_expiry(manager, email):
            expired_count += 1

    if expired_count > 0:
        logger.info(
            f"[TRIAL] Expired {expired_count} trial(s) out of "
            f"{len(trial_subscribers)} active trial subscribers"
        )

    return expired_count


def is_trial_active(subscriber: dict) -> bool:
    """
    Check if a subscriber's trial is currently active.

    Pure function that checks the subscriber dict without database access.
    Used for fast inline checks during routing.

    Args:
        subscriber: Subscriber dict with 'tier' and 'trial_expiry' fields.

    Returns:
        True if subscriber is on trial tier and trial has not expired.
        False otherwise.
    """
    if subscriber.get("tier") != "trial":
        return False

    trial_expiry = subscriber.get("trial_expiry")
    if trial_expiry is None:
        return False

    try:
        expiry_dt = datetime.fromisoformat(trial_expiry)
        return expiry_dt > datetime.now()
    except (ValueError, TypeError):
        return False
