# Detty Flight Deals: Amadeus Continuous Monitoring

**Date:** January 19, 2026
**Status:** Ready for implementation

---

## Problem Statement

The current system runs scheduled batch searches using fast-flights (Google Flights scraping). This has limitations:

1. **Speed** - Deals can disappear before the next scheduled run
2. **Coverage** - Fixed dates/times, can't catch flexible pricing
3. **Reliability** - Scraping is fragile, rate-limited

**Goal:** Build a hybrid monitoring system that uses Amadeus API for priority routes with frequent checks, while keeping fast-flights for broader coverage on a daily schedule.

---

## Approach: Hybrid Monitoring

### Priority Routes (Amadeus API)
- **Routes:** NYC/WAS → Lagos/Accra (6 routes total)
- **Frequency:** Every 2 hours
- **Cost:** Free tier (2,000 calls/month)

### Standard Routes (fast-flights)
- **Routes:** Everything else (63 routes)
- **Frequency:** Daily
- **Cost:** Free (scraping)

This lets us validate the API approach on highest-value routes before scaling.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    DETTY DEAL ENGINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │  Priority Monitor│         │  Standard Monitor│          │
│  │  (Amadeus API)   │         │  (fast-flights)  │          │
│  │                  │         │                  │          │
│  │  • JFK/EWR/IAD   │         │  • Other origins │          │
│  │  • LOS/ACC       │         │  • Other dests   │          │
│  │  • Every 2 hours │         │  • Daily         │          │
│  └────────┬────────┘         └────────┬────────┘           │
│           │                           │                     │
│           └───────────┬───────────────┘                     │
│                       ▼                                     │
│              ┌─────────────────┐                           │
│              │  Price Tracker   │                           │
│              │  • Compare to    │                           │
│              │    cached prices │                           │
│              │  • Detect deals  │                           │
│              │  • Log history   │                           │
│              └────────┬────────┘                           │
│                       ▼                                     │
│              ┌─────────────────┐                           │
│              │  Alert System   │                           │
│              │  • Buttondown   │                           │
│              │  • Google Sheet │                           │
│              └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Priority Routes Configuration

```python
PRIORITY_ROUTES = [
    ("JFK", "LOS"),  # New York JFK → Lagos
    ("JFK", "ACC"),  # New York JFK → Accra
    ("EWR", "LOS"),  # Newark → Lagos
    ("EWR", "ACC"),  # Newark → Accra
    ("IAD", "LOS"),  # Washington Dulles → Lagos
    ("IAD", "ACC"),  # Washington Dulles → Accra
]
```

**API call budget:**
- 6 routes × 1 call each (Cheapest Date Search) = 6 calls per scan
- 2,000 free calls ÷ 6 = ~330 scans/month
- ~11 scans/day = **every 2 hours**

---

## Amadeus API Integration

### Authentication
- OAuth2 with client credentials
- Credentials stored as GitHub secrets: `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`
- Test environment (free tier) returns real prices

### Endpoints

1. **Flight Cheapest Date Search**
   - Returns cheapest prices across a date range
   - 1 call = all dates for a route
   - Endpoint: `GET /v1/shopping/flight-dates`

2. **Flight Offers Search** (future)
   - Get specific flight details
   - Use for verification before alerting

### Client Structure

```python
# amadeus_client.py

class AmadeusClient:
    BASE_URL = "https://test.api.amadeus.com"  # Test env (free)

    def __init__(self):
        self.client_id = os.environ["AMADEUS_CLIENT_ID"]
        self.client_secret = os.environ["AMADEUS_CLIENT_SECRET"]
        self.token = None
        self.token_expires = None

    def authenticate(self):
        """Get OAuth2 token."""
        response = requests.post(
            f"{self.BASE_URL}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
        )
        data = response.json()
        self.token = data["access_token"]
        self.token_expires = datetime.now() + timedelta(seconds=data["expires_in"])

    def get_cheapest_dates(self, origin: str, dest: str,
                           departure_date: str, one_way: bool = False) -> list[dict]:
        """
        Get cheapest prices across date range.
        Returns: [{"departureDate": "2026-07-15", "returnDate": "2026-07-25",
                   "price": {"total": "892.00"}}, ...]
        """
        self._ensure_token()

        response = requests.get(
            f"{self.BASE_URL}/v1/shopping/flight-dates",
            headers={"Authorization": f"Bearer {self.token}"},
            params={
                "origin": origin,
                "destination": dest,
                "departureDate": departure_date,  # Searches range from this date
                "oneWay": one_way,
                "viewBy": "DATE",
            }
        )
        return response.json().get("data", [])
```

---

## Price Change Detection

### Alert Logic

Only alert when a price becomes a deal or improves:

```python
def should_alert(new_price: int, old_price: int | None,
                 dest: str, travel_date: datetime) -> bool:
    """Only alert when price is a deal."""

    new_tier = classify_deal_tier(new_price, dest, travel_date)[0]

    # Not a deal? Don't care
    if new_tier == "Normal":
        return False

    # First time seeing a deal on this route/date
    if old_price is None:
        return True

    # Already alerted - only re-alert if tier improved
    old_tier = classify_deal_tier(old_price, dest, travel_date)[0]
    tier_rank = {"Normal": 0, "Good": 1, "Great": 2, "WOW": 3}

    return tier_rank[new_tier] > tier_rank[old_tier]
```

### Alert Triggers

1. Price enters Good/Great/WOW tier → alert
2. Price moves up a tier (Good → Great → WOW) → alert again
3. Normal price or same tier → log only, no alert

### Deduplication

Prevent alerting the same deal repeatedly:

```python
ALERT_COOLDOWN = {
    "same_tier": 24,  # hours before re-alerting same tier
    "better_tier": 0,  # alert immediately if tier improves
}
```

---

## Price Cache & History

### Price Cache (`price_cache.json`)

Stores last known price for each route/date combination:

```json
{
  "JFK-LOS:2026-07-15": {
    "price": 1150,
    "tier": "Good",
    "checked_at": "2026-01-19T14:00:00Z",
    "alerted_at": "2026-01-19T14:00:00Z"
  }
}
```

- Committed to repo (small, needed for comparison)
- Updated after every check

### Price History (`price_history.jsonl`)

All price data for future analysis (already implemented):

```json
{"searched_at": "2026-01-19T14:00:00Z", "origin": "JFK", "destination": "LOS", "travel_date": "2026-07-15", "price": 1150, "source": "amadeus", "days_until_travel": 176, "season": "jul_peak"}
```

- Gitignored (can grow large)
- Used for baseline validation in Phase 3

---

## File Structure

```
detty-flight-deals/
├── amadeus_monitor.py      # NEW: Priority route monitor
├── amadeus_client.py       # NEW: Amadeus API wrapper
├── price_tracker.py        # NEW: Price change detection & caching
├── price_cache.json        # NEW: Last known prices (committed)
├── alert_cooldown.json     # NEW: Deduplication state (committed)
├── price_history.jsonl     # EXISTS: All price data (gitignored)
├── deal_finder.py          # EXISTS: Standard monitor (fast-flights)
├── mistake_fare_monitor.py # EXISTS: RSS feed monitor
├── mvp0_sender.py          # EXISTS: Email sending
└── .github/workflows/
    ├── priority_monitor.yml  # NEW: Every 2 hours
    ├── deal_finder.yml       # EXISTS: Daily
    └── mistake_fares.yml     # EXISTS: Every 30 min
```

---

## GitHub Actions Workflow

### Priority Monitor (`.github/workflows/priority_monitor.yml`)

```yaml
name: Priority Route Monitor (Amadeus)

on:
  schedule:
    - cron: '0 */2 * * *'  # Every 2 hours
  workflow_dispatch:        # Manual trigger for testing

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
        run: pip install requests

      - name: Run priority monitor
        env:
          AMADEUS_CLIENT_ID: ${{ secrets.AMADEUS_CLIENT_ID }}
          AMADEUS_CLIENT_SECRET: ${{ secrets.AMADEUS_CLIENT_SECRET }}
          BUTTONDOWN_API_KEY: ${{ secrets.BUTTONDOWN_API_KEY }}
          SMTP_EMAIL: ${{ secrets.SMTP_EMAIL }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
        run: python amadeus_monitor.py

      - name: Commit state files
        run: |
          git config user.name "GitHub Action"
          git config user.email "action@github.com"
          git add price_cache.json alert_cooldown.json || true
          git diff --staged --quiet || git commit -m "Update price cache"
          git push || true
```

---

## Error Handling

| Issue | Handling |
|-------|----------|
| Amadeus rate limit | Back off, continue next cycle |
| Amadeus API down | Log error, skip run, retry next cycle |
| Token expired | Auto-refresh before each run |
| Invalid response | Log, skip that route, continue others |
| GitHub Action fails | Built-in retry, GitHub notification |

### Health Monitoring

- Log every run outcome
- If 3+ consecutive failures → alert admin (not subscribers)

---

## Implementation Checklist

### Phase 1: Amadeus Integration
- [ ] Sign up for Amadeus developer account (free)
- [ ] Create `amadeus_client.py` with OAuth2 and Cheapest Date Search
- [ ] Test API calls manually

### Phase 2: Price Tracking
- [ ] Create `price_tracker.py` with cache and change detection
- [ ] Create `price_cache.json` (empty initial state)
- [ ] Create `alert_cooldown.json` (empty initial state)

### Phase 3: Monitor Script
- [ ] Create `amadeus_monitor.py` that ties it together
- [ ] Import shared code from `deal_finder.py`
- [ ] Add alerting via existing email infrastructure

### Phase 4: Deployment
- [ ] Add Amadeus secrets to GitHub repo
- [ ] Create `.github/workflows/priority_monitor.yml`
- [ ] Test with manual workflow dispatch
- [ ] Enable scheduled runs

### Phase 5: Validation
- [ ] Monitor for 1 week
- [ ] Compare Amadeus prices vs fast-flights prices
- [ ] Verify alerts are accurate and not spammy
- [ ] Adjust thresholds if needed

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Uptime | 95%+ of scheduled runs succeed |
| Alert accuracy | 90%+ of alerts are real deals |
| Speed | Catch deals within 2 hours of appearing |
| Spam | <1 alert per day per subscriber (on average) |
| Subscriber growth | Track if priority route coverage increases signups |

---

## Future Expansion

Once validated:

1. **More origins** - Add ATL, DFW, IAH to priority routes
2. **More destinations** - Add Abuja, Dakar, Douala to priority
3. **Production API** - Upgrade to Amadeus production when volume justifies
4. **Multi-source** - Add Google Flights (SerpApi) for price verification
5. **More Africa** - Expand to East Africa, South Africa, eventually N. Africa

---

## Open Questions

1. **Trip length flexibility** - Currently hardcoded to 10 days. Should Amadeus monitor search for flexible trip lengths?
2. **One-way monitoring** - Some deals are one-way. Worth monitoring?
3. **Alerting channel** - Email only, or add SMS/push for WOW deals?

---

## Appendix: Amadeus Free Tier Limits

- **Test environment:** 2,000 API calls/month
- **Rate limit:** 10 requests/second
- **Data:** Real prices, labeled as "test"
- **Upgrade path:** Production environment at ~$0.01-0.02/call
