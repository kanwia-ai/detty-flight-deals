# Detty Flight Deals: Pricing Tiers Design

**Date:** January 19, 2026
**Status:** Ready for implementation

---

## Problem Statement

Users want to be told "this is a fantastic deal, book it" without needing to understand the complexities of flight pricing. They trust us to know what's good.

**The job to be done:**
> "Tell me when there's a deal good enough that I should stop what I'm doing and book travel to Africa."

**Key challenges:**
1. Deal quality is relative to *seasonality* (December prices ≠ May prices)
2. Deal quality is relative to *booking window* (same December flight is cheaper in January than November)
3. Users don't have mental price models for Africa like they do for Europe/Asia
4. We need to be accurate by Detty December booking season (August 2026)

---

## Approach: Ship Now, Get Smarter Over Time

### Phase 1: Fixed Seasonal Thresholds (Now)
- Two seasons with different baselines
- Percentage-based tier classification
- Ship immediately, start learning

### Phase 2: Background Data Collection (Now)
- Log every price searched
- Zero user-facing cost
- Build historical dataset for future accuracy

### Phase 3: Hybrid Mode (By August 2026)
- Where we have sufficient data, use historical comparison
- Fall back to fixed thresholds where we don't
- Transition gradually as data accumulates

---

## Tier Framework

**Tiers are defined as percentage below the seasonal normal price:**

| Tier | % Below Seasonal Normal | User Reaction | Alert Policy |
|------|------------------------|---------------|--------------|
| **Normal** | 0-19% | "That's typical" | Don't alert |
| **Good** | 20-29% | "Nice, worth considering" | Alert all |
| **Great** | 30-39% | "Really good, should book soon" | Alert all |
| **WOW** | 40%+ | "Book NOW, this is unheard of" | Alert premium |

**Formula:**
```python
percent_below = (seasonal_normal - price) / seasonal_normal
tier = "WOW" if percent_below >= 0.40 else \
       "Great" if percent_below >= 0.30 else \
       "Good" if percent_below >= 0.20 else \
       "Normal"
```

---

## Seasons

| Season | Dates | Driver |
|--------|-------|--------|
| **December Peak** | Dec 1 - Jan 7 | Detty December, Christmas/New Year, diaspora homecoming |
| **July Peak** | Jul 1 - Aug 15 | US summer holidays (less intense than December) |
| **Off-Peak** | Everything else | — |

**Important:** December and July peaks have **different baselines**. December demand is more extreme due to Detty December.

**Implementation:**
```python
def get_season(travel_date: date) -> str:
    month, day = travel_date.month, travel_date.day
    # December 1 - January 7
    if month == 12 or (month == 1 and day <= 7):
        return "dec_peak"
    # July 1 - August 15
    if (month == 7) or (month == 8 and day <= 15):
        return "jul_peak"
    return "off_peak"
```

---

## Alert Windows

**Critical:** Baselines represent typical prices **when booking 60-90 days out**. We only alert when the booking window is appropriate for the travel season.

| Season | Alert Window | Reason |
|--------|--------------|--------|
| **December Peak** | 90-240 days out | Book early for Detty December |
| **July Peak** | 60-180 days out | Summer travel, less extreme |
| **Off-Peak** | 45-150 days out | Standard booking window |

**Why this matters:** A December flight at $1,000 found 300 days out is **normal** (early booking discount). The same price found 100 days out is a **WOW deal**.

**Implementation:**
```python
ALERT_WINDOWS = {
    "dec_peak": (90, 240),   # 3-8 months out
    "jul_peak": (60, 180),   # 2-6 months out
    "off_peak": (45, 150),   # 1.5-5 months out
}

def in_alert_window(days_out: int, season: str) -> bool:
    min_days, max_days = ALERT_WINDOWS[season]
    return min_days <= days_out <= max_days

def should_alert(travel_date, search_date, price, dest):
    days_out = (travel_date - search_date).days
    season = get_season(travel_date)

    # Only alert within appropriate booking window
    if not in_alert_window(days_out, season):
        return False  # Too early or too late to judge

    # Within window, use standard tier classification
    baseline = get_baseline(dest, season)
    percent_below = (baseline - price) / baseline
    return percent_below >= 0.20  # Good or better
```

---

## Seasonal Normal Prices by Destination

**Note:** These baselines represent typical prices **when booking 60-90 days out**. Earlier bookings will naturally be cheaper; later bookings will be higher.

| Destination | Code | Off-Peak | July Peak | December Peak |
|-------------|------|----------|-----------|---------------|
| Lagos | LOS | $900 | $1,400 | $1,800 |
| Abuja | ABV | $900 | $1,450 | $1,850 |
| Accra | ACC | $900 | $1,150 | $1,400 |
| Dakar | DSS | $1,000 | $1,150 | $1,250 |
| Freetown | FNA | $1,100 | $1,400 | $1,600 |
| Abidjan | ABJ | $1,300 | $1,400 | $1,500 |
| Lomé | LFW | $1,200 | $1,350 | $1,500 |
| Cotonou | COO | $1,200 | $1,350 | $1,500 |
| Douala | DLA | $1,000 | $1,400 | $1,800 |
| Yaoundé | NSI | $1,000 | $1,400 | $1,800 |
| Kinshasa | FIH | $1,500 | $1,500 | $1,500 |

**Source:** Market research + user validation (January 2026)

**July vs December difference:** December has ~20-30% higher baselines than July for diaspora-heavy routes (Nigeria, Ghana, Cameroon) due to Detty December demand. Francophone and DRC routes show less December premium.

---

## Calculated Thresholds

*Good = 20% off, Great = 30% off, WOW = 40% off baseline*

### Off-Peak (Feb-Jun, Sep-Nov)

| Destination | Baseline | Good (<) | Great (<) | WOW (<) |
|-------------|----------|----------|-----------|---------|
| Lagos | $900 | $720 | $630 | $540 |
| Abuja | $900 | $720 | $630 | $540 |
| Accra | $900 | $720 | $630 | $540 |
| Dakar | $1,000 | $800 | $700 | $600 |
| Freetown | $1,100 | $880 | $770 | $660 |
| Abidjan | $1,300 | $1,040 | $910 | $780 |
| Lomé | $1,200 | $960 | $840 | $720 |
| Cotonou | $1,200 | $960 | $840 | $720 |
| Douala | $1,000 | $800 | $700 | $600 |
| Yaoundé | $1,000 | $800 | $700 | $600 |
| Kinshasa | $1,500 | $1,200 | $1,050 | $900 |

### July Peak (Jul 1 - Aug 15)

| Destination | Baseline | Good (<) | Great (<) | WOW (<) |
|-------------|----------|----------|-----------|---------|
| Lagos | $1,400 | $1,120 | $980 | $840 |
| Abuja | $1,450 | $1,160 | $1,015 | $870 |
| Accra | $1,150 | $920 | $805 | $690 |
| Dakar | $1,150 | $920 | $805 | $690 |
| Freetown | $1,400 | $1,120 | $980 | $840 |
| Abidjan | $1,400 | $1,120 | $980 | $840 |
| Lomé | $1,350 | $1,080 | $945 | $810 |
| Cotonou | $1,350 | $1,080 | $945 | $810 |
| Douala | $1,400 | $1,120 | $980 | $840 |
| Yaoundé | $1,400 | $1,120 | $980 | $840 |
| Kinshasa | $1,500 | $1,200 | $1,050 | $900 |

### December Peak (Dec 1 - Jan 7)

| Destination | Baseline | Good (<) | Great (<) | WOW (<) |
|-------------|----------|----------|-----------|---------|
| Lagos | $1,800 | $1,440 | $1,260 | $1,080 |
| Abuja | $1,850 | $1,480 | $1,295 | $1,110 |
| Accra | $1,400 | $1,120 | $980 | $840 |
| Dakar | $1,250 | $1,000 | $875 | $750 |
| Freetown | $1,600 | $1,280 | $1,120 | $960 |
| Abidjan | $1,500 | $1,200 | $1,050 | $900 |
| Lomé | $1,500 | $1,200 | $1,050 | $900 |
| Cotonou | $1,500 | $1,200 | $1,050 | $900 |
| Douala | $1,800 | $1,440 | $1,260 | $1,080 |
| Yaoundé | $1,800 | $1,440 | $1,260 | $1,080 |
| Kinshasa | $1,500 | $1,200 | $1,050 | $900 |

---

## Data Collection Schema

**Purpose:** Build historical price data for future accuracy improvements.

**Storage:** SQLite database (`price_history.db`) or JSON Lines file (`price_history.jsonl`)

**Schema:**
```sql
CREATE TABLE price_searches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    origin TEXT NOT NULL,           -- e.g., "JFK"
    destination TEXT NOT NULL,      -- e.g., "LOS"
    travel_date DATE NOT NULL,      -- departure date
    return_date DATE,               -- for round-trips
    price INTEGER NOT NULL,         -- in USD
    source TEXT,                    -- e.g., "google_flights", "fast_flights"
    days_until_travel INTEGER       -- computed: travel_date - searched_at
);

CREATE INDEX idx_route_date ON price_searches(origin, destination, travel_date);
```

**JSON Lines alternative:**
```json
{"searched_at": "2026-01-19T10:30:00Z", "origin": "JFK", "destination": "LOS", "travel_date": "2026-12-20", "return_date": "2026-12-30", "price": 1150, "source": "fast_flights", "days_until_travel": 335}
```

**Logging trigger:** Every successful price search, regardless of whether it's a deal.

---

## Phase 2: Using Collected Data (Month 3-6)

Once we have 3+ months of data, we can:

1. **Validate thresholds:** Are our fixed normals accurate? Adjust if needed.
2. **Detect patterns:** Do certain routes have different seasonality than expected?
3. **Build percentiles:** What's the 25th/50th/75th percentile price for each route/season?

**Minimum data threshold for hybrid mode:**
- 30+ price points for a given route + travel month + booking window band
- Until then, fall back to fixed thresholds

---

## Phase 3: Hybrid Classification (By August 2026)

```python
def classify_deal(price, origin, dest, travel_date, search_date):
    days_out = (travel_date - search_date).days

    # Try historical comparison first
    historical_baseline = get_historical_baseline(
        origin, dest,
        travel_month=travel_date.month,
        days_out_band=get_booking_band(days_out)
    )

    if historical_baseline:
        # Use data-driven baseline
        baseline = historical_baseline
    else:
        # Fall back to fixed thresholds
        baseline = get_seasonal_normal(dest, travel_date)

    percent_below = (baseline - price) / baseline
    return get_tier(percent_below)

def get_booking_band(days_out):
    if days_out > 120:
        return "far"      # 4+ months out
    elif days_out > 60:
        return "medium"   # 2-4 months out
    else:
        return "close"    # <2 months out
```

---

## Implementation Checklist

### Phase 1 (This Week)
- [ ] Update `DESTINATIONS` config with 3-season baselines (off-peak, jul_peak, dec_peak)
- [ ] Add `get_season()` function (returns "off_peak", "jul_peak", or "dec_peak")
- [ ] Add `in_alert_window()` function with season-specific windows
- [ ] Add `should_alert()` function that checks booking window before classifying
- [ ] Update `classify_deal_tier()` to use seasonal baseline
- [ ] Test with real price data from screenshots

### Phase 2 (This Week)
- [ ] Create `price_history.db` or `.jsonl` file
- [ ] Add logging to `search_flight()` function
- [ ] Log: origin, dest, travel_date, search_date, price, days_until_travel
- [ ] Ensure logging doesn't slow down searches

### Phase 3 (By August)
- [ ] Analyze collected data — validate baselines are accurate
- [ ] Build `get_historical_baseline()` function
- [ ] Implement hybrid classification (data-driven where available, fallback to fixed)
- [ ] Add "learning mode" for new destinations
- [ ] A/B test against fixed thresholds

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Deal accuracy | >80% of WOW deals feel like "book now" to users | User feedback, click-through rates |
| False positives | <10% of alerts are "meh" | User feedback |
| Data coverage | 30+ data points per major route by August | Query database |
| User trust | Users book deals we send | Conversion tracking |

---

## Resolved Decisions

1. **July vs December peak:** ✅ **Yes, differentiated.** December baselines are ~20-30% higher than July for diaspora-heavy routes due to Detty December demand.

2. **Booking window in Phase 1:** ✅ **Yes, via alert windows.** We only alert when travel is within the appropriate booking window for that season. This prevents spamming users with "deals" that are actually normal early-booking prices.

---

## Open Question: New Destinations

**How do we handle Tier 2 cities when we add them?**

**Recommended approach: Learning Mode**

When adding a new destination:
1. **First 30 days:** Collect prices only, don't classify as deals
2. **After 30 days:** Calculate baseline from collected data (median price)
3. **Then:** Enable deal classification with data-driven baseline

```python
def get_baseline(dest, season):
    # Check if we have enough data
    data_points = get_price_count(dest, season)

    if data_points >= 30:
        # Use learned baseline (median of collected prices)
        return get_median_price(dest, season)
    elif dest in MANUAL_BASELINES:
        # Use manually researched baseline
        return MANUAL_BASELINES[dest][season]
    else:
        # Not enough data, don't alert yet
        return None  # Signals "learning mode"
```

This ensures we don't send bad deal alerts for destinations we don't understand yet.

---

## Appendix: Research Sources

- Google Flights price checks (January 2026)
- User validation (Cameroon, Ghana, Nigeria pricing)
- Going.com, Thrifty Traveler, Hopper methodology research
- KAYAK, Momondo, Expedia seasonal pricing data
