"""
Detty Flight Deals - Subscriber Package
Metro group mappings, subscriber management, and filtering utilities.
"""

from .metro_groups import METRO_GROUPS, AIRPORT_TO_METRO, DEST_REGIONS
from .manager import SubscriberManager

__all__ = [
    "METRO_GROUPS",
    "AIRPORT_TO_METRO",
    "DEST_REGIONS",
    "SubscriberManager",
]
