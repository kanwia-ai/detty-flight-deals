# Phase 6: Business/First Class Monitoring - Research

**Researched:** 2026-02-10
**Domain:** Premium cabin fare monitoring via Amadeus API + existing anomaly detection pipeline
**Confidence:** HIGH (for API integration), MEDIUM (for threshold calibration)

## Summary

Phase 6 adds premium cabin fare monitoring (Business, First, Premium Economy) to the existing Amadeus priority route monitoring system. The core technical integration is straightforward: the Amadeus Flight Offers Search API accepts a `travelClass` query parameter with values `ECONOMY`, `PREMIUM_ECONOMY`, `BUSINESS`, or `FIRST`. The existing `amadeus_client.py` already uses `search_offers_fallback()` which calls `flight_offers_search.get()` -- adding `travelClass` is a single parameter addition. However, the Cheapest Date Search API does **not** support cabin class filtering, so premium cabin monitoring must exclusively use Flight Offers Search (the fallback path).

The main complexity is in the anomaly detection and threshold systems, which are currently economy-only. Premium cabins need separate baselines, separate thresholds, and a longer silent monitoring period (4+ weeks per CONTEXT.md) before alerts fire. The subscriber routing is already built (Phase 5 premium-only routing) and can be reused directly -- premium cabin deals are routed identically to mistake fares: instant email + SMS to premium subscribers only.

**Primary recommendation:** Add `travelClass` parameter to `search_offers_fallback()`, create a parallel `PremiumCabinMonitor` that runs on a separate 4-6 hour cadence, with its own cache keys (route + cabin class), separate static thresholds, and a hard API budget cap tracked via a persistent counter file (like `price_cache.json`).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| amadeus | >=12.0.0 | Amadeus SDK (already installed) | Already in use; `travelClass` param is a simple addition to `flight_offers_search.get()` |
| tenacity | >=8.0.0 | Retry logic for API calls | Already in use in `db/client.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | >=2.0.0 | Price history analysis | Already used in anomaly detection; reuse for premium cabin baselines |
| scipy | >=1.11.0 | Statistical calculations | Already used in anomaly detection; same z-score pipeline |

### No New Dependencies
No new libraries are needed. Everything required is already installed via `requirements.txt`.

## Architecture Patterns

### Recommended Changes to Project Structure
```
detty-flight-deals/
├── amadeus_client.py           # ADD: travelClass parameter to search_offers_fallback()
├── amadeus_monitor.py          # KEEP: economy-only, unchanged
├── premium_cabin_monitor.py    # NEW: orchestrator for premium cabin monitoring
├── price_tracker.py            # MODIFY: cabin_class-aware cache keys
├── anomaly/
│   ├── static_thresholds.py    # ADD: PREMIUM_STATIC_THRESHOLDS dict
│   ├── baseline_calculator.py  # MODIFY: pass cabin_class through classify_deal()
│   └── ...                     # Other anomaly modules unchanged
├── alert/
│   ├── state_machine.py        # MODIFY: cabin_class-aware route state keys
│   └── templates.py            # ADD: premium cabin email card styling
├── subscriber/
│   └── router.py               # REUSE: premium-only routing already exists
├── db/
│   ├── schema.py               # EXISTING: cabin_class column already exists in price_observations
│   └── client.py               # EXISTING: record_observation() already accepts cabin_class param
├── premium_budget.json         # NEW: API budget counter (persistent across runs)
└── .github/workflows/
    └── premium_cabin_monitor.yml  # NEW: separate workflow, every 4-6 hours
```

### Pattern 1: Cabin-Class-Aware Cache Keys
**What:** Extend cache key format from `"JFK-LOS"` to `"JFK-LOS:BUSINESS"` for premium cabin tracking.
**When to use:** Whenever storing or retrieving price data for premium cabins.
**Why:** Economy and business class prices for the same route are completely independent data series. They must have separate baselines, separate cooldowns, and separate FSM states. Using the same cache key would corrupt both.

```python
# Current cache key (economy):
def make_cache_key(self, origin: str, dest: str) -> str:
    return f"{origin}-{dest}"

# Extended cache key (cabin-aware):
def make_cache_key(self, origin: str, dest: str, cabin_class: str = "economy") -> str:
    if cabin_class == "economy":
        return f"{origin}-{dest}"  # Backward compatible
    return f"{origin}-{dest}:{cabin_class.upper()}"
```

### Pattern 2: Separate Monitor Orchestrator
**What:** Create `premium_cabin_monitor.py` as a separate entry point (like `amadeus_monitor.py`).
**When to use:** Premium cabin monitoring runs on a different cadence (every 4-6 hours) than economy (every 2 hours).
**Why:** Different schedules, different API budgets, different alert treatment. A separate orchestrator avoids complicating the existing `amadeus_monitor.py` with conditional logic.

```python
# premium_cabin_monitor.py - main entry point
CABIN_CLASSES = ["BUSINESS", "FIRST", "PREMIUM_ECONOMY"]
PRIORITY_ROUTES = [...]  # Same 6 routes as amadeus_client.py

def monitor_premium_cabins():
    """Monitor premium cabin fares on priority routes."""
    budget = load_budget()
    if budget.is_exhausted():
        print("Monthly API budget exhausted. Skipping premium cabin check.")
        return

    client = create_amadeus_client()
    for origin, dest in PRIORITY_ROUTES:
        for cabin in CABIN_CLASSES:
            if budget.remaining() < 12:  # Need 12 calls per route-cabin combo
                break
            prices = search_offers_with_cabin(client, origin, dest, cabin)
            budget.record(len(prices) if prices else 1)
            # ... classify, route alerts ...

    budget.save()
```

### Pattern 3: API Budget Hard Cap
**What:** Persistent JSON counter tracking API calls per month, with a hard stop at $25/month.
**When to use:** Every API call in premium cabin monitoring.
**Why:** User explicitly requested a $25/month hard budget cap. At ~$0.004 per Flight Offers Search call (Amadeus production pricing), that is roughly 6,250 calls/month max. At 6 routes x 3 cabin classes x 12 sample dates = 216 calls per run, the budget supports ~28 runs/month, or roughly one run every 4-5 hours.

```python
# premium_budget.json structure
{
    "month": "2026-02",
    "calls_used": 432,
    "budget_limit_calls": 6250,
    "last_run": "2026-02-10T14:30:00"
}
```

### Anti-Patterns to Avoid
- **Mixing economy and premium cabin in one cache key:** Will corrupt baseline calculations. Always include cabin class in all keys.
- **Reusing economy thresholds for business class:** Business class prices have completely different distributions. A $2,000 business class fare to Lagos is normal; a $2,000 economy fare is absurd.
- **Alerting during silent monitoring period:** Premium cabins need 4+ weeks of data collection before sending any alerts. Alerting on day 1 with no baseline will produce false positives.
- **Running premium cabin checks at economy cadence:** Wastes API budget. Premium cabin deals change slowly; every 4-6 hours is sufficient.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cabin class filtering | Custom HTTP requests to Amadeus | `travelClass` param on `flight_offers_search.get()` | SDK handles OAuth, rate limiting, error codes |
| Premium subscriber routing | New routing logic | Existing `AlertRouter` from Phase 5 | Already routes WOW/mistake deals to premium-only subscribers with SMS |
| Price history storage | New database table | Existing `price_observations` table | Already has `cabin_class` column (default 'economy') |
| Z-score anomaly detection | Separate detection pipeline | Existing `BaselineCalculator` | Already accepts `cabin_class` parameter in `classify_deal()` and `_get_price_history()` |
| Alert state tracking | New FSM | Existing `AlertStateMachine` | Use cabin-class-aware route keys; FSM logic is identical |

**Key insight:** The existing infrastructure was designed with cabin class awareness from the start. The `price_observations` table already has a `cabin_class` column. The `BaselineCalculator.classify_deal()` already accepts a `cabin_class` parameter. The `TursoClient.get_price_history()` already filters by `cabin_class`. The heavy lifting is already done; Phase 6 is primarily about wiring up the Amadeus parameter and adding premium-cabin-specific thresholds.

## Common Pitfalls

### Pitfall 1: Cheapest Date Search Does NOT Support Cabin Class
**What goes wrong:** Attempting to use `flight_dates.get()` with a cabin class parameter fails silently (returns economy results) or errors.
**Why it happens:** The Flight Cheapest Date Search API does not accept a `travelClass` parameter. It returns cached data and the cache is economy-only for most routes.
**How to avoid:** Premium cabin monitoring MUST use `flight_offers_search.get()` exclusively (the "fallback" path). Do not attempt the Cheapest Date Search first for premium cabins -- it is a wasted API call.
**Warning signs:** Getting suspiciously cheap "business class" prices that match economy prices.

### Pitfall 2: Insufficient Silent Monitoring Before First Alert
**What goes wrong:** First premium cabin alert fires on day 1 with no baseline, resulting in false positive or embarrassingly high "deal" price.
**Why it happens:** Static thresholds for premium cabins are estimates, not researched baselines like economy. Without observed data, a $3,000 business class fare might be classified as a "deal" when it is actually the normal price.
**How to avoid:** Enforce a minimum observation count (e.g., 28 observations = 4 weeks of 4-6 hourly checks) before allowing ANY premium cabin alerts. During silent monitoring, log prices to `price_observations` but never trigger alerts.
**Warning signs:** Premium cabin alerts with `observation_count < 28` in the first month.

### Pitfall 3: API Budget Exhaustion Mid-Month
**What goes wrong:** All premium cabin API calls are consumed in the first 2 weeks, leaving zero monitoring for the rest of the month.
**Why it happens:** Not tracking budget per run, or a bug that causes infinite retry loops.
**How to avoid:** Load budget counter at start of each run. Check remaining budget BEFORE each API call. Save counter after each run. Reset counter on month change.
**Warning signs:** `premium_budget.json` showing `calls_used > budget_limit_calls`.

### Pitfall 4: Cache Key Collision Between Economy and Premium
**What goes wrong:** Premium cabin price updates overwrite economy cache entries (or vice versa), corrupting baseline calculations.
**Why it happens:** Using the same cache key format (e.g., `"JFK-LOS"`) for both economy and business class data.
**How to avoid:** Always include cabin class in cache keys: `"JFK-LOS:BUSINESS"`. Keep economy keys as-is (`"JFK-LOS"`) for backward compatibility.
**Warning signs:** Economy deal alerts with business-class-level prices, or business class alerts with economy-level prices.

### Pitfall 5: Amadeus Test Environment May Lack Premium Cabin Data
**What goes wrong:** Business/first class searches in the Amadeus test environment return no results or return economy-only results.
**Why it happens:** The test environment uses a subset of real data. Premium cabin inventory on niche routes (US-Africa) may not be in the test dataset.
**How to avoid:** Test with `AMADEUS_HOSTNAME=test` first, but expect that switching to `production` will be necessary for real premium cabin data. Build the system to handle "no results" gracefully -- log it but don't error.
**Warning signs:** All premium cabin searches returning empty results in test mode.

### Pitfall 6: First Class Rarely Available on US-Africa Routes
**What goes wrong:** System monitors FIRST class but never finds any inventory, wasting API calls.
**Why it happens:** Very few airlines offer true First class on US-Africa routes. Most "First" results will be empty or return Business class results.
**How to avoid:** Start with BUSINESS and PREMIUM_ECONOMY monitoring. Add FIRST only if initial data collection shows available inventory. The user's context says "monitor three premium cabin classes" but be prepared that FIRST may yield no data.
**Warning signs:** FIRST class searches consistently returning 0 results across all routes.

## Code Examples

### Adding travelClass to Flight Offers Search
```python
# Source: Amadeus API Reference - Flight Offers Search GET endpoint
# https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search/api-reference

# Current code in amadeus_client.py (economy, no travelClass specified):
response = client.shopping.flight_offers_search.get(
    originLocationCode=origin,
    destinationLocationCode=dest,
    departureDate=date,
    adults=1,
    max=5,
    currencyCode="USD",
)

# Updated code for premium cabin search:
response = client.shopping.flight_offers_search.get(
    originLocationCode=origin,
    destinationLocationCode=dest,
    departureDate=date,
    adults=1,
    max=5,
    currencyCode="USD",
    travelClass="BUSINESS",  # ECONOMY | PREMIUM_ECONOMY | BUSINESS | FIRST
)
```

### Premium Cabin Static Thresholds
```python
# Source: Market research from KAYAK, Momondo, Cheapflights (2025-2026 data)
# Business class US-Africa typical pricing:
#   - JFK/EWR to Lagos (LOS): $3,000-$5,000 round trip (normal)
#   - JFK/EWR to Accra (ACC): $2,600-$4,500 round trip (normal)
#   - Deal threshold: 40-50% below normal per CONTEXT.md

PREMIUM_STATIC_THRESHOLDS = {
    # Business Class (research-based estimates)
    "BUSINESS": {
        "LOS": {"normal": 4000, "deal": 2400},  # 40% off $4,000
        "ABV": {"normal": 4000, "deal": 2400},
        "ACC": {"normal": 3500, "deal": 2100},  # 40% off $3,500
    },
    # First Class (very limited availability on US-Africa routes)
    "FIRST": {
        "LOS": {"normal": 8000, "deal": 4000},  # 50% off
        "ACC": {"normal": 7000, "deal": 3500},
    },
    # Premium Economy
    "PREMIUM_ECONOMY": {
        "LOS": {"normal": 1800, "deal": 1080},  # 40% off $1,800
        "ACC": {"normal": 1600, "deal": 960},
    },
}
```

**NOTE:** These thresholds are LOW confidence estimates based on web search data. The 4+ week silent monitoring period exists precisely because these numbers need validation against real observed prices before being used for alerts.

### API Budget Tracker
```python
# premium_budget.json pattern
import json
from datetime import datetime
from pathlib import Path

class PremiumBudget:
    """Track API calls against monthly budget cap."""

    BUDGET_FILE = Path(__file__).parent / "premium_budget.json"
    MAX_CALLS_PER_MONTH = 6250  # ~$25 at $0.004/call

    def __init__(self):
        self._data = self._load()
        self._check_month_rollover()

    def _load(self):
        if not self.BUDGET_FILE.exists():
            return {"month": "", "calls_used": 0, "budget_limit_calls": self.MAX_CALLS_PER_MONTH}
        try:
            with open(self.BUDGET_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"month": "", "calls_used": 0, "budget_limit_calls": self.MAX_CALLS_PER_MONTH}

    def _check_month_rollover(self):
        current_month = datetime.now().strftime("%Y-%m")
        if self._data.get("month") != current_month:
            self._data = {
                "month": current_month,
                "calls_used": 0,
                "budget_limit_calls": self.MAX_CALLS_PER_MONTH,
                "last_run": None,
            }

    def remaining(self) -> int:
        return max(0, self._data["budget_limit_calls"] - self._data["calls_used"])

    def is_exhausted(self) -> bool:
        return self.remaining() <= 0

    def record(self, count: int):
        self._data["calls_used"] += count
        self._data["last_run"] = datetime.now().isoformat()

    def save(self):
        with open(self.BUDGET_FILE, "w") as f:
            json.dump(self._data, f, indent=2)
```

### Cabin-Class-Aware Alert State Key
```python
# Extending the FSM to use cabin-class-aware route keys
# Current: fsm.process("JFK-LOS", deal_tier="great", price_cents=65000)
# New:     fsm.process("JFK-LOS:BUSINESS", deal_tier="great", price_cents=240000)

# The FSM itself doesn't change -- the route key already supports any string.
# The caller constructs the key with cabin class appended.

def build_route_key(origin: str, dest: str, cabin_class: str = "economy") -> str:
    """Build a route key that includes cabin class for premium cabins."""
    base = f"{origin}-{dest}"
    if cabin_class == "economy":
        return base  # Backward compatible
    return f"{base}:{cabin_class.upper()}"
```

### Premium Cabin Email Template
```python
# Extending format_destination_card_html for premium cabin badge
def format_premium_cabin_card_html(deal: dict) -> str:
    """Format a premium cabin deal card with cabin class badge."""
    cabin = deal.get("cabin_class", "BUSINESS").upper()

    # Cabin-specific styling
    cabin_colors = {
        "BUSINESS": {"badge_bg": "#1E40AF", "badge_text": "#FFF", "label": "Business Class"},
        "FIRST": {"badge_bg": "#7C2D12", "badge_text": "#FFF", "label": "First Class"},
        "PREMIUM_ECONOMY": {"badge_bg": "#065F46", "badge_text": "#FFF", "label": "Premium Economy"},
    }
    cc = cabin_colors.get(cabin, cabin_colors["BUSINESS"])

    # Card follows same pattern as format_destination_card_html in deal_finder.py
    # but adds cabin class badge and uses WOW-level urgency colors
    # ... (same structure as existing cards with cabin badge prepended)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Economy-only monitoring | Cabin-class-aware monitoring | Phase 6 | Separate data series per cabin class |
| Single cache key per route | Cabin-appended cache keys | Phase 6 | Prevents data corruption between cabin classes |
| Economy-only static thresholds | Per-cabin-class thresholds | Phase 6 | Accurate deal classification for premium cabins |
| Cheapest Date Search primary | Flight Offers Search only (premium) | Phase 6 | Cheapest Date Search does not support cabin class |

**Important note on Cheapest Date Search:**
- The Flight Cheapest Date Search API does **NOT** support `travelClass` filtering.
- Premium cabin monitoring must use Flight Offers Search exclusively.
- This means premium cabin monitoring costs 12 API calls per route-cabin combo (vs. potentially 1 for economy via Cheapest Date Search).
- This is the primary driver of the API budget constraint.

## Open Questions

1. **Exact premium cabin "normal" prices**
   - What we know: Business class US to Lagos is roughly $3,000-$5,000 based on KAYAK/Momondo/Cheapflights data. Accra is roughly $2,600-$4,500.
   - What's unclear: These are aggregate ranges, not route-specific baselines. The actual normal price for JFK-LOS Business vs. ATL-LOS Business may differ significantly.
   - Recommendation: Use the MEDIUM-confidence estimates in `PREMIUM_STATIC_THRESHOLDS` as initial fallback, but rely on the 4+ week silent monitoring period to build real baselines before alerting. The z-score anomaly detection (which uses actual observed data) will be far more reliable than these static estimates.

2. **First Class availability on US-Africa routes**
   - What we know: Very few airlines offer true First class on US-Africa routes. Ethiopian Airlines has Business class only. Turkish Airlines offers Business. United/Delta codeshares may have First on the US domestic legs only.
   - What's unclear: Whether the Amadeus API returns FIRST class results for these specific routes, or whether it returns empty results.
   - Recommendation: Include FIRST in monitoring but handle empty results gracefully. If after 2 weeks of monitoring, a cabin class consistently returns zero results for a route, log a warning and optionally skip that cabin-route combo to save API budget.

3. **Amadeus API per-call pricing in production**
   - What we know: Amadeus production pricing is roughly $0.003-$0.046 per call depending on API type. Flight Offers Search is on the lower end.
   - What's unclear: The exact per-call price for Flight Offers Search in production. Some sources cite ~$0.004, others cite different rates.
   - Recommendation: Use $0.004/call as the planning estimate (6,250 calls/month at $25 budget). Build the budget tracker with a configurable `MAX_CALLS_PER_MONTH` so it can be adjusted after seeing the first production invoice. Start conservative (e.g., 5,000 calls/month) and increase if budget allows.

4. **Optimal silent monitoring period length**
   - What we know: CONTEXT.md says 4+ weeks minimum. Economy uses 30 observations for z-score (2 weeks at 12 checks/day). Premium cabins check every 4-6 hours = 4-6 checks/day.
   - What's unclear: Exactly how many observations are needed for reliable premium cabin baselines.
   - Recommendation: Use 28 observations minimum (= 4 weeks at ~1 check per day, or 5-7 days at 4-6 checks/day). The z-score anomaly detector already requires `min_periods=30` observations, so the silent period naturally aligns. Enforce a hard floor of 28 days of calendar time even if observation count exceeds 30 earlier (prices may vary by day of week, need full week cycles).

5. **Whether to use a feature flag**
   - What we know: CONTEXT.md lists this as "Claude's discretion."
   - What's unclear: Whether the feature should be toggleable without code changes.
   - Recommendation: Use an environment variable `PREMIUM_CABIN_MONITORING_ENABLED=true/false` (default false). This allows enabling/disabling via GitHub Secrets without code changes, and makes silent monitoring easy to manage. The separate GitHub Actions workflow also serves as an implicit toggle (disable the workflow to disable monitoring).

## Sources

### Primary (HIGH confidence)
- Amadeus Flight Offers Search API Reference - `travelClass` parameter accepts `ECONOMY | PREMIUM_ECONOMY | BUSINESS | FIRST`
  - Source: [Amadeus API Reference](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search/api-reference)
  - Source: [Ballerina connector docs (mirrors official API)](https://central.ballerina.io/ballerinax/amadeus.flightofferssearch/latest) - confirmed full parameter list
- Amadeus Flight Cheapest Date Search API - does NOT support `travelClass` parameter
  - Source: [Amadeus Cheapest Date Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search/api-reference)
  - Source: [Flight APIs Tutorial](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/flights/)
- Existing codebase analysis - `cabin_class` column already exists in `price_observations` table, `BaselineCalculator.classify_deal()` already accepts `cabin_class` parameter, `TursoClient.get_price_history()` already filters by `cabin_class`

### Secondary (MEDIUM confidence)
- Business class US-Africa pricing: $2,600-$5,000 round trip based on KAYAK, Momondo, Cheapflights aggregated data (multiple sources agree)
  - Source: [KAYAK Business Class to Africa](https://www.kayak.com/flight-routes/Business-Class-United-States-US0/Africa-AF0.bc.ksp)
  - Source: [KAYAK Business Class to Lagos](https://www.kayak.com/flight-routes/Business-Class-United-States-US0/Lagos-Murtala-Muhammed-LOS.bc.ksp)
  - Source: [KAYAK Business Class to Accra](https://www.kayak.com/flight-routes/Business-Class-United-States-US0/Accra-Kotoka-ACC.bc.ksp)
- Amadeus API pricing: ~$0.003-$0.046 per call in production (multiple sources)
  - Source: [Amadeus Pricing](https://developers.amadeus.com/pricing)
- Going (Scott's Cheap Flights) charges $199/year for business/first class deals (validates premium differentiator)
  - Source: [The Points Guy](https://thepointsguy.com/news/scotts-cheap-flights/)

### Tertiary (LOW confidence)
- Premium cabin "normal" price estimates ($3,000-$5,000 for business to Lagos, $2,600-$4,500 for Accra) - based on aggregated search engine data, not controlled observations. These will be superseded by the silent monitoring period's actual observed prices.
- First class availability on US-Africa routes - anecdotal from search results, not verified via Amadeus API
- Exact Amadeus per-call pricing ($0.004 estimate) - could not verify the exact figure from official docs (pricing page uses JavaScript rendering)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; Amadeus SDK already supports `travelClass`; existing DB schema already has `cabin_class` column
- Architecture: HIGH - Pattern of separate orchestrator + cabin-class-aware keys is straightforward; heavily leverages existing infrastructure
- Thresholds: LOW - Premium cabin "normal" prices are estimates from search engines; real baselines require 4+ weeks of observation
- Pitfalls: HIGH - Well-understood from existing codebase analysis (API limitations, cache key collisions, budget exhaustion)

**Research date:** 2026-02-10
**Valid until:** 2026-03-10 (30 days -- stable domain, main risk is Amadeus pricing changes)
