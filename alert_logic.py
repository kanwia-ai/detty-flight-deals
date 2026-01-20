"""
Detty Flight Deals - Smart Alert Logic

Determines when to send alerts based on MEANINGFUL changes:
- New destination on sale
- Tier upgrade (Great → WOW)
- Price drop of $100+ on same destination
- New origin airport with best price

Separates WOW (instant) from Good/Great (weekly digest).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# Files for tracking state
LAST_ALERT_FILE = Path(__file__).parent / "last_alert.json"
LAST_DIGEST_FILE = Path(__file__).parent / "last_digest.json"

# Thresholds for "meaningful" changes
PRICE_DROP_THRESHOLD = 100  # $100 drop = meaningful
TIER_PRIORITY = {"WOW": 3, "Great": 2, "Good": 1, "Normal": 0}


# ============================================================
# STATE MANAGEMENT
# ============================================================

def load_last_alert() -> dict:
    """Load the last instant alert state."""
    if not LAST_ALERT_FILE.exists():
        return {"sent_at": None, "destinations": {}}
    try:
        with open(LAST_ALERT_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"sent_at": None, "destinations": {}}


def save_last_alert(state: dict):
    """Save the instant alert state."""
    state["sent_at"] = datetime.now().isoformat()
    with open(LAST_ALERT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_last_digest() -> dict:
    """Load the last weekly digest state."""
    if not LAST_DIGEST_FILE.exists():
        return {"sent_at": None, "destinations": {}}
    try:
        with open(LAST_DIGEST_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"sent_at": None, "destinations": {}}


def save_last_digest(state: dict):
    """Save the weekly digest state."""
    state["sent_at"] = datetime.now().isoformat()
    with open(LAST_DIGEST_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ============================================================
# DEAL AGGREGATION
# ============================================================

def aggregate_by_destination(deals: list) -> dict:
    """
    Aggregate deals by destination, keeping best price and all origins.

    Returns: {
        "LOS": {
            "dest_name": "Lagos",
            "tier": "WOW",
            "best_price": 650,
            "percent_below": 45,
            "normal_price": 1200,
            "origins": {
                "JFK": {"price": 650, "departure": "2026-03-10", ...},
                "IAD": {"price": 720, "departure": "2026-03-15", ...},
            }
        }
    }
    """
    by_dest = {}

    for deal in deals:
        dest = deal["dest"]
        origin = deal["origin"]

        if dest not in by_dest:
            by_dest[dest] = {
                "dest": dest,
                "dest_name": deal["dest_name"],
                "tier": deal["tier"],
                "best_price": deal["price"],
                "percent_below": deal["percent_below"],
                "normal_price": deal["normal_price"],
                "origins": {},
            }

        # Update best price and tier if this origin is cheaper
        if deal["price"] < by_dest[dest]["best_price"]:
            by_dest[dest]["best_price"] = deal["price"]
            by_dest[dest]["tier"] = deal["tier"]
            by_dest[dest]["percent_below"] = deal["percent_below"]

        # Track all origins
        by_dest[dest]["origins"][origin] = {
            "price": deal["price"],
            "departure": deal["departure"],
            "return": deal["return"],
            "url": deal["url"],
        }

    return by_dest


# ============================================================
# MEANINGFUL CHANGE DETECTION
# ============================================================

def is_tier_upgrade(old_tier: str, new_tier: str) -> bool:
    """Check if this is a tier upgrade (e.g., Great → WOW)."""
    return TIER_PRIORITY.get(new_tier, 0) > TIER_PRIORITY.get(old_tier, 0)


def is_significant_price_drop(old_price: int, new_price: int) -> bool:
    """Check if price dropped by at least $100."""
    return (old_price - new_price) >= PRICE_DROP_THRESHOLD


def compute_meaningful_changes(current_deals: dict, last_alert: dict) -> dict:
    """
    Compare current deals to last alert, identify meaningful changes.

    Returns: {
        "new_destinations": [dest_data, ...],      # Completely new
        "tier_upgrades": [dest_data, ...],         # Great → WOW
        "price_drops": [dest_data, ...],           # $100+ cheaper
        "unchanged": [dest_data, ...],             # Same as before
    }
    """
    last_dests = last_alert.get("destinations", {})

    changes = {
        "new_destinations": [],
        "tier_upgrades": [],
        "price_drops": [],
        "unchanged": [],
    }

    for dest, data in current_deals.items():
        if dest not in last_dests:
            # Completely new destination
            changes["new_destinations"].append(data)
        else:
            old = last_dests[dest]
            old_tier = old.get("tier", "Normal")
            old_price = old.get("best_price", 9999)
            new_tier = data["tier"]
            new_price = data["best_price"]

            if is_tier_upgrade(old_tier, new_tier):
                # Tier upgrade (e.g., Great → WOW)
                data["change_reason"] = f"Upgraded from {old_tier} to {new_tier}"
                changes["tier_upgrades"].append(data)
            elif is_significant_price_drop(old_price, new_price):
                # Significant price drop
                data["change_reason"] = f"Price dropped ${old_price - new_price} (was ${old_price})"
                changes["price_drops"].append(data)
            else:
                # No meaningful change
                changes["unchanged"].append(data)

    return changes


# ============================================================
# ALERT DECISION LOGIC
# ============================================================

def should_send_instant_alert(current_deals: list) -> tuple[bool, list, dict]:
    """
    Determine if we should send an instant WOW alert.

    Returns: (should_send, wow_deals_to_send, updated_state)
    """
    # Aggregate current deals by destination
    by_dest = aggregate_by_destination(current_deals)

    # Filter to WOW-only
    wow_deals = {d: data for d, data in by_dest.items() if data["tier"] == "WOW"}

    if not wow_deals:
        return (False, [], {})

    # Load last alert state
    last_alert = load_last_alert()

    # Compute meaningful changes
    changes = compute_meaningful_changes(wow_deals, last_alert)

    # Deals worth alerting about
    alert_worthy = (
        changes["new_destinations"] +
        changes["tier_upgrades"] +
        changes["price_drops"]
    )

    if not alert_worthy:
        print(f"  WOW deals found but no meaningful changes from last alert")
        return (False, [], {})

    # Build new state (ALL current WOW deals, not just changes)
    new_state = {
        "destinations": {
            d: {
                "tier": data["tier"],
                "best_price": data["best_price"],
                "origins": list(data["origins"].keys()),
            }
            for d, data in wow_deals.items()
        }
    }

    return (True, alert_worthy, new_state)


def should_send_weekly_digest(current_deals: list) -> tuple[bool, list, dict]:
    """
    Determine if we should send the weekly digest (Good + Great deals).
    Only sends once per week (Sunday).

    Returns: (should_send, deals_to_send, updated_state)
    """
    # Check if it's Sunday (or override for testing)
    today = datetime.now()
    is_sunday = today.weekday() == 6

    # Load last digest
    last_digest = load_last_digest()
    last_sent = last_digest.get("sent_at")

    # Check if we already sent this week
    if last_sent:
        last_sent_dt = datetime.fromisoformat(last_sent)
        days_since = (today - last_sent_dt).days
        if days_since < 6:  # Don't send more than once per week
            print(f"  Weekly digest already sent {days_since} days ago")
            return (False, [], {})

    if not is_sunday:
        print(f"  Not Sunday (today is {today.strftime('%A')}), skipping digest")
        return (False, [], {})

    # Aggregate and filter to Good + Great only
    by_dest = aggregate_by_destination(current_deals)
    digest_deals = {
        d: data for d, data in by_dest.items()
        if data["tier"] in ["Good", "Great"]
    }

    if not digest_deals:
        return (False, [], {})

    # Build state
    new_state = {
        "destinations": {
            d: {
                "tier": data["tier"],
                "best_price": data["best_price"],
            }
            for d, data in digest_deals.items()
        }
    }

    return (True, list(digest_deals.values()), new_state)


# ============================================================
# TESTING / MANUAL OVERRIDE
# ============================================================

def force_digest_check(current_deals: list) -> tuple[bool, list]:
    """
    Force a digest check regardless of day of week.
    For testing purposes.
    """
    by_dest = aggregate_by_destination(current_deals)
    digest_deals = [
        data for d, data in by_dest.items()
        if data["tier"] in ["Good", "Great"]
    ]
    return (len(digest_deals) > 0, digest_deals)


def get_alert_summary(current_deals: list) -> str:
    """
    Get a summary of what would be sent.
    Useful for debugging and testing.
    """
    by_dest = aggregate_by_destination(current_deals)

    # WOW check
    wow_deals = {d: data for d, data in by_dest.items() if data["tier"] == "WOW"}
    last_alert = load_last_alert()
    wow_changes = compute_meaningful_changes(wow_deals, last_alert) if wow_deals else {}

    # Great/Good for digest
    digest_deals = {d: data for d, data in by_dest.items() if data["tier"] in ["Good", "Great"]}

    lines = ["=" * 50, "ALERT SUMMARY", "=" * 50, ""]

    # WOW section
    lines.append(f"🚨 WOW DEALS: {len(wow_deals)} destinations")
    if wow_changes:
        lines.append(f"   New: {len(wow_changes.get('new_destinations', []))}")
        lines.append(f"   Tier upgrades: {len(wow_changes.get('tier_upgrades', []))}")
        lines.append(f"   Price drops: {len(wow_changes.get('price_drops', []))}")
        lines.append(f"   Unchanged: {len(wow_changes.get('unchanged', []))}")

        alert_worthy = (
            wow_changes.get("new_destinations", []) +
            wow_changes.get("tier_upgrades", []) +
            wow_changes.get("price_drops", [])
        )
        lines.append(f"   → Would send instant alert: {'YES' if alert_worthy else 'NO'}")
    lines.append("")

    # Digest section
    lines.append(f"📊 DIGEST DEALS: {len(digest_deals)} destinations")
    lines.append(f"   Great: {len([d for d in digest_deals.values() if d['tier'] == 'Great'])}")
    lines.append(f"   Good: {len([d for d in digest_deals.values() if d['tier'] == 'Good'])}")

    last_digest = load_last_digest()
    last_sent = last_digest.get("sent_at", "never")
    lines.append(f"   Last digest sent: {last_sent}")
    lines.append(f"   → Would send digest: {'YES (if Sunday)' if digest_deals else 'NO'}")

    return "\n".join(lines)


# ============================================================
# MAIN (for testing)
# ============================================================

if __name__ == "__main__":
    # Test with sample data
    sample_deals = [
        {"origin": "JFK", "dest": "FIH", "dest_name": "Kinshasa", "price": 880,
         "tier": "WOW", "percent_below": 41, "normal_price": 1500,
         "departure": "2026-03-10", "return": "2026-03-20", "url": "https://..."},
        {"origin": "IAD", "dest": "DSS", "dest_name": "Dakar", "price": 628,
         "tier": "Great", "percent_below": 37, "normal_price": 1000,
         "departure": "2026-03-17", "return": "2026-03-27", "url": "https://..."},
        {"origin": "JFK", "dest": "ABJ", "dest_name": "Abidjan", "price": 885,
         "tier": "Great", "percent_below": 32, "normal_price": 1300,
         "departure": "2026-03-10", "return": "2026-03-20", "url": "https://..."},
    ]

    print(get_alert_summary(sample_deals))
