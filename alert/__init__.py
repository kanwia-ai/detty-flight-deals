"""
Detty Flight Deals - Alert Package
Alert state machine for tier-escalation deal notifications.

Eliminates alert fatigue by tracking deal states per route.
Users only get notified when a deal enters a NEW tier
(NORMAL->Great, NORMAL->WOW, Great->WOW), not for same-tier
price fluctuations.
"""

from .state_machine import AlertState, RouteState, AlertStateMachine
from .templates import (
    format_alert_subject,
    format_escalation_body,
    format_mistake_fare_alert,
    get_tier_label,
    TIER_EMOJIS,
    MISTAKE_FARE_URGENCY,
)

__all__ = [
    "AlertState",
    "RouteState",
    "AlertStateMachine",
    "format_alert_subject",
    "format_escalation_body",
    "format_mistake_fare_alert",
    "get_tier_label",
    "TIER_EMOJIS",
    "MISTAKE_FARE_URGENCY",
]
