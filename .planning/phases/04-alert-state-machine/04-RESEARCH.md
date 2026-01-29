# Phase 4: Alert State Machine - Research

**Researched:** 2026-01-28
**Domain:** Finite state machine design, alert deduplication, cooldown/throttling patterns
**Confidence:** HIGH (well-understood design patterns, simple custom implementation preferred)

## Summary

This phase implements a tier-escalation finite state machine to eliminate alert fatigue. Users only get notified on meaningful tier transitions (entering Great or WOW), not minor price fluctuations. The FSM persists state per route in Turso and enforces cooldowns to prevent spam.

Research confirms that a **simple custom FSM using Python Enum and dataclass** is the recommended approach over external libraries. The existing `alert_state` table schema (already created in Phase 2) provides the foundation for persistence. The key insight is that "once per deal window" cooldown is simpler than time-based cooldown tiers -- alert once when a deal appears, only re-alert if it escalates to a better tier.

The two-tier model (Great for free, WOW for premium) simplifies the state machine significantly compared to the original three-tier design. Mistake fares are flagged separately and always route to premium. The FSM needs to track: current tier, whether we've alerted at this tier, and consecutive normal price count for cycle reset.

**Primary recommendation:** Implement a custom FSM with Enum states and simple transition logic. No external FSM library needed -- the state space is small (4 states: NORMAL, GREAT_ALERTING, WOW_ALERTING, GREAT_ALERTED) and transitions are straightforward. Persist state via existing `alert_state` table with schema extension for `last_alerted_tier` and `last_alert_price`.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python Enum | stdlib | State definitions | Type-safe, no dependencies |
| Python dataclass | stdlib | FSM state holder | Clean serialization, immutable by default |
| Turso/libsql | existing | State persistence | Already integrated in Phase 2 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime | stdlib | Cooldown expiry timestamps | ISO format string storage |
| typing | stdlib | Type hints for FSM | Code clarity and IDE support |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom Enum FSM | `python-statemachine` 2.5.0 | Library is powerful but overkill for 4 states; adds dependency |
| Custom Enum FSM | `transitions` 0.9.0 | Same concern -- more complexity than needed for simple state space |
| Turso persistence | JSON file | Turso already set up, JSON was migrated away in Phase 2 |

**Installation:**
```bash
# No new packages needed -- all stdlib + existing dependencies
# Turso client already available from Phase 2
```

## Architecture Patterns

### Recommended Project Structure
```
detty-flight-deals/
├── alert/
│   ├── __init__.py           # Export AlertStateMachine, AlertState
│   ├── state_machine.py      # FSM implementation
│   └── templates.py          # Email template helpers for tier labels
├── db/
│   └── schema.py             # Schema extension (add columns)
│   └── client.py             # update_alert_state enhancement
├── deal_finder.py            # Modified to use AlertStateMachine
└── anomaly/                   # Existing - provides tier classification
```

### Pattern 1: Enum-Based State Machine
**What:** Define states as Enum, transitions as methods
**When to use:** Small state space (<10 states), simple transitions
**Why:** No external dependencies, easy to test, transparent logic

**Example:**
```python
# Source: Python stdlib Enum documentation, FSM design patterns
from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

class AlertState(Enum):
    """Possible states in the alert FSM."""
    NORMAL = auto()           # No active deal
    GREAT_ALERTING = auto()   # Great deal detected, will alert
    GREAT_ALERTED = auto()    # Great deal, already alerted
    WOW_ALERTING = auto()     # WOW deal detected, will alert
    WOW_ALERTED = auto()      # WOW deal, already alerted


@dataclass
class RouteAlertState:
    """Persisted state for a single route."""
    route: str
    state: AlertState
    last_alert_tier: Optional[str] = None
    last_alert_price: Optional[int] = None  # cents
    consecutive_normal_count: int = 0

    def to_db_dict(self) -> dict:
        """Serialize for database storage."""
        return {
            "route": self.route,
            "current_tier": self.state.name,
            "cooldown_expiry": None,  # Replaced by "once per deal" logic
            "consecutive_normal_count": self.consecutive_normal_count,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "RouteAlertState":
        """Deserialize from database."""
        state_name = row.get("current_tier") or "NORMAL"
        try:
            state = AlertState[state_name]
        except KeyError:
            state = AlertState.NORMAL

        return cls(
            route=row["route"],
            state=state,
            consecutive_normal_count=row.get("consecutive_normal_count", 0),
        )
```

### Pattern 2: Transition Table with Guards
**What:** Define allowed transitions declaratively, validate with guards
**When to use:** Clear audit trail of what transitions are allowed
**Why:** Easy to verify correctness, self-documenting

**Example:**
```python
# Source: State machine design pattern best practices
class AlertStateMachine:
    """
    FSM for alert tier transitions.

    Key rules (from CONTEXT.md):
    - Two tiers: Great (free) and WOW (premium)
    - Alert once when deal appears at a tier
    - Escalation (Great->WOW) triggers new alert immediately
    - De-escalation is silent (no alert)
    - Reset after N consecutive normal prices
    """

    # Transition table: (from_state, event) -> to_state
    TRANSITIONS = {
        # From NORMAL
        (AlertState.NORMAL, "great_deal"): AlertState.GREAT_ALERTING,
        (AlertState.NORMAL, "wow_deal"): AlertState.WOW_ALERTING,
        (AlertState.NORMAL, "normal"): AlertState.NORMAL,

        # From GREAT states
        (AlertState.GREAT_ALERTING, "alert_sent"): AlertState.GREAT_ALERTED,
        (AlertState.GREAT_ALERTED, "wow_deal"): AlertState.WOW_ALERTING,  # Escalation!
        (AlertState.GREAT_ALERTED, "great_deal"): AlertState.GREAT_ALERTED,  # Stay (no re-alert)
        (AlertState.GREAT_ALERTED, "normal"): AlertState.NORMAL,  # De-escalate silent

        # From WOW states
        (AlertState.WOW_ALERTING, "alert_sent"): AlertState.WOW_ALERTED,
        (AlertState.WOW_ALERTED, "wow_deal"): AlertState.WOW_ALERTED,  # Stay (no re-alert)
        (AlertState.WOW_ALERTED, "great_deal"): AlertState.GREAT_ALERTED,  # De-escalate silent
        (AlertState.WOW_ALERTED, "normal"): AlertState.NORMAL,  # Deal ended
    }

    RESET_THRESHOLD = 3  # Consecutive normal checks to reset cycle

    def __init__(self, db_client):
        self.db = db_client

    def process_price(
        self,
        route: str,
        tier: Optional[str],
        price_cents: int,
        is_mistake_fare: bool = False
    ) -> Tuple[bool, Optional[str], RouteAlertState]:
        """
        Process a price observation and determine if alert should be sent.

        Args:
            route: Route string e.g., "JFK-LOS"
            tier: Deal tier from anomaly detection ("great", "wow", None)
            price_cents: Current price in cents
            is_mistake_fare: True if detected as mistake fare

        Returns:
            Tuple of (should_alert, alert_tier, new_state)
        """
        # Load current state
        current = self._load_state(route)

        # Determine event
        if tier == "wow" or is_mistake_fare:
            event = "wow_deal"
            alert_tier = "WOW" if not is_mistake_fare else "MISTAKE"
        elif tier == "great":
            event = "great_deal"
            alert_tier = "Great"
        else:
            event = "normal"
            alert_tier = None

        # Check transition
        key = (current.state, event)
        new_state_enum = self.TRANSITIONS.get(key, current.state)

        # Determine if we should alert
        should_alert = new_state_enum in (AlertState.GREAT_ALERTING, AlertState.WOW_ALERTING)

        # Handle consecutive normal tracking for reset
        if event == "normal":
            current.consecutive_normal_count += 1
            if current.consecutive_normal_count >= self.RESET_THRESHOLD:
                new_state_enum = AlertState.NORMAL
                current.consecutive_normal_count = 0
        else:
            current.consecutive_normal_count = 0

        # Update state
        current.state = new_state_enum
        if should_alert:
            current.last_alert_tier = alert_tier
            current.last_alert_price = price_cents
            # Transition to ALERTED after processing
            current.state = self.TRANSITIONS.get(
                (new_state_enum, "alert_sent"),
                new_state_enum
            )

        # Persist
        self._save_state(current)

        return should_alert, alert_tier, current
```

### Pattern 3: Escalation Email Context
**What:** Include both "drop from last alert" and "vs normal price" in escalation emails
**When to use:** Great->WOW escalation scenarios
**Why:** User decision from CONTEXT.md

**Example:**
```python
# Source: CONTEXT.md decision on escalation email format
def format_escalation_context(
    current_price: int,
    last_alert_price: int,
    normal_price: int
) -> str:
    """
    Format price context for escalation emails.

    Shows both: drop since last alert AND savings vs normal.
    Example: "$580 (down $140 from yesterday, normally $920)"
    """
    drop_from_last = last_alert_price - current_price
    savings_vs_normal = normal_price - current_price

    return (
        f"${current_price // 100} "
        f"(down ${drop_from_last // 100} from last alert, "
        f"normally ${normal_price // 100})"
    )
```

### Anti-Patterns to Avoid
- **Time-based cooldowns per tier:** Original design had 48h/24h/12h cooldowns. User simplified to "once per deal window" -- simpler, less state to track
- **External FSM libraries:** `python-statemachine` and `transitions` are overkill for 5 states
- **Alerting on de-escalation:** User explicitly decided de-escalation (WOW->Great, Great->Normal) should be silent
- **Persisting full state objects:** Store minimal state (tier name, consecutive count); reconstruct in memory

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State persistence | Custom file-based state | Turso `alert_state` table | Already exists from Phase 2, handles concurrency |
| Tier classification | Manual threshold logic | Phase 3 `anomaly.classify_deal` | Already implemented, tested |
| Timestamp handling | Custom date parsing | `datetime.fromisoformat()` | Handles ISO format, edge cases |

**Key insight:** The FSM is simple enough that the complexity is in the transitions, not the framework. A custom Enum-based implementation is more transparent and easier to debug than any library.

## Common Pitfalls

### Pitfall 1: Alerting Multiple Times for Same Tier
**What goes wrong:** User gets 5 emails for the same Great deal because price fluctuates
**Why it happens:** Not tracking "already alerted at this tier"
**How to avoid:** FSM distinguishes GREAT_ALERTING (will alert) from GREAT_ALERTED (already alerted)
**Warning signs:** Users report duplicate emails

### Pitfall 2: Missing Escalation Alerts
**What goes wrong:** Deal escalates Great->WOW but no new email sent
**Why it happens:** Checking "already alerted" without considering tier change
**How to avoid:** Explicit escalation transition: GREAT_ALERTED + wow_deal -> WOW_ALERTING
**Warning signs:** WOW deals only sent to users who haven't seen the Great version

### Pitfall 3: State Persistence Race Conditions
**What goes wrong:** Two concurrent checks for same route overwrite each other's state
**Why it happens:** Read-modify-write without locking
**How to avoid:** Turso handles this via SQLite serialization; if using JSON, need file locking
**Warning signs:** Inconsistent state, duplicate alerts in high-frequency monitoring

### Pitfall 4: Forgetting to Reset Cycle
**What goes wrong:** Route stuck in ALERTED state forever, never alerts again
**Why it happens:** Not tracking consecutive normal prices to reset
**How to avoid:** Track `consecutive_normal_count`, reset to NORMAL after threshold
**Warning signs:** Route never alerts after first deal ends

### Pitfall 5: De-escalation Alerts Confusing Users
**What goes wrong:** User gets "Great deal on Lagos" after just seeing WOW deal for same route
**Why it happens:** Treating de-escalation as new deal
**How to avoid:** De-escalation transitions go directly to ALERTED state (silent)
**Warning signs:** Users confused about getting "worse" deal notification

## Code Examples

### Complete AlertStateMachine Implementation
```python
# Source: Python stdlib Enum, dataclass, design patterns research
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple, Dict

class AlertState(Enum):
    """Alert FSM states."""
    NORMAL = auto()           # No active deal
    GREAT_ALERTING = auto()   # Great deal, need to alert
    GREAT_ALERTED = auto()    # Great deal, already alerted
    WOW_ALERTING = auto()     # WOW deal, need to alert
    WOW_ALERTED = auto()      # WOW deal, already alerted


@dataclass
class RouteState:
    """Per-route alert state."""
    route: str
    state: AlertState = AlertState.NORMAL
    last_alert_tier: Optional[str] = None
    last_alert_price_cents: Optional[int] = None
    consecutive_normal: int = 0


class AlertStateMachine:
    """
    Tier-escalation FSM for flight deal alerts.

    States:
        NORMAL: No deal active
        GREAT_ALERTING: Great deal detected, will send alert
        GREAT_ALERTED: Great deal, alert already sent
        WOW_ALERTING: WOW deal detected, will send alert
        WOW_ALERTED: WOW deal, alert already sent

    Events:
        normal: Price is normal (not a deal)
        great_deal: Price qualifies as Great deal
        wow_deal: Price qualifies as WOW deal (or mistake fare)

    Key behaviors:
        - Alert once per deal at each tier
        - Escalation (Great->WOW) triggers new alert
        - De-escalation is silent
        - Reset after 3 consecutive normal prices
    """

    RESET_THRESHOLD = 3

    # Transition table: (current_state, event) -> (new_state, should_alert)
    TRANSITIONS: Dict[Tuple[AlertState, str], Tuple[AlertState, bool]] = {
        # From NORMAL
        (AlertState.NORMAL, "normal"): (AlertState.NORMAL, False),
        (AlertState.NORMAL, "great_deal"): (AlertState.GREAT_ALERTING, True),
        (AlertState.NORMAL, "wow_deal"): (AlertState.WOW_ALERTING, True),

        # From GREAT_ALERTING (transient, becomes ALERTED after alert sent)
        (AlertState.GREAT_ALERTING, "alert_sent"): (AlertState.GREAT_ALERTED, False),

        # From GREAT_ALERTED
        (AlertState.GREAT_ALERTED, "normal"): (AlertState.NORMAL, False),  # Deal ended
        (AlertState.GREAT_ALERTED, "great_deal"): (AlertState.GREAT_ALERTED, False),  # Same tier, no re-alert
        (AlertState.GREAT_ALERTED, "wow_deal"): (AlertState.WOW_ALERTING, True),  # ESCALATION!

        # From WOW_ALERTING (transient)
        (AlertState.WOW_ALERTING, "alert_sent"): (AlertState.WOW_ALERTED, False),

        # From WOW_ALERTED
        (AlertState.WOW_ALERTED, "normal"): (AlertState.NORMAL, False),  # Deal ended
        (AlertState.WOW_ALERTED, "great_deal"): (AlertState.GREAT_ALERTED, False),  # De-escalate silent
        (AlertState.WOW_ALERTED, "wow_deal"): (AlertState.WOW_ALERTED, False),  # Same tier, no re-alert
    }

    def __init__(self, db_client=None):
        """Initialize with optional database client for persistence."""
        self.db = db_client
        self._cache: Dict[str, RouteState] = {}

    def get_state(self, route: str) -> RouteState:
        """Get current state for a route, loading from DB if needed."""
        if route in self._cache:
            return self._cache[route]

        # Try loading from database
        if self.db and hasattr(self.db, 'get_alert_state'):
            db_state = self.db.get_alert_state(route)
            if db_state:
                state_name = db_state.get("current_tier") or "NORMAL"
                try:
                    state = AlertState[state_name]
                except KeyError:
                    state = AlertState.NORMAL

                route_state = RouteState(
                    route=route,
                    state=state,
                    consecutive_normal=db_state.get("consecutive_normal_count", 0),
                )
                self._cache[route] = route_state
                return route_state

        # New route, start in NORMAL
        route_state = RouteState(route=route)
        self._cache[route] = route_state
        return route_state

    def _save_state(self, state: RouteState) -> None:
        """Persist state to database."""
        self._cache[state.route] = state

        if self.db and hasattr(self.db, 'update_alert_state'):
            self.db.update_alert_state(
                route=state.route,
                current_tier=state.state.name,
                cooldown_expiry=None,  # Not used in "once per deal" model
                consecutive_normal_count=state.consecutive_normal,
            )

    def process(
        self,
        route: str,
        deal_tier: Optional[str],
        price_cents: int,
        is_mistake_fare: bool = False,
        normal_price_cents: Optional[int] = None
    ) -> Tuple[bool, Optional[dict]]:
        """
        Process a price check and determine alert action.

        Args:
            route: Route string e.g., "JFK-LOS"
            deal_tier: Tier from anomaly detection ("great", "wow", None)
            price_cents: Current price in cents
            is_mistake_fare: Flag from level shift detection
            normal_price_cents: Normal price for savings calculation

        Returns:
            Tuple of (should_alert, alert_info)
            alert_info contains: tier, price, is_escalation, context
        """
        current = self.get_state(route)

        # Determine event
        if is_mistake_fare:
            event = "wow_deal"
            tier_label = "MISTAKE"
        elif deal_tier == "wow" or deal_tier == "exceptional":
            event = "wow_deal"
            tier_label = "WOW"
        elif deal_tier == "great":
            event = "great_deal"
            tier_label = "Great"
        else:
            event = "normal"
            tier_label = None

        # Track consecutive normal for reset
        if event == "normal":
            current.consecutive_normal += 1
            if current.consecutive_normal >= self.RESET_THRESHOLD:
                # Reset cycle
                current.state = AlertState.NORMAL
                current.consecutive_normal = 0
                current.last_alert_tier = None
                current.last_alert_price_cents = None
                self._save_state(current)
                return False, None
        else:
            current.consecutive_normal = 0

        # Look up transition
        key = (current.state, event)
        transition = self.TRANSITIONS.get(key)

        if not transition:
            # No valid transition, stay in current state
            self._save_state(current)
            return False, None

        new_state, should_alert = transition

        # Check for escalation
        is_escalation = (
            current.last_alert_tier is not None and
            tier_label == "WOW" and
            current.last_alert_tier in ("Great", "GREAT")
        )

        # Build alert info
        alert_info = None
        if should_alert:
            alert_info = {
                "tier": tier_label,
                "tier_emoji": self._get_tier_emoji(tier_label, is_mistake_fare),
                "price_cents": price_cents,
                "is_escalation": is_escalation,
                "is_mistake_fare": is_mistake_fare,
                "last_alert_price_cents": current.last_alert_price_cents,
                "normal_price_cents": normal_price_cents,
            }

            # Update state to reflect alert will be sent
            current.last_alert_tier = tier_label
            current.last_alert_price_cents = price_cents

            # Transition to ALERTED state
            alert_sent_key = (new_state, "alert_sent")
            if alert_sent_key in self.TRANSITIONS:
                new_state = self.TRANSITIONS[alert_sent_key][0]

        current.state = new_state
        self._save_state(current)

        return should_alert, alert_info

    def _get_tier_emoji(self, tier: str, is_mistake_fare: bool) -> str:
        """Get emoji for tier label in email subject."""
        if is_mistake_fare:
            return "!!"  # Warning indicator for mistake fares

        tier_emojis = {
            "Great": "*",      # Star for great deals
            "WOW": "**",       # Double star for WOW
            "MISTAKE": "!!",   # Warning for mistake fares
        }
        return tier_emojis.get(tier, "")
```

### Email Subject Formatting
```python
# Source: CONTEXT.md decisions on email format
def format_alert_subject(
    route: str,
    dest_name: str,
    price_cents: int,
    tier: str,
    tier_emoji: str,
    is_escalation: bool,
    last_price_cents: Optional[int] = None
) -> str:
    """
    Format email subject line with tier and price.

    Normal: "[* Great] Lagos from $650"
    Escalation: "[** WOW] Price DROP: Lagos now $580 (was $720)"
    Mistake: "[!! MISTAKE] Book NOW: Lagos $400"
    """
    price = price_cents // 100
    origin = route.split("-")[0]

    if tier == "MISTAKE":
        return f"[{tier_emoji} MISTAKE FARE] Book NOW: {dest_name} ${price}"

    if is_escalation and last_price_cents:
        last_price = last_price_cents // 100
        return f"[{tier_emoji} {tier}] Price DROP: {dest_name} now ${price} (was ${last_price})"

    return f"[{tier_emoji} {tier}] {dest_name} from ${price}"


def format_escalation_body(
    current_price_cents: int,
    last_alert_price_cents: int,
    normal_price_cents: int
) -> str:
    """
    Format price context showing both drops.

    Example: "$580 (down $140 since our last alert, saves $340 vs normal $920)"
    """
    current = current_price_cents // 100
    last = last_alert_price_cents // 100
    normal = normal_price_cents // 100

    drop = last - current
    savings = normal - current

    return (
        f"${current} "
        f"(down ${drop} since our last alert, "
        f"saves ${savings} vs normal ${normal})"
    )
```

### Mistake Fare Urgency Messaging
```python
# Source: CONTEXT.md decision on mistake fare handling
MISTAKE_FARE_URGENCY = """
!! MISTAKE FARE -- Book NOW, may disappear in hours

This price is likely an error. Airlines sometimes honor these,
sometimes cancel within 24-72 hours. If you book:
- Use a credit card with good travel protection
- Don't book non-refundable hotels until fare is confirmed
- Most mistake fares ARE honored (~70%)
"""

def format_mistake_fare_alert(
    dest_name: str,
    price_cents: int,
    normal_price_cents: int,
    booking_url: str
) -> dict:
    """Format complete mistake fare alert content."""
    price = price_cents // 100
    normal = normal_price_cents // 100
    savings_pct = int((1 - price / normal) * 100)

    return {
        "subject": f"[!! MISTAKE FARE] {dest_name} ${price} ({savings_pct}% off!)",
        "urgency_banner": MISTAKE_FARE_URGENCY,
        "price_line": f"${price} (normally ${normal} -- save {savings_pct}%)",
        "cta": f"Book now: {booking_url}",
    }
```

## Database Schema Extension

The existing `alert_state` table needs minor extension:

```sql
-- Existing schema (from Phase 2)
CREATE TABLE IF NOT EXISTS alert_state (
    route TEXT PRIMARY KEY,
    current_tier TEXT,
    cooldown_expiry TEXT,              -- Not used in "once per deal" model
    consecutive_normal_count INTEGER DEFAULT 0
);

-- Extension for Phase 4 (add columns if not exist)
-- Note: SQLite doesn't support IF NOT EXISTS for columns
-- Implementation should check column existence first

ALTER TABLE alert_state ADD COLUMN last_alert_tier TEXT;
ALTER TABLE alert_state ADD COLUMN last_alert_price_cents INTEGER;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Time-based cooldowns (48h/24h/12h) | Once per deal window | CONTEXT.md decision | Simpler state, better UX |
| Three tiers (Good/Great/WOW) | Two tiers (Great/WOW) | CONTEXT.md decision | Simpler FSM, clearer value prop |
| External FSM library | Custom Enum-based FSM | Research finding | Fewer dependencies, easier debugging |
| Complex cooldown expiry tracking | Consecutive normal count reset | Design simplification | Less state to persist |

**Deprecated/outdated:**
- Time-based per-tier cooldowns: Replaced by "once per deal window" approach
- "Good" tier: Eliminated -- if it's just "good," Google Alerts can find it
- `cooldown_expiry` column: Kept for compatibility but not used

## Open Questions

1. **Consecutive Normal Threshold**
   - What we know: 3 checks recommended based on monitoring frequency
   - What's unclear: Optimal threshold for 2-hour priority vs daily standard monitoring
   - Recommendation: Start with 3, make configurable per monitoring frequency

2. **Mistake Fare Detection Integration**
   - What we know: Level shift detection produces `is_level_shift` flag
   - What's unclear: Should all level shifts be treated as mistake fares?
   - Recommendation: Level shift + exceptional z-score = mistake fare; level shift alone = WOW

3. **Schema Migration Strategy**
   - What we know: Need to add 2 columns to `alert_state`
   - What's unclear: Whether to use ALTER TABLE or recreate
   - Recommendation: ALTER TABLE with existence check, no data migration needed (new columns)

4. **Email Template Emoji Selection**
   - What we know: User wants distinctive emoji per tier
   - What's unclear: Exact emoji choices
   - Recommendation: Claude's discretion per CONTEXT.md -- use * and ** for text compatibility

## Sources

### Primary (HIGH confidence)
- [Python Enum Documentation](https://docs.python.org/3/library/enum.html) - State definitions
- [Python dataclass Documentation](https://docs.python.org/3/library/dataclasses.html) - State holder pattern
- `db/schema.py` - Existing alert_state table schema
- `db/client.py` - Existing update_alert_state and get_alert_state methods
- `04-CONTEXT.md` - User decisions on tiers, cooldowns, escalation

### Secondary (MEDIUM confidence)
- [python-statemachine PyPI](https://pypi.org/project/python-statemachine/) - Evaluated, deemed overkill
- [transitions GitHub](https://github.com/pytransitions/transitions) - Evaluated, deemed overkill
- [python-statemachine Persistence](https://python-statemachine.readthedocs.io/en/latest/auto_examples/persistent_model_machine.html) - Persistence pattern reference
- [DEV.to Simple State Machine](https://dev.to/karn/building-a-simple-state-machine-in-python) - Custom FSM pattern

### Tertiary (LOW confidence)
- [Squadcast Alert Deduplication](https://support.squadcast.com/services/alert-deduplication-rules/alert-deduplication-rules) - General deduplication concepts
- [PagerDuty Event Management](https://support.pagerduty.com/main/docs/event-management) - Cooldown/suppression patterns

## Metadata

**Confidence breakdown:**
- FSM design pattern: HIGH - Well-understood, minimal complexity
- Custom Enum implementation: HIGH - stdlib, no external dependencies
- Database schema extension: HIGH - Building on existing Phase 2 infrastructure
- Tier mapping from anomaly detection: HIGH - Integrates with existing Phase 3 code
- Email formatting: MEDIUM - User preferences may evolve

**Research date:** 2026-01-28
**Valid until:** 2026-03-28 (60 days - design patterns are stable)
