# Phase 1: Amadeus Integration - Research

**Researched:** 2026-01-27
**Domain:** Amadeus Self-Service API (Flight Cheapest Date Search), Python SDK, GitHub Actions scheduling, cross-validation with fast-flights
**Confidence:** MEDIUM (critical caveat about cached data coverage discovered)

## Summary

The Amadeus Self-Service API provides a Flight Cheapest Date Search endpoint (`GET /v1/shopping/flight-dates`) that returns cached prices across a date range in a single API call -- exactly what this phase needs. The official Python SDK (`amadeus` v12.0.0) handles OAuth2 token management automatically, simplifying stateless GitHub Actions usage: just instantiate `Client()` each run and the SDK fetches a fresh token.

**However, a critical discovery changes the implementation plan:** The Flight Cheapest Date Search API is built on a **pre-computed cache of selected origin-destination pairs**. Not all routes are available even in production. African airports (LOS, ACC) may not be in the cache. The test environment has even more limited coverage (confirmed: US, Spain, UK, Germany, India only for some APIs). This means the code MUST handle graceful fallback when the Cheapest Date Search returns no data for a route, and should use the Flight Offers Search API (`GET /v2/shopping/flight-offers`) as a fallback for live pricing on specific dates.

**Primary recommendation:** Use the Amadeus Python SDK (`pip install amadeus`) for all API calls. Start with Flight Cheapest Date Search for efficiency (1 call = full date range), but implement Flight Offers Search as a fallback for routes not in the cache. Cross-validate ALL Amadeus prices against fast-flights (Google Flights) before alerting subscribers. Never send single-source alerts.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `amadeus` | 12.0.0 | Official Amadeus Python SDK | Handles OAuth2 automatically, typed methods, maintained by Amadeus |
| `requests` | >=2.28.0 | HTTP client (already in project) | SDK dependency, also used for manual API calls if needed |
| `fast-flights` | >=1.0.0 | Google Flights scraper (already in project) | Cross-validation source, existing codebase dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | -- | Price cache persistence | State files (price_cache.json, alert_cooldown.json) |
| `datetime` (stdlib) | -- | Date math, cooldown timing | Alert dedup, date range generation |
| `pathlib` (stdlib) | -- | File paths for state files | Consistent with existing codebase pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Amadeus SDK | Raw `requests` + manual OAuth2 | SDK handles token auto-refresh; raw requests gives more control but more code. **Use SDK.** |
| Flight Cheapest Date Search | Flight Offers Search only | Offers Search is live data but 1 call per date (26+ calls per route vs 1). Only use as fallback. |
| JSON state files | Turso database | Phase 2 handles DB migration. JSON is fine for Phase 1 (6 routes, small state). |

**Installation:**
```bash
pip install amadeus
```

Add to `requirements.txt`:
```
amadeus>=12.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
detty-flight-deals/
  amadeus_client.py       # NEW: Amadeus API wrapper (SDK-based)
  price_tracker.py        # NEW: Price change detection + caching
  amadeus_monitor.py      # NEW: Priority route coordinator
  cross_validator.py      # NEW: Amadeus vs fast-flights comparison
  price_cache.json        # NEW: Last known prices (committed)
  alert_cooldown.json     # NEW: Dedup state (committed)
  deal_finder.py          # EXISTING: Standard daily monitor (fast-flights)
  mistake_fare_monitor.py # EXISTING: RSS mistake fare monitor
  mvp0_sender.py          # EXISTING: Email sender (Google Sheets subscribers)
  .github/workflows/
    priority_monitor.yml  # NEW: Every 2 hours
    find_deals.yml        # EXISTING: Daily
    mistake_fares.yml     # EXISTING: Every 30 min
```

### Pattern 1: SDK Client with Automatic Token Management
**What:** Use the Amadeus Python SDK `Client` class which handles OAuth2 token lifecycle automatically (tokens refresh every ~30 minutes internally).
**When to use:** Every GitHub Actions run. No need to cache tokens externally.
**Example:**
```python
# Source: https://github.com/amadeus4dev/amadeus-python
from amadeus import Client, ResponseError

# SDK reads from env vars AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET
amadeus = Client()

try:
    # One call = all cheapest dates for a route
    response = amadeus.shopping.flight_dates.get(
        origin='JFK',
        destination='LOS'
    )
    # response.data is a list of flight-date objects
    for flight_date in response.data:
        print(f"{flight_date['departureDate']}: ${flight_date['price']['total']}")
except ResponseError as error:
    print(f"API error: {error}")
```

### Pattern 2: Cheapest Date Search with Offers Search Fallback
**What:** Try Flight Cheapest Date Search first (cached, 1 API call). If no data (route not in cache), fall back to Flight Offers Search (live, 1 call per date sample).
**When to use:** For every priority route check.
**Example:**
```python
# Source: https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/flights/
def get_prices_for_route(amadeus_client, origin, dest):
    """Try cached search first, fall back to live search."""
    # Attempt 1: Cheapest Date Search (1 API call, full date range)
    try:
        response = amadeus_client.shopping.flight_dates.get(
            origin=origin,
            destination=dest
        )
        if response.data:
            return parse_cheapest_dates(response.data), "cheapest_date_search"
    except ResponseError:
        pass

    # Attempt 2: Flight Offers Search (live, per-date, more API calls)
    prices = []
    sample_dates = generate_sample_dates()  # e.g., every 2 weeks for 6 months
    for date in sample_dates:
        try:
            response = amadeus_client.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=dest,
                departureDate=date,
                adults=1
            )
            if response.data:
                cheapest = min(response.data, key=lambda x: float(x['price']['total']))
                prices.append({
                    'departureDate': date,
                    'price': {'total': cheapest['price']['total']}
                })
        except ResponseError:
            continue
    return prices, "flight_offers_search"
```

### Pattern 3: Cross-Validation Before Alert
**What:** Never alert on single-source data. Verify Amadeus prices against fast-flights (Google Flights) before sending to subscribers.
**When to use:** Whenever Amadeus finds a deal candidate.
**Example:**
```python
def cross_validate_deal(origin, dest, departure_date, amadeus_price):
    """Verify Amadeus price against Google Flights via fast-flights."""
    from fast_flights import FlightData, Passengers, get_flights
    from deal_finder import parse_price

    return_date = (datetime.strptime(departure_date, "%Y-%m-%d") + timedelta(days=10)).strftime("%Y-%m-%d")

    try:
        result = get_flights(
            flight_data=[
                FlightData(date=departure_date, from_airport=origin, to_airport=dest),
                FlightData(date=return_date, from_airport=dest, to_airport=origin),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
        )
        if result and result.flights:
            google_prices = [parse_price(f.price) for f in result.flights if parse_price(f.price)]
            if google_prices:
                google_min = min(google_prices)
                # Allow 15% tolerance (different sources, timing, fare classes)
                tolerance = 0.15
                if abs(amadeus_price - google_min) / google_min <= tolerance:
                    return True, google_min  # Validated
                elif amadeus_price < google_min:
                    return True, google_min  # Amadeus found a better deal
                else:
                    return False, google_min  # Amadeus price suspicious (higher by >15%)
    except Exception:
        pass
    return None, None  # Could not validate (fast-flights failed)
```

### Pattern 4: State File Management (JSON Cache)
**What:** Use committed JSON files for price cache and alert cooldown state, following the same pattern as existing `seen_deals.json`.
**When to use:** Phase 1 only. Phase 2 migrates to Turso.
**Example:**
```python
import json
from pathlib import Path

PRICE_CACHE_FILE = Path(__file__).parent / "price_cache.json"

def load_price_cache():
    if not PRICE_CACHE_FILE.exists():
        return {}
    try:
        with open(PRICE_CACHE_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def save_price_cache(cache):
    with open(PRICE_CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
```

### Anti-Patterns to Avoid
- **Alerting on Amadeus-only data:** The Cheapest Date Search returns cached/trending prices, not live fares. Always cross-validate with fast-flights before alerting subscribers.
- **Assuming all routes exist in cache:** The Cheapest Date Search API may return empty data for JFK-LOS or JFK-ACC. The code MUST handle this gracefully.
- **Building custom OAuth2 token management:** The SDK handles this. Don't hand-roll token refresh logic.
- **Running Flight Offers Search for every date:** This burns API calls. Use sparingly (sample dates) as a fallback only.
- **Committing state files from overlapping workflows:** The priority monitor (every 2h) and deal finder (daily) both commit state. Use GitHub Actions concurrency groups to prevent git push conflicts.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth2 token management | Manual token fetch/refresh/expiry tracking | `amadeus.Client()` SDK | SDK auto-refreshes every 30 min, handles expiry, thread-safe |
| Amadeus API request/response | Raw `requests.get()` to Amadeus endpoints | `amadeus.shopping.flight_dates.get()` | SDK handles auth headers, error codes, response parsing |
| Deal tier classification | New tier logic in amadeus_monitor.py | Import `classify_deal()` from `deal_finder.py` | Existing function works, maintains single source of truth for thresholds |
| Email sending | New email logic in amadeus_monitor.py | Import from `mvp0_sender.py` / use existing `send_email()` from `deal_finder.py` | Existing infrastructure supports Google Sheets subscribers + Gmail SMTP |
| Price history logging | New logging in price_tracker.py | Import `log_price_search()` from `deal_finder.py` | Existing JSONL logging works, adds `source` field already |

**Key insight:** The existing codebase in `deal_finder.py` has well-tested functions for deal classification, email sending, price parsing, and history logging. The new Amadeus modules should import and reuse these rather than duplicating logic.

## Common Pitfalls

### Pitfall 1: Cheapest Date Search Returns No Data for African Routes
**What goes wrong:** API call returns empty `data` array because JFK-LOS is not in the pre-computed cache.
**Why it happens:** The Flight Cheapest Date Search API uses a machine-learning-built cache of "trending" origin-destination pairs. African routes from US airports may not be trending enough to appear in the cache, especially in the test environment (which only covers US, Spain, UK, Germany, India for some APIs).
**How to avoid:** Implement Flight Offers Search fallback from Day 1. Test with actual API credentials before assuming Cheapest Date Search will work for all 6 priority routes.
**Warning signs:** Empty `response.data` arrays, HTTP 500 errors for specific routes.

### Pitfall 2: Test Environment Has Limited/Fake Data
**What goes wrong:** Code works in test but prices are not real or routes don't exist.
**Why it happens:** Test environment (`test.api.amadeus.com`) uses cached/limited data. Production (`api.amadeus.com`) has live data but costs money after free quota.
**How to avoid:** Start on test for development, but plan to move to production environment for real monitoring. The SDK makes switching easy: `Client(hostname='production')`. Free quota carries over to production.
**Warning signs:** Prices that seem unrealistic, routes that work for MAD-BCN but fail for JFK-LOS.

### Pitfall 3: API Call Budget Blown by Offers Search Fallback
**What goes wrong:** If Cheapest Date Search fails for all 6 routes and each falls back to Flight Offers Search with 12 sample dates, that's 6 x 12 = 72 calls per scan instead of 6. At 12 scans/day, that's 864 calls/day = 25,920 calls/month (way over free tier).
**Why it happens:** Flight Offers Search is live pricing, 1 call per date, and burns through quota fast.
**How to avoid:** Track API call count per run and per month. If using Offers Search fallback, reduce sample dates (e.g., 4 dates per route instead of 12). Set a hard monthly cap with early termination. Log remaining quota.
**Warning signs:** Approaching 2,000 calls mid-month, 429 "Too many requests" errors.

### Pitfall 4: Git Push Conflicts Between Workflows
**What goes wrong:** The priority_monitor.yml (every 2h) and find_deals.yml (daily) both commit state files to the same branch. If they overlap, `git push` fails.
**Why it happens:** GitHub Actions cron schedules can overlap, especially if the daily run is slow.
**How to avoid:** Use GitHub Actions `concurrency` groups. Give each workflow a unique group name. Use `cancel-in-progress: false` so runs queue rather than cancel.
**Warning signs:** Failed workflow runs with "git push rejected" errors.

### Pitfall 5: Amadeus Excludes Major Airlines
**What goes wrong:** Amadeus Self-Service API does not include Delta, American Airlines, British Airways, or any low-cost carriers. A deal found by Amadeus may not be the actual cheapest option.
**Why it happens:** These airlines opted out of Amadeus self-service distribution.
**How to avoid:** This is exactly why cross-validation with fast-flights (Google Flights) is required. Google Flights includes ALL airlines. Amadeus is a supplementary data source, not a replacement.
**Warning signs:** Amadeus showing higher prices than Google Flights for routes dominated by Delta/AA.

### Pitfall 6: Price Format Mismatch Between Sources
**What goes wrong:** Amadeus returns prices as strings like `"892.00"` (float-formatted), while fast-flights returns `"$892"` or `"$1,234"`. Direct comparison breaks.
**Why it happens:** Different APIs, different formats.
**How to avoid:** Normalize all prices to integer cents or dollars immediately after retrieval. Amadeus: `int(float(price_data['price']['total']))`. fast-flights: use existing `parse_price()` from `deal_finder.py`.
**Warning signs:** Comparison logic always showing mismatch, deals being filtered incorrectly.

## Code Examples

### Complete SDK Initialization and Cheapest Date Search
```python
# Source: https://amadeus4dev.github.io/amadeus-python/
# Source: https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search
from amadeus import Client, ResponseError
import os

def create_amadeus_client():
    """Create Amadeus client. SDK reads AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET from env."""
    return Client(
        # hostname='test' is default; switch to 'production' for real data
        hostname=os.environ.get('AMADEUS_HOSTNAME', 'test'),
        log_level='warn'  # 'debug' for development, 'silent' for production
    )

def search_cheapest_dates(client, origin, dest):
    """Search cheapest dates for a route. Returns list of {departureDate, returnDate, price}."""
    try:
        response = client.shopping.flight_dates.get(
            origin=origin,
            destination=dest
        )
        return response.data  # List of flight-date objects
    except ResponseError as error:
        print(f"Amadeus error for {origin}-{dest}: {error}")
        return []
```

### Response Data Structure (Flight Cheapest Date Search)
```json
{
  "meta": {
    "currency": "USD",
    "defaults": {
      "departureDate": "2026-02-01,2026-08-01",
      "oneWay": false,
      "duration": "1,15",
      "nonStop": false,
      "viewBy": "DATE"
    }
  },
  "data": [
    {
      "type": "flight-date",
      "origin": "JFK",
      "destination": "LOS",
      "departureDate": "2026-07-15",
      "returnDate": "2026-07-25",
      "price": {
        "total": "892.00"
      },
      "links": {
        "flightDestinations": "https://...",
        "flightOffers": "https://..."
      }
    }
  ],
  "dictionaries": {
    "currencies": {"USD": "US DOLLAR"},
    "locations": {
      "JFK": {"subType": "AIRPORT", "detailedName": "JOHN F KENNEDY INTL"}
    }
  }
}
```

### Flight Offers Search Fallback
```python
# Source: https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search
def search_offers_for_date(client, origin, dest, departure_date):
    """Get live flight offers for a specific date. More expensive API call."""
    try:
        response = client.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=dest,
            departureDate=departure_date,
            adults=1,
            max=5,  # Limit results to save bandwidth
            currencyCode='USD'
        )
        if response.data:
            cheapest = min(response.data, key=lambda x: float(x['price']['total']))
            return {
                'departureDate': departure_date,
                'price': {'total': cheapest['price']['total']},
                'source': 'flight_offers_search'
            }
    except ResponseError as error:
        print(f"Offers search error {origin}-{dest} {departure_date}: {error}")
    return None
```

### GitHub Actions Workflow with Concurrency
```yaml
# Source: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions
name: Priority Route Monitor (Amadeus)

on:
  schedule:
    - cron: '15 */2 * * *'  # Every 2 hours, at :15 past (avoid top-of-hour congestion)
  workflow_dispatch:

concurrency:
  group: priority-monitor
  cancel-in-progress: false  # Queue, don't cancel - state files need to be committed

permissions:
  contents: write

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run priority monitor
        env:
          AMADEUS_CLIENT_ID: ${{ secrets.AMADEUS_CLIENT_ID }}
          AMADEUS_CLIENT_SECRET: ${{ secrets.AMADEUS_CLIENT_SECRET }}
          AMADEUS_HOSTNAME: test  # Change to 'production' when ready
          SMTP_EMAIL: ${{ secrets.SMTP_EMAIL }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          NOTIFY_EMAIL: ${{ secrets.NOTIFY_EMAIL }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          GOOGLE_SHEETS_CREDS: ${{ secrets.GOOGLE_SHEETS_CREDS }}
        run: python amadeus_monitor.py

      - name: Commit state files
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git pull --rebase origin main || true
          git add price_cache.json alert_cooldown.json 2>/dev/null || true
          git diff --staged --quiet || git commit -m "Update priority monitor state [skip ci]"
          git push || true
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw `requests` + manual OAuth2 | `amadeus` Python SDK (v12.0.0) | SDK available since 2019, v12 March 2025 | Auto token management, typed methods, error handling |
| Test environment for monitoring | Production environment with free quota | Always available | Test has limited/cached data; production has real data with same free quota |
| Flight Cheapest Date Search only | Cheapest Date + Offers Search fallback | API limitation has always existed | Cache-based API may not have African routes; need live fallback |
| Manual price threshold checks | Existing `classify_deal()` in deal_finder.py | Already in codebase | Reuse, don't rebuild |

**Deprecated/outdated:**
- The design doc mentions `BASE_URL = "https://test.api.amadeus.com"` with raw `requests`. Use the SDK instead -- it handles hostname switching via `Client(hostname='production')`.
- The design doc mentions `BUTTONDOWN_API_KEY` for email. The codebase has since switched to Google Sheets subscribers via `mvp0_sender.py`. Update the workflow env vars accordingly.

## Open Questions

1. **Does Cheapest Date Search have JFK-LOS / JFK-ACC in its cache?**
   - What we know: The API uses pre-computed caches of "trending" routes. African routes from US are niche. Test environment has very limited coverage.
   - What's unclear: Whether these specific routes exist in the production cache. Only testing with real credentials will reveal this.
   - Recommendation: Build the fallback to Flight Offers Search from Day 1. Test Cheapest Date Search first for each route and log which routes have cache coverage. Accept that some/all routes may need the more expensive Offers Search path.

2. **Exact free tier quota for Flight Cheapest Date Search**
   - What we know: Amadeus free tier ranges from 200 to 10,000 calls/month depending on the API. The design doc assumes 2,000.
   - What's unclear: The exact number for this specific API. It's only visible in the Amadeus developer workspace after creating an account.
   - Recommendation: Check quota in the dashboard after signing up. Build call tracking/logging to monitor usage. If quota is lower than expected, reduce check frequency or number of routes.

3. **Test vs Production environment for actual monitoring**
   - What we know: Test env has limited/cached data and is "exclusively intended for development purposes." Production has real data but charges beyond free quota.
   - What's unclear: Whether test environment returns useful data for US-Africa routes at all.
   - Recommendation: Develop against test, but plan to switch to production early. The SDK makes this a one-line change: `Client(hostname='production')`. Free quota applies in both environments.

4. **Amadeus price accuracy for one-way vs round-trip**
   - What we know: Cheapest Date Search supports `oneWay` parameter. The existing codebase searches round-trip with 10-day trips.
   - What's unclear: Whether Amadeus round-trip prices are comparable to Google Flights round-trip prices (different fare classes, different aggregation).
   - Recommendation: Log both Amadeus and Google Flights prices for the same route/date to build comparison data during the first week of operation.

5. **Priority route selection**
   - What we know: Design doc specifies 6 routes: JFK-LOS, JFK-ACC, EWR-LOS, EWR-ACC, IAD-LOS, IAD-ACC.
   - What's unclear: Whether these are the best 6 given API limitations. NYC (city code) might work better than JFK/EWR separately.
   - Recommendation: Try city codes (NYC instead of JFK+EWR) where available -- this halves the API calls for the same coverage. But verify Amadeus supports city codes for US airports in this API.

6. **Cross-validation timing**
   - What we know: fast-flights (Google Flights) and Amadeus may return different prices because they check at different times. Prices change hourly.
   - What's unclear: How much tolerance to allow when comparing prices from two sources checked minutes apart.
   - Recommendation: Start with 15% tolerance. If Amadeus price is within 15% of Google Flights price, consider it validated. Log all comparisons to tune this threshold over time.

## Sources

### Primary (HIGH confidence)
- [Amadeus Python SDK Reference (v8.0.0 docs)](https://amadeus4dev.github.io/amadeus-python/) - Client initialization, flight_dates.get(), flight_offers_search.get(), Response object
- [Amadeus Python SDK GitHub (v12.0.0)](https://github.com/amadeus4dev/amadeus-python) - Installation, environment variables, error handling, method mapping
- [Flight Cheapest Date Search API docs](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search) - Parameters, response format, cache behavior
- [Amadeus Code Examples - Response JSON](https://github.com/amadeus4dev/amadeus-code-examples/blob/master/flight_cheapest_date_search/v1/get/response.json) - Verified response structure
- [GitHub Actions Concurrency docs](https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions) - Concurrency groups, cancel-in-progress
- [Amadeus Rate Limits guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/api-rate-limits/) - 10 req/sec (test), 40 req/sec (production)
- [PyPI amadeus package](https://pypi.org/project/amadeus/) - v12.0.0, released March 11, 2025

### Secondary (MEDIUM confidence)
- [Amadeus Test Data guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/test-data/) - Test environment limited to US/Spain/UK/Germany/India for some APIs
- [Amadeus Flight APIs Tutorial](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/resources/flights/) - Cheapest Date Search uses pre-computed cache; not all routes available even in production
- [Amadeus OAuth2 Authorization guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/API-Keys/authorization/) - Token expires in ~30 minutes, SDK handles auto-refresh
- [Amadeus Pricing guide](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/pricing/) - Free quota per API varies 200-10,000; production charges $0.003-$0.046 per call beyond quota
- Existing codebase (`deal_finder.py`, `mistake_fare_monitor.py`, `mvp0_sender.py`) - Verified code patterns for deal classification, email, state management

### Tertiary (LOW confidence)
- Design doc claim of "2,000 free calls/month" - Cannot verify exact number; Amadeus only shows quota in developer workspace dashboard after account creation. Range is 200-10,000 depending on API.
- African route availability in Cheapest Date Search cache - No confirmation that JFK-LOS or JFK-ACC exist in the cache. Must be tested with actual credentials.
- `amadeus` SDK v12.0.0 feature set - PyPI confirms version and release date; full changelog not reviewed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Amadeus Python SDK is the official, well-documented client
- Architecture: MEDIUM - Fallback pattern (Cheapest Date -> Offers Search) is sound but untested for these specific routes
- Pitfalls: HIGH - Cache limitation is well-documented by Amadeus; git push conflicts are a known GitHub Actions issue
- Cross-validation: MEDIUM - The approach is correct but tolerance thresholds need empirical tuning
- Free tier quota: LOW - Exact number for Flight Cheapest Date Search not publicly documented

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (Amadeus SDK and API are stable; cache coverage may change)
