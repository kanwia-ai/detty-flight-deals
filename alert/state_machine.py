"""
Detty Flight Deals - Alert State Machine

Finite State Machine (FSM) for tier-escalation alerts.

Tracks deal states per route to eliminate alert fatigue. Users only get
notified when a deal enters a NEW tier (NORMAL->Great, NORMAL->WOW,
Great->WOW), not for same-tier price fluctuations.

States:
    NORMAL          -> No active deal
    GREAT_ALERTING  -> Great deal detected, will alert
    GREAT_ALERTED   -> Great deal sent, awaiting reset or escalation
    WOW_ALERTING    -> WOW deal detected, will alert
    WOW_ALERTED     -> WOW deal sent, awaiting reset

Key behaviors:
    - Two tiers: Great (free) and WOW (premium)
    - "good" tier from anomaly detection maps to Great
    - Mistake fares always treated as WOW-level (premium content)
    - De-escalation is SILENT (no alert on WOW->Great or Great->Normal)
    - Escalation OVERRIDES (Great->WOW always alerts)
    - Reset after 3 consecutive normal prices
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AlertState(Enum):
    """FSM states for route-level deal tracking."""

    NORMAL = auto()            # No active deal
    GREAT_ALERTING = auto()    # Great deal detected, will alert
    GREAT_ALERTED = auto()     # Great deal, already alerted
    WOW_ALERTING = auto()      # WOW deal detected, will alert
    WOW_ALERTED = auto()       # WOW deal, already alerted


@dataclass
class RouteState:
    """
    Current FSM state for a single route.

    Attributes:
        route: Route identifier e.g. "JFK-LOS"
        state: Current AlertState (default NORMAL)
        last_alert_tier: Tier of the last alert sent ("Great", "WOW", "MISTAKE")
        last_alert_price_cents: Price in cents when last alert was sent
        consecutive_normal: Count of consecutive normal prices (for reset logic)
    """

    route: str
    state: AlertState = AlertState.NORMAL
    last_alert_tier: Optional[str] = None
    last_alert_price_cents: Optional[int] = None
    consecutive_normal: int = 0


# Event types for FSM transitions
_EVENT_GREAT = "great_deal"
_EVENT_WOW = "wow_deal"
_EVENT_NORMAL = "normal_price"


class AlertStateMachine:
    """
    Finite State Machine for tier-escalation deal alerts.

    Tracks per-route deal state to prevent alert fatigue. Only alerts
    when a deal enters a NEW tier or escalates. De-escalation and
    same-tier price changes are silent.

    The FSM uses a transition table mapping (current_state, event) to
    (new_state, should_alert). States transition through ALERTING
    (transient) to ALERTED (stable) after an alert is sent.

    Args:
        db_client: Optional TursoClient for state persistence.
                   If None, state is stored in memory only.

    Example:
        fsm = AlertStateMachine(db_client=turso)
        should_alert, info = fsm.process("JFK-LOS", "great", 65000)
        if should_alert:
            send_alert(info)
    """

    RESET_THRESHOLD = 3  # Consecutive normal prices to reset cycle

    # Transition table: (current_state, event) -> (new_state, should_alert)
    # States flow: NORMAL -> *_ALERTING -> *_ALERTED
    # ALERTING is transient: process() immediately transitions to ALERTED after alerting
    TRANSITIONS: Dict[Tuple[AlertState, str], Tuple[AlertState, bool]] = {
        # From NORMAL: any deal triggers alert
        (AlertState.NORMAL, _EVENT_GREAT): (AlertState.GREAT_ALERTING, True),
        (AlertState.NORMAL, _EVENT_WOW): (AlertState.WOW_ALERTING, True),
        (AlertState.NORMAL, _EVENT_NORMAL): (AlertState.NORMAL, False),

        # From GREAT_ALERTED: same tier suppressed, escalation alerts
        (AlertState.GREAT_ALERTED, _EVENT_GREAT): (AlertState.GREAT_ALERTED, False),
        (AlertState.GREAT_ALERTED, _EVENT_WOW): (AlertState.WOW_ALERTING, True),
        # Normal prices: count toward reset (handled in _handle_normal)

        # From WOW_ALERTED: same tier suppressed, de-escalation silent
        (AlertState.WOW_ALERTED, _EVENT_WOW): (AlertState.WOW_ALERTED, False),
        (AlertState.WOW_ALERTED, _EVENT_GREAT): (AlertState.GREAT_ALERTED, False),
        # Normal prices: count toward reset (handled in _handle_normal)

        # From ALERTING states (transient, but handle if re-entered)
        (AlertState.GREAT_ALERTING, _EVENT_GREAT): (AlertState.GREAT_ALERTED, False),
        (AlertState.GREAT_ALERTING, _EVENT_WOW): (AlertState.WOW_ALERTING, True),
        (AlertState.GREAT_ALERTING, _EVENT_NORMAL): (AlertState.GREAT_ALERTED, False),
        (AlertState.WOW_ALERTING, _EVENT_WOW): (AlertState.WOW_ALERTED, False),
        (AlertState.WOW_ALERTING, _EVENT_GREAT): (AlertState.GREAT_ALERTED, False),
        (AlertState.WOW_ALERTING, _EVENT_NORMAL): (AlertState.WOW_ALERTED, False),
    }

    def __init__(self, db_client=None):
        """
        Initialize the Alert State Machine.

        Args:
            db_client: Optional TursoClient for persisting state to Turso.
                       If None, state is stored in an in-memory dict only.
        """
        self.db = db_client
        self._memory_states: Dict[str, RouteState] = {}

    def get_state(self, route: str) -> RouteState:
        """
        Get current FSM state for a route.

        Loads from database if db_client is available, falls back to
        in-memory storage, or returns a fresh NORMAL state.

        Args:
            route: Route identifier e.g. "JFK-LOS"

        Returns:
            RouteState for the given route
        """
        # Try database first
        if self.db is not None:
            record = self.db.get_alert_state(route)
            if record is not None:
                return self._dict_to_route_state(route, record)

        # Fall back to in-memory
        if route in self._memory_states:
            return self._memory_states[route]

        # New route: start at NORMAL
        return RouteState(route=route)

    def _save_state(self, state: RouteState) -> None:
        """
        Persist FSM state for a route.

        Writes to database if db_client is available, otherwise
        stores in the in-memory dict.

        Args:
            state: RouteState to persist
        """
        if self.db is not None:
            self.db.update_alert_state(
                route=state.route,
                current_tier=state.state.name,
                consecutive_normal_count=state.consecutive_normal,
                last_alert_tier=state.last_alert_tier,
                last_alert_price_cents=state.last_alert_price_cents,
            )
        else:
            self._memory_states[state.route] = state

    def process(
        self,
        route: str,
        deal_tier: Optional[str],
        price_cents: int,
        is_mistake_fare: bool = False,
        normal_price_cents: Optional[int] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Process a price observation through the FSM.

        Maps the deal tier to an FSM event, looks up the transition,
        and returns whether an alert should be sent.

        Args:
            route: Route identifier e.g. "JFK-LOS"
            deal_tier: Tier from anomaly detection ("good", "great", "wow") or None for normal
            price_cents: Current price in cents
            is_mistake_fare: If True, always treated as WOW-level (premium content)
            normal_price_cents: Baseline normal price for context (optional)

        Returns:
            Tuple of (should_alert: bool, alert_info: Optional[dict])
            alert_info contains: tier, tier_emoji, price_cents, is_escalation,
            is_mistake_fare, previous_tier, normal_price_cents
        """
        state = self.get_state(route)
        event = self._classify_event(deal_tier, is_mistake_fare)

        logger.debug(
            f"[FSM] {route}: state={state.state.name}, event={event}, "
            f"price={price_cents}, tier={deal_tier}, mistake={is_mistake_fare}"
        )

        # Handle normal prices separately (consecutive count logic)
        if event == _EVENT_NORMAL:
            return self._handle_normal(state, price_cents)

        # Reset consecutive normal count on any deal
        state.consecutive_normal = 0

        # Look up transition
        transition_key = (state.state, event)
        if transition_key not in self.TRANSITIONS:
            logger.warning(
                f"[FSM] No transition for ({state.state.name}, {event}), "
                f"staying in {state.state.name}"
            )
            self._save_state(state)
            return False, None

        new_state, should_alert = self.TRANSITIONS[transition_key]
        previous_tier = state.last_alert_tier
        is_escalation = (
            previous_tier is not None
            and should_alert
            and state.state in (AlertState.GREAT_ALERTED, AlertState.GREAT_ALERTING)
            and event == _EVENT_WOW
        )

        # Determine display tier
        display_tier = self._get_display_tier(deal_tier, is_mistake_fare)

        # Update state
        state.state = new_state

        if should_alert:
            # Transition through ALERTING -> ALERTED
            if new_state == AlertState.GREAT_ALERTING:
                state.state = AlertState.GREAT_ALERTED
            elif new_state == AlertState.WOW_ALERTING:
                state.state = AlertState.WOW_ALERTED

            # Record alert details
            state.last_alert_tier = display_tier
            state.last_alert_price_cents = price_cents

        self._save_state(state)

        if should_alert:
            alert_info = {
                "tier": display_tier,
                "tier_emoji": self._get_tier_emoji(display_tier, is_mistake_fare),
                "price_cents": price_cents,
                "is_escalation": is_escalation,
                "is_mistake_fare": is_mistake_fare,
                "previous_tier": previous_tier,
                "normal_price_cents": normal_price_cents,
            }
            logger.info(
                f"[FSM] {route}: ALERT {display_tier} "
                f"({'escalation' if is_escalation else 'new'}) "
                f"at {price_cents} cents"
            )
            return True, alert_info

        logger.debug(f"[FSM] {route}: no alert (state={state.state.name})")
        return False, None

    def _handle_normal(
        self, state: RouteState, price_cents: int
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Handle a normal price observation.

        Increments consecutive normal counter. After RESET_THRESHOLD
        consecutive normal prices, resets the FSM to NORMAL state.

        De-escalation is always silent (no alert sent).

        Args:
            state: Current RouteState
            price_cents: Current price in cents

        Returns:
            Always (False, None) -- normal prices never trigger alerts
        """
        if state.state == AlertState.NORMAL:
            # Already normal, just save and return
            self._save_state(state)
            return False, None

        # In an alerted state: count toward reset
        state.consecutive_normal += 1
        logger.debug(
            f"[FSM] {state.route}: normal #{state.consecutive_normal}/{self.RESET_THRESHOLD}"
        )

        if state.consecutive_normal >= self.RESET_THRESHOLD:
            logger.info(
                f"[FSM] {state.route}: RESET to NORMAL after "
                f"{self.RESET_THRESHOLD} consecutive normal prices"
            )
            state.state = AlertState.NORMAL
            state.consecutive_normal = 0
            state.last_alert_tier = None
            state.last_alert_price_cents = None

        self._save_state(state)
        return False, None

    @staticmethod
    def _classify_event(
        deal_tier: Optional[str], is_mistake_fare: bool
    ) -> str:
        """
        Map deal tier and mistake fare flag to an FSM event.

        Tier mapping:
            - "good" or "great" -> great_deal event
            - "wow" -> wow_deal event
            - is_mistake_fare=True -> wow_deal event (always premium)
            - None or unrecognized -> normal_price event

        Args:
            deal_tier: Tier from anomaly detection or None
            is_mistake_fare: Whether this is a mistake fare

        Returns:
            FSM event string (_EVENT_GREAT, _EVENT_WOW, or _EVENT_NORMAL)
        """
        # Mistake fares always treated as WOW-level
        if is_mistake_fare:
            return _EVENT_WOW

        if deal_tier is None:
            return _EVENT_NORMAL

        tier_lower = deal_tier.lower()

        # "good" from anomaly detection maps to Great tier
        if tier_lower in ("good", "great"):
            return _EVENT_GREAT
        elif tier_lower == "wow":
            return _EVENT_WOW
        else:
            logger.warning(f"[FSM] Unknown deal tier '{deal_tier}', treating as normal")
            return _EVENT_NORMAL

    @staticmethod
    def _get_display_tier(
        deal_tier: Optional[str], is_mistake_fare: bool
    ) -> str:
        """
        Get the display tier name for alerts.

        Args:
            deal_tier: Tier from anomaly detection
            is_mistake_fare: Whether this is a mistake fare

        Returns:
            Display tier: "MISTAKE", "WOW", or "Great"
        """
        if is_mistake_fare:
            return "MISTAKE"

        if deal_tier is None:
            return "Great"  # Shouldn't happen in alert path, but safe default

        tier_lower = deal_tier.lower()
        if tier_lower == "wow":
            return "WOW"
        else:
            return "Great"

    @staticmethod
    def _get_tier_emoji(tier: str, is_mistake_fare: bool) -> str:
        """
        Get text-compatible tier indicator for email subjects.

        Per RESEARCH.md: text-compatible indicators that work in
        email subject lines across all clients.

        Args:
            tier: Display tier name ("Great", "WOW", "MISTAKE")
            is_mistake_fare: Whether this is a mistake fare

        Returns:
            Tier emoji string: "*" for Great, "**" for WOW, "!!" for Mistake
        """
        if is_mistake_fare or tier == "MISTAKE":
            return "!!"
        elif tier == "WOW":
            return "**"
        else:
            return "*"

    @staticmethod
    def _dict_to_route_state(route: str, record: dict) -> RouteState:
        """
        Convert a database record dict to a RouteState dataclass.

        Handles missing or None values gracefully for backward
        compatibility with pre-Phase-4 records.

        Args:
            route: Route identifier
            record: Dict from TursoClient.get_alert_state()

        Returns:
            RouteState populated from database record
        """
        # Parse state from stored name, default to NORMAL
        state_name = record.get("current_tier")
        try:
            state = AlertState[state_name] if state_name else AlertState.NORMAL
        except KeyError:
            logger.warning(
                f"[FSM] Unknown state '{state_name}' for {route}, resetting to NORMAL"
            )
            state = AlertState.NORMAL

        return RouteState(
            route=route,
            state=state,
            last_alert_tier=record.get("last_alert_tier"),
            last_alert_price_cents=record.get("last_alert_price_cents"),
            consecutive_normal=record.get("consecutive_normal_count", 0) or 0,
        )
