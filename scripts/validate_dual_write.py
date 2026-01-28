#!/usr/bin/env python3
"""
Dual-Write Validation Script

Compares seen_deals.json against Turso price_cache table.
Run daily during migration to validate data consistency.

Usage:
    python scripts/validate_dual_write.py

Exit codes:
    0: No discrepancies
    1: Discrepancies found (printed to stdout)
    2: Error (Turso unavailable, file missing, etc.)
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import TursoClient
from deal_finder import SEEN_DEALS_FILE, load_seen_deals


def validate():
    """Compare JSON and Turso state, return discrepancies."""

    # Load JSON state (source of truth)
    if not SEEN_DEALS_FILE.exists():
        print(f"[WARN] {SEEN_DEALS_FILE} not found")
        return {"status": "error", "reason": "JSON file missing"}

    json_data = load_seen_deals()

    # Connect to Turso
    client = TursoClient(dual_write=False)  # Read-only for validation
    if not client._turso_available:
        print("[WARN] Turso not available - cannot validate")
        return {"status": "error", "reason": "Turso unavailable"}

    # Query Turso price_cache
    try:
        result = client._conn.execute(
            "SELECT route, tier, price_cents, dest_name, last_seen FROM price_cache"
        ).fetchall()
    except Exception as e:
        print(f"[ERROR] Turso query failed: {e}")
        return {"status": "error", "reason": str(e)}

    # Build Turso dict for comparison
    turso_data = {}
    for row in result:
        route, tier, price_cents, dest_name, last_seen = row
        key = f"{route}-{tier}"
        turso_data[key] = {
            "price_cents": price_cents,
            "dest_name": dest_name,
            "last_seen": last_seen,
        }

    # Compare
    discrepancies = []

    # Check JSON entries against Turso
    for key, json_entry in json_data.items():
        json_price_cents = int(json_entry.get("price", 0) * 100)
        turso_entry = turso_data.get(key)

        if turso_entry is None:
            discrepancies.append({
                "key": key,
                "issue": "missing_in_turso",
                "json_price": json_price_cents,
            })
        elif turso_entry["price_cents"] != json_price_cents:
            discrepancies.append({
                "key": key,
                "issue": "price_mismatch",
                "json_price": json_price_cents,
                "turso_price": turso_entry["price_cents"],
            })

    # Check for Turso entries not in JSON
    for key, turso_entry in turso_data.items():
        if key not in json_data:
            discrepancies.append({
                "key": key,
                "issue": "missing_in_json",
                "turso_price": turso_entry["price_cents"],
            })

    return {
        "status": "ok" if not discrepancies else "discrepancies",
        "json_count": len(json_data),
        "turso_count": len(turso_data),
        "discrepancies": discrepancies,
        "validated_at": datetime.now().isoformat(),
    }


def main():
    print(f"Dual-Write Validation - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    result = validate()

    print(f"JSON entries: {result.get('json_count', 'N/A')}")
    print(f"Turso entries: {result.get('turso_count', 'N/A')}")

    if result["status"] == "error":
        print(f"\n[ERROR] {result['reason']}")
        sys.exit(2)

    if result["status"] == "ok":
        print("\n[OK] No discrepancies found")
        sys.exit(0)

    print(f"\n[WARN] {len(result['discrepancies'])} discrepancies found:")
    for d in result["discrepancies"]:
        print(f"  - {d['key']}: {d['issue']}")
        if d["issue"] == "price_mismatch":
            print(f"      JSON: {d['json_price']} cents, Turso: {d['turso_price']} cents")

    sys.exit(1)


if __name__ == "__main__":
    main()
