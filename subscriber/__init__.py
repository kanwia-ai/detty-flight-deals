"""
Detty Flight Deals - Subscriber Package
Metro group mappings, subscriber management, trial lifecycle, and migration utilities.
"""

from .metro_groups import METRO_GROUPS, AIRPORT_TO_METRO, DEST_REGIONS
from .manager import SubscriberManager
from .trial import start_trial, check_trial_expiry, expire_all_trials, is_trial_active
from .migration import migrate_from_sheets

__all__ = [
    "METRO_GROUPS",
    "AIRPORT_TO_METRO",
    "DEST_REGIONS",
    "SubscriberManager",
    "start_trial",
    "check_trial_expiry",
    "expire_all_trials",
    "is_trial_active",
    "migrate_from_sheets",
]
