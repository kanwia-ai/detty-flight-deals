# Phase 3: Anomaly Detection - Research

**Researched:** 2026-01-28
**Domain:** Time series anomaly detection, statistical thresholds, flight pricing patterns
**Confidence:** MEDIUM (technical stack is HIGH, domain-specific thresholds are MEDIUM due to limited public data)

## Summary

This phase replaces manual percentage thresholds with data-driven baselines for detecting flight deals. The core technical approach uses rolling z-score calculations (scipy/numpy) for anomaly detection, with level shift detection for discovering sudden price drops. Seasonal adjustments account for the significant price variations during peak travel periods like Detty December.

The standard stack combines scipy/numpy for z-score calculations and pandas for rolling window operations. For level shift detection, the CONTEXT.md specifies ADTK, but ADTK has not been updated since April 2020 and may have compatibility issues with Python 3.11+. A simpler custom implementation using pandas rolling windows is recommended as the primary approach, with ADTK as an optional fallback if it works in the target environment.

Research revealed that competitor services (Going, Thrifty Traveler, Dollar Flight Club) use 30-90% off thresholds for deals, with Going reporting average member savings of $550 on international flights and claiming deals in the 95th percentile of all fares. For Africa routes specifically, December prices spike significantly (prices roughly double) due to Detty December demand from the diaspora.

**Primary recommendation:** Use scipy/numpy for rolling z-score with z < -2.5 threshold, pandas rolling windows (90-day baseline, recalculated weekly), custom level shift detection rather than ADTK, and research-backed seasonal multipliers (+50% Dec-Jan based on market data showing prices roughly double).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scipy | 1.11+ | `scipy.stats.zscore` for z-score calculations | Industry standard, well-documented, stable API |
| numpy | 1.24+ | Array operations, numerical computations | Foundation for scipy, universal in data science |
| pandas | 2.0+ | Rolling window calculations, time series handling | `rolling().mean()`, `rolling().std()` for 90-day baselines |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| adtk | 0.6.2 | LevelShiftAD detector | OPTIONAL: Only if confirmed working with Python 3.11+ |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ADTK LevelShiftAD | Custom pandas-based level shift | ADTK unmaintained since 2020; custom is simpler, testable |
| scipy.stats.zscore | Custom z-score function | scipy is battle-tested; no need to hand-roll |
| Rolling z-score | Isolation Forest (sklearn) | Z-score is simpler, interpretable, sufficient for this use case |

**Installation:**
```bash
pip install scipy numpy pandas
# Optional: pip install adtk (test compatibility first)
```

## Architecture Patterns

### Recommended Project Structure
```
detty-flight-deals/
├── anomaly/
│   ├── __init__.py
│   ├── anomaly_detector.py    # Rolling z-score calculations
│   ├── baseline_calculator.py # 90-day rolling baselines per route
│   ├── level_shift_detector.py # Sudden price drop detection
│   └── seasonal_adjustments.py # Month-based threshold multipliers
├── deal_finder.py             # Modified to use anomaly detection
├── price_tracker.py           # Existing - provides data
└── db/                        # Existing - stores observations
```

### Pattern 1: Rolling Z-Score Detector
**What:** Calculate z-scores using rolling mean/std instead of global statistics
**When to use:** Detecting anomalously cheap fares against historical baselines
**Why rolling:** Global z-scores don't capture seasonality; rolling windows adapt to recent trends
**Example:**
```python
# Source: scipy/pandas documentation patterns
import pandas as pd
import numpy as np

def rolling_zscore(prices: pd.Series, window: int = 90, min_periods: int = 30) -> pd.Series:
    """
    Calculate rolling z-score for price series.

    Args:
        prices: Time series of prices (cents)
        window: Rolling window size in observations
        min_periods: Minimum observations required

    Returns:
        Z-scores where negative = below average (potential deal)
    """
    rolling_mean = prices.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = prices.rolling(window=window, min_periods=min_periods).std()

    # Prevent division by zero
    rolling_std = rolling_std.replace(0, np.nan)

    z_score = (prices - rolling_mean) / rolling_std
    return z_score


def is_anomaly(z_score: float, threshold: float = -2.5) -> bool:
    """
    Check if z-score indicates an anomalously cheap fare.

    z < -2.5 means price is 2.5 standard deviations below rolling mean.
    This catches roughly the bottom 0.6% of price distribution.
    """
    return z_score < threshold
```

### Pattern 2: Custom Level Shift Detection (Simpler than ADTK)
**What:** Detect sudden price drops by comparing short-term vs long-term medians
**When to use:** Discovering "mistake fares" or exceptional sudden deals
**Why custom:** ADTK unmaintained; this approach is transparent, testable, dependency-light
**Example:**
```python
# Source: ADTK LevelShiftAD concept, implemented with pandas
def detect_level_shift(
    prices: pd.Series,
    short_window: int = 3,
    long_window: int = 14,
    threshold_pct: float = 0.40
) -> bool:
    """
    Detect if recent prices represent a level shift (sudden drop).

    Compares median of recent short window vs previous long window.
    A 40%+ drop from the previous baseline indicates potential mistake fare.

    Args:
        prices: Time series of prices (most recent last)
        short_window: Recent observations to compare (e.g., last 3 checks)
        long_window: Baseline period (e.g., previous 14 observations)
        threshold_pct: Percentage drop to trigger (0.40 = 40% drop)

    Returns:
        True if level shift detected (exceptional deal)
    """
    if len(prices) < short_window + long_window:
        return False

    recent_median = prices.iloc[-short_window:].median()
    baseline_median = prices.iloc[-(short_window + long_window):-short_window].median()

    if baseline_median == 0:
        return False

    drop_pct = (baseline_median - recent_median) / baseline_median
    return drop_pct >= threshold_pct
```

### Pattern 3: Hybrid Cold Start Handling
**What:** Fall back to static thresholds when insufficient historical data
**When to use:** New routes with <30 observations
**Example:**
```python
# Source: DISC-06 requirement
def classify_deal_hybrid(
    price_cents: int,
    route: str,
    historical_prices: pd.Series | None,
    static_thresholds: dict
) -> dict | None:
    """
    Classify deals using z-score when data exists, static thresholds otherwise.

    Args:
        price_cents: Current price in cents
        route: Route string e.g., "JFK-LOS"
        historical_prices: Past prices for this route (or None)
        static_thresholds: Fallback thresholds per destination

    Returns:
        Deal classification dict or None if not a deal
    """
    # Check if we have enough history for z-score
    if historical_prices is not None and len(historical_prices) >= 30:
        z_score = rolling_zscore(historical_prices).iloc[-1]

        if z_score < -2.5:
            # Additional absolute floor check
            dest = route.split("-")[1]
            floor = static_thresholds.get(dest, {}).get("wow", 0) * 100  # cents

            if price_cents <= floor:
                return {"tier": "exceptional", "method": "zscore", "z": z_score}
            else:
                return {"tier": "great", "method": "zscore", "z": z_score}

        return None  # Not anomalous

    # Cold start: use static thresholds
    dest = route.split("-")[1]
    thresholds = static_thresholds.get(dest)
    if not thresholds:
        return None

    price_dollars = price_cents / 100

    if price_dollars < thresholds["wow"]:
        return {"tier": "wow", "method": "static"}
    elif price_dollars < thresholds["great"]:
        return {"tier": "great", "method": "static"}
    elif price_dollars < thresholds["good"]:
        return {"tier": "good", "method": "static"}

    return None
```

### Anti-Patterns to Avoid
- **Global z-scores:** Don't use entire price history for mean/std - seasonal patterns will skew results
- **Too small rolling windows:** <30 observations leads to unstable z-scores; use min_periods
- **Ignoring seasonality:** A "good" December price is not the same as a "good" March price
- **Complex ML for simple problems:** Z-score is interpretable and sufficient; Isolation Forest/autoencoders are overkill

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Z-score calculation | Custom mean/std/zscore | `scipy.stats.zscore` or pandas `.rolling().mean()/.std()` | Edge cases (empty data, single value, zeros) handled |
| Rolling windows | Manual array slicing | `pandas.Series.rolling()` | Handles min_periods, NaN, time-based windows |
| Statistical significance | Custom p-value calculations | scipy.stats | Well-tested, handles edge cases |

**Key insight:** The goal is interpretable deal detection, not academic novelty. Z-score is well-understood, debuggable, and sufficient for this use case.

## Common Pitfalls

### Pitfall 1: Forgetting min_periods in Rolling Calculations
**What goes wrong:** New routes produce z-scores from 1-2 observations, causing false positives
**Why it happens:** pandas rolling with window=90 will calculate from observation 1
**How to avoid:** Always specify `min_periods=30` in rolling calculations
**Warning signs:** Brand new routes immediately flagging deals

### Pitfall 2: Not Handling Zero Standard Deviation
**What goes wrong:** Division by zero when all prices in window are identical
**Why it happens:** Low-volume routes may have same price for extended periods
**How to avoid:** Replace std=0 with np.nan, skip z-score classification
**Warning signs:** RuntimeWarning division by zero, or inf/-inf z-scores

### Pitfall 3: Seasonal Distortion of Baselines
**What goes wrong:** December baseline includes cheap January prices, making December prices look normal
**Why it happens:** 90-day rolling window spans multiple seasons
**How to avoid:** Apply seasonal multipliers BEFORE comparison, or use seasonally-adjusted baselines
**Warning signs:** Missing obvious December deals that are 50%+ above January prices

### Pitfall 4: ADTK Compatibility Issues
**What goes wrong:** Import errors, unexpected behavior on Python 3.11+
**Why it happens:** ADTK last updated April 2020, tested only on Python 3.5-3.8
**How to avoid:** Test ADTK in target environment first; use custom level shift detection as primary
**Warning signs:** ImportError, AttributeError, unexpected NaN results

### Pitfall 5: Confusing Price Units (Dollars vs Cents)
**What goes wrong:** Z-scores calculated on dollars, thresholds in cents, comparisons fail
**Why it happens:** Mixed units across codebase
**How to avoid:** Store everything in cents (INTEGER in database per Phase 2 decision); convert only for display
**Warning signs:** Deals classified wrong by 100x factor

## Code Examples

### Verified Rolling Z-Score Implementation
```python
# Source: scipy.stats.zscore docs + pandas rolling docs
import pandas as pd
import numpy as np
from scipy import stats

class AnomalyDetector:
    """
    Anomaly detection for flight prices using rolling z-scores.

    DISC-04: Detects anomalously cheap fares via rolling z-score (z < -2.5)
    """

    def __init__(
        self,
        window: int = 90,
        min_periods: int = 30,
        z_threshold: float = -2.5
    ):
        self.window = window
        self.min_periods = min_periods
        self.z_threshold = z_threshold

    def calculate_rolling_zscore(self, prices: pd.Series) -> pd.Series:
        """
        Calculate rolling z-score for price series.

        Z-score formula: (x - mean) / std
        Negative z-score means price is below average.
        z < -2.5 is approximately the bottom 0.6% of distribution.
        """
        rolling_mean = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).mean()

        rolling_std = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).std()

        # Handle zero std (constant prices)
        rolling_std = rolling_std.replace(0, np.nan)

        z_scores = (prices - rolling_mean) / rolling_std
        return z_scores

    def is_anomaly(self, z_score: float) -> bool:
        """Check if z-score indicates anomalous cheap fare."""
        if pd.isna(z_score):
            return False
        return z_score < self.z_threshold

    def detect(self, prices: pd.Series) -> dict:
        """
        Run detection on price series.

        Returns:
            {
                "is_anomaly": bool,
                "z_score": float or None,
                "method": "zscore" or "insufficient_data",
                "rolling_mean": float,
                "rolling_std": float
            }
        """
        if len(prices) < self.min_periods:
            return {
                "is_anomaly": False,
                "z_score": None,
                "method": "insufficient_data",
                "rolling_mean": None,
                "rolling_std": None
            }

        z_scores = self.calculate_rolling_zscore(prices)
        latest_z = z_scores.iloc[-1]

        rolling_mean = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).mean().iloc[-1]

        rolling_std = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).std().iloc[-1]

        return {
            "is_anomaly": self.is_anomaly(latest_z),
            "z_score": float(latest_z) if not pd.isna(latest_z) else None,
            "method": "zscore",
            "rolling_mean": float(rolling_mean) if not pd.isna(rolling_mean) else None,
            "rolling_std": float(rolling_std) if not pd.isna(rolling_std) else None
        }
```

### Seasonal Adjustment Implementation
```python
# Source: Research findings on Africa flight seasonality
from datetime import datetime
from typing import Optional

class SeasonalAdjuster:
    """
    Apply seasonal threshold adjustments to avoid false positives during peak travel.

    DISC-07: Seasonal adjustments based on research:
    - Dec-Jan: +50% (Detty December - prices roughly double)
    - Jun-Aug: +25% (Summer vacation season)

    These multipliers raise the "deal threshold" during peak seasons,
    so a $900 fare in December is treated like a $600 fare in March.
    """

    # Research-backed multipliers
    # Source: Market research showing December prices ~2x normal
    SEASONAL_MULTIPLIERS = {
        1: 1.50,   # January (Detty December spillover)
        2: 1.00,   # February (shoulder)
        3: 1.00,   # March (shoulder)
        4: 1.00,   # April (shoulder)
        5: 1.00,   # May (shoulder)
        6: 1.25,   # June (summer starts)
        7: 1.25,   # July (peak summer)
        8: 1.25,   # August (peak summer)
        9: 1.00,   # September (cheapest)
        10: 1.00,  # October (cheapest)
        11: 1.00,  # November (shoulder)
        12: 1.50,  # December (Detty December peak)
    }

    @classmethod
    def get_multiplier(cls, travel_date: datetime) -> float:
        """Get seasonal multiplier for a travel date."""
        return cls.SEASONAL_MULTIPLIERS.get(travel_date.month, 1.0)

    @classmethod
    def adjust_threshold(
        cls,
        base_threshold: int,
        travel_date: datetime
    ) -> int:
        """
        Adjust a price threshold for seasonality.

        Example: $700 WOW threshold in December becomes $1050
        (because $1050 in December is like $700 in March)

        Args:
            base_threshold: Base threshold in cents
            travel_date: Travel departure date

        Returns:
            Seasonally-adjusted threshold in cents
        """
        multiplier = cls.get_multiplier(travel_date)
        return int(base_threshold * multiplier)

    @classmethod
    def normalize_price(
        cls,
        price_cents: int,
        travel_date: datetime
    ) -> int:
        """
        Normalize a price to remove seasonal effects.

        This allows comparing prices across seasons.
        A $1050 December price normalizes to $700 (divided by 1.5).

        Args:
            price_cents: Actual price in cents
            travel_date: Travel departure date

        Returns:
            Seasonally-normalized price in cents
        """
        multiplier = cls.get_multiplier(travel_date)
        return int(price_cents / multiplier)
```

### Cold Start Static Thresholds
```python
# Source: pm-docs/pricing-tiers.md (existing research)
# These are used when <30 observations exist for z-score calculation

STATIC_THRESHOLDS = {
    # Nigeria (highest diaspora demand)
    "LOS": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    "ABV": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    # Ghana
    "ACC": {"normal": 1100, "good": 850, "great": 650, "wow": 650},
    # Senegal
    "DSS": {"normal": 1000, "good": 750, "great": 550, "wow": 550},
    # Sierra Leone
    "FNA": {"normal": 1100, "good": 900, "great": 700, "wow": 700},
    # Ivory Coast
    "ABJ": {"normal": 1300, "good": 1000, "great": 800, "wow": 800},
    # Togo
    "LFW": {"normal": 1300, "good": 1000, "great": 750, "wow": 750},
    # Benin
    "COO": {"normal": 1200, "good": 900, "great": 700, "wow": 700},
    # Cameroon
    "DLA": {"normal": 1000, "good": 800, "great": 600, "wow": 600},
    "NSI": {"normal": 1000, "good": 800, "great": 600, "wow": 600},
    # DRC
    "FIH": {"normal": 1500, "good": 1100, "great": 850, "wow": 850},
}

# Exceptional deal absolute floors (research-based historical lows)
# Anything below this is "too good to be true" - likely mistake fare territory
# Source: pm-docs/pricing-tiers.md "Best recent deals" data
EXCEPTIONAL_FLOORS = {
    "LOS": 500,  # Historical lows around $685-800, $500 would be exceptional
    "ABV": 500,
    "ACC": 450,  # Historical lows around $700-850
    "DSS": 350,  # Historical lows around $400-600 (direct flights)
    "FNA": 500,
    "ABJ": 600,
    "LFW": 400,  # Historical lows around $500-800
    "COO": 550,
    "DLA": 400,  # Historical lows around $570-800
    "NSI": 400,
    "FIH": 600,  # Historical lows around $700-950
}
```

## Competitor Threshold Research

### Going (formerly Scott's Cheap Flights)
- **Deal standard:** 30-90% off typical fares, average 45% off
- **Member savings:** Average $550 on international economy, $200 domestic
- **Quality filter:** Only send deals in 95th percentile of all fares
- **Peak season guidance:** Add ~25% to off-season price for solid peak fare
- **Source:** [Going Deal Report](https://www.going.com/guides/going-deal-report), [Going 2026 State of Travel](https://www.going.com/guides/state-of-travel-2026)

### Thrifty Traveler
- **Deal standard:** 50-90% off claimed
- **Focus:** Quality over quantity - "truly exceptional opportunities"
- **Source:** [Thrifty Traveler Review](https://thepointsparty.com/articles/thrifty-traveler-vs-dollar-flight-club)

### Expedia Flight Deals
- **Threshold:** 20% less than typical predicted price
- **Additional criteria:** Max 1 stop, layovers under 8 hours
- **Source:** [Expedia Flight Deals](https://www.expedia.com/product/flight-deals/)

### Summary for Detty Thresholds
| Tier | Percentage Off | Z-Score Equivalent | Notes |
|------|----------------|-------------------|-------|
| Good | 20-30% | z < -1.5 | Matches Expedia's 20% threshold |
| Great | 35-45% | z < -2.0 | Going's average savings |
| WOW/Exceptional | 50%+ | z < -2.5 | Rare, mistake fare territory |

## Africa Route Seasonality Research

### Peak Seasons (Price Increases)
| Period | Events | Price Impact | Source |
|--------|--------|--------------|--------|
| December | Detty December, homecoming | +50-100% (prices roughly double) | [CNN](https://www.cnn.com/2025/12/19/travel/detty-december-nigeria-party-problems), [Naija247](https://naija247news.com/detty-december-2025-flight-prices-skyrocket-nigerians-abroad-struggle-to-return-home/) |
| January | Detty spillover, Year of Return | +30-50% | Market research |
| July-August | Summer vacation, school holidays | +25% | [ASAP Tickets](https://blog.asaptickets.com/cheapest-time-to-travel-to-africa/) |
| October 1 | Nigeria Independence Day | Moderate spike | Calendar data |

### Cheap Seasons
| Period | Why Cheap | Best For | Source |
|--------|-----------|----------|--------|
| September | Lowest demand, rainy season | All routes | [Going](https://www.going.com/flights/to/nigeria) |
| October | Shoulder season | All routes | Market research |
| February | Post-holiday lull | All routes | [ASAP Tickets](https://blog.asaptickets.com/cheapest-time-to-travel-to-africa/) |
| April-May | Before summer spike | All routes | Market research |

### Diaspora Travel Events (Beyond Detty December)
| Event | Timing | Impact | Notes |
|-------|--------|--------|-------|
| Detty December | Dec-Jan | Major | Nigeria, Ghana homecoming |
| Easter | March-April | Moderate | Religious travel, weddings |
| Osun-Osogbo Festival | August | Regional | Nigeria (Osogbo) |
| Ghana Panafest | December (biennial) | Moderate | Diaspora cultural event |
| Africa Day | May 25 | Minor | 9 African countries |
| Eid celebrations | Variable | Moderate | Nigeria (Kano, Sokoto) |

## Mistake Fare Signals

### How to Identify Likely Mistake Fares
| Signal | Indicator | Confidence |
|--------|-----------|------------|
| Price drop magnitude | 50-90% below normal | HIGH |
| Sudden appearance | Price drops in hours, not days | HIGH |
| Cross-source variance | Amadeus shows $200, Google shows $1200 | HIGH |
| Missing fuel surcharge | Multi-stop routes with suspiciously low prices | MEDIUM |
| Currency anomalies | Unusual currency or exchange rate | MEDIUM |
| Duration | Disappears within 24-48 hours | HIGH (confirms it was error) |

### Mistake Fare Statistics
- **Honor rate:** ~70% of mistake fares are honored
- **Cancellation window:** Usually within 24-72 hours
- **Savings:** Up to 90% off standard prices
- **Source:** [Going Mistake Fares Guide](https://www.going.com/guides/mistake-fares), [Dollar Flight Club](https://dollarflightclub.com/articles/what-are-error-fares-and-how-to-find-them/)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed percentage thresholds | Rolling z-score | Industry trend | Adapts to market conditions |
| Global statistics | Rolling windows | Best practice | Captures seasonality, trends |
| Manual threshold tuning | Data-driven baselines | Phase 3 goal | Less maintenance, more accurate |
| ADTK for level shift | Custom pandas implementation | 2025+ | ADTK unmaintained, simpler is better |

**Deprecated/outdated:**
- ADTK (0.6.2, April 2020): Last update was nearly 6 years ago, Python 3.11+ compatibility uncertain
- Static-only thresholds: Fail to adapt to market changes, seasonal patterns
- Global z-scores: Don't account for seasonality or market trends

## Open Questions

1. **ADTK Python 3.11+ Compatibility**
   - What we know: ADTK last updated April 2020, tested on Python 3.5-3.8
   - What's unclear: Whether it works reliably on modern Python
   - Recommendation: Test in target environment; use custom level shift detection as primary

2. **Optimal Rolling Window Size**
   - What we know: 90 days is standard, captures seasonal quarter
   - What's unclear: Is 90 days optimal for Africa routes with less frequent monitoring?
   - Recommendation: Start with 90 days, adjust based on data density

3. **Z-Score Threshold Tuning**
   - What we know: z < -2.5 captures bottom ~0.6% of distribution
   - What's unclear: Optimal threshold for balancing false positives vs missing deals
   - Recommendation: Start with -2.5, track precision/recall, adjust iteratively

4. **Seasonal Multiplier Calibration**
   - What we know: December prices roughly double, summer +25%
   - What's unclear: Exact multipliers per destination (Lagos vs Nairobi may differ)
   - Recommendation: Start with uniform multipliers, refine with historical data

5. **Cross-Route Learning for Cold Start**
   - What we know: JFK-LOS data could inform EWR-LOS baselines
   - What's unclear: How similar are routes from nearby origins?
   - Recommendation: Phase 4 enhancement - start with per-route only

## Sources

### Primary (HIGH confidence)
- [scipy.stats.zscore Documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html) - Z-score calculation
- [pandas Rolling Documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html) - Rolling window operations
- `pm-docs/pricing-tiers.md` - Existing threshold research for all destinations

### Secondary (MEDIUM confidence)
- [Going Deal Report](https://www.going.com/guides/going-deal-report) - Competitor threshold criteria
- [Going 2026 State of Travel](https://www.going.com/guides/state-of-travel-2026) - Market conditions
- [ADTK LevelShiftAD Documentation](https://adtk.readthedocs.io/en/stable/notebooks/demo.html) - Level shift detection concept
- [ADTK GitHub](https://github.com/arundo/adtk) - Maintenance status (inactive since 2020)
- [CNN Detty December](https://www.cnn.com/2025/12/19/travel/detty-december-nigeria-party-problems) - Seasonal price patterns
- [Going Mistake Fares Guide](https://www.going.com/guides/mistake-fares) - Mistake fare signals

### Tertiary (LOW confidence)
- [ADTK Snyk Analysis](https://snyk.io/advisor/python/adtk) - Package health assessment
- WebSearch results on African diaspora travel patterns - General patterns, limited quantitative data
- WebSearch results on historical flight prices - Current prices only, no historical data found

## Metadata

**Confidence breakdown:**
- Standard stack (scipy/numpy/pandas): HIGH - Official documentation, widely used
- Rolling z-score approach: HIGH - Well-established statistical method
- ADTK viability: LOW - Unmaintained since 2020, compatibility uncertain
- Seasonal multipliers: MEDIUM - Based on market reports, not primary data
- Competitor thresholds: MEDIUM - Some services don't disclose specific criteria

**Research date:** 2026-01-28
**Valid until:** 2026-03-28 (60 days - statistical methods are stable, seasonal data may need refresh for next December)
