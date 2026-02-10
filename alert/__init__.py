"""
Detty Flight Deals - Alert Package
Alert state machine for tier-escalation deal notifications.

Eliminates alert fatigue by tracking deal states per route.
Users only get notified when a deal enters a NEW tier
(NORMAL->Great, NORMAL->WOW, Great->WOW), not for same-tier
price fluctuations.
"""

from .state_machine import AlertState, RouteState, AlertStateMachine

__all__ = ["AlertState", "RouteState", "AlertStateMachine"]
