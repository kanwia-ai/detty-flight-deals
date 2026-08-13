"""
One-off: migrate seen_deals.json alert memory to the channel key format.

The Aug 9 baselines rework changed alert-memory keys from
{ORIG}-{DEST}-{tier}-{bucket} to {channel}:{ORIG}-{DEST}-{bucket} without
migrating the file, which orphaned every alert recorded before it shipped.
should_alert_wow() saw a blank slate and re-blasted fares subscribers had
already been told about — three consecutive 🚨 mornings Aug 9-11, capped by
Lagos $1032 re-alerting one dollar ABOVE the $1031 recorded on Aug 2.

Seeds both channels ("wow" and "digest") with the cheapest price ever
recorded per route+bucket under the old keys, keeps an existing channel
record when it is already cheaper, then drops the dead old-format keys.
Idempotent: once no old-format keys remain, re-running is a no-op.

Run from anywhere:  python scripts/migrate_seen_deals.py
"""

import json
from pathlib import Path

STATE_FILE = Path(__file__).parent.parent / "seen_deals.json"


def main():
    with open(STATE_FILE) as f:
        seen = json.load(f)

    old = {k: v for k, v in seen.items()
           if ":" not in k and not k.startswith("_")}
    if not old:
        print("No old-format keys — nothing to migrate.")
        return

    # Cheapest record per route+bucket (ties: most recent sighting)
    best = {}
    for key, entry in old.items():
        parts = key.split("-")  # ORIG-DEST-tier-bucket, bucket may contain '-'
        route_bucket = f"{parts[0]}-{parts[1]}-{'-'.join(parts[3:])}"
        cur = best.get(route_bucket)
        if (cur is None or entry["price"] < cur["price"]
                or (entry["price"] == cur["price"]
                    and entry["last_seen"] > cur["last_seen"])):
            best[route_bucket] = entry

    seeded = 0
    for route_bucket, entry in sorted(best.items()):
        for channel in ("wow", "digest"):
            target = f"{channel}:{route_bucket}"
            prior = seen.get(target)
            if prior is not None and prior["price"] <= entry["price"]:
                continue
            seen[target] = {
                "price": entry["price"],
                "tier": entry["tier"],
                "last_seen": max(entry["last_seen"],
                                 prior["last_seen"] if prior else ""),
                "dest_name": entry["dest_name"],
            }
            seeded += 1
            print(f"  {target:32} <- ${entry['price']} ({entry['last_seen']})")

    for key in old:
        del seen[key]

    with open(STATE_FILE, "w") as f:
        json.dump(seen, f, indent=2)

    print(f"\nSeeded/updated {seeded} channel records from {len(old)} "
          f"old-format keys ({len(best)} route+buckets); "
          f"state now has {len(seen)} entries.")


if __name__ == "__main__":
    main()
