"""
Detty Flight Deals - Subscriber Package
Metro group mappings, subscriber management, trial lifecycle, alert routing,
SMS alerts, digest generation, payment reminders, and migration utilities.
"""

from .metro_groups import METRO_GROUPS, AIRPORT_TO_METRO, DEST_REGIONS
from .manager import SubscriberManager
from .trial import start_trial, check_trial_expiry, expire_all_trials, is_trial_active
from .digest import generate_digest, send_weekly_digests
from .reminders import send_payment_reminders
from .migration import migrate_from_sheets
from .router import AlertRouter
from .sms import send_sms_alert

__all__ = [
    "METRO_GROUPS",
    "AIRPORT_TO_METRO",
    "DEST_REGIONS",
    "SubscriberManager",
    "start_trial",
    "check_trial_expiry",
    "expire_all_trials",
    "is_trial_active",
    "generate_digest",
    "send_weekly_digests",
    "send_payment_reminders",
    "migrate_from_sheets",
    "AlertRouter",
    "send_sms_alert",
]
