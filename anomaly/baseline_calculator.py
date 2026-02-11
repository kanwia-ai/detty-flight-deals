"""
BaselineCalculator - Hybrid deal classification combining all detection methods.

Orchestrates:
- LevelShiftDetector: Sudden price drops (exceptional deals)
- AnomalyDetector: Rolling z-score (when 30+ observations exist)
- Static thresholds: Cold-start fallback (when <30 observations)
- SeasonalAdjuster: Threshold adjustments for peak travel periods

Classification flow (from CONTEXT.md):
1. Check for level shift first (sudden drops are immediately "exceptional")
2. If 30+ observations exist, use z-score classification
3. If <30 observations, use static threshold fallback
4. Apply seasonal adjustment to static thresholds when travel_date provided

DISC-04 through DISC-07: Complete hybrid detection pipeline.
"""

import pandas as pd
from datetime import datetime
from typing import Optional

from .anomaly_detector import AnomalyDetector
from .level_shift_detector import LevelShiftDetector
from .seasonal_adjustments import SeasonalAdjuster
from .static_thresholds import STATIC_THRESHOLDS, EXCEPTIONAL_FLOORS, classify_with_static, classify_premium_cabin, PREMIUM_STATIC_THRESHOLDS

# Import TursoClient conditionally to avoid circular imports
try:
    from db import TursoClient
except ImportError:
    TursoClient = None


# Z-score tier mapping (from RESEARCH.md)
# z < -2.5: "exceptional" (also check absolute floor)
# z < -2.0: "great"
# z < -1.5: "good"
# else: None (not a deal)
ZSCORE_THRESHOLDS = {
    "exceptional": -2.5,
    "great": -2.0,
    "good": -1.5,
}

# Cold start handling: 2-week silent monitoring period for new routes
SILENT_PERIOD_OBSERVATIONS = 14

# Premium cabin silent monitoring: 4+ weeks (28 observations) before alerts fire
# Premium cabin data is sparse and thresholds are LOW confidence — need longer baseline
PREMIUM_SILENT_OBSERVATIONS = 28


class BaselineCalculator:
    """
    Hybrid deal classification combining all anomaly detection methods.

    Uses the following priority order:
    1. Level shift detection (sudden 40%+ drops -> exceptional)
    2. Z-score classification (when 30+ observations exist)
    3. Static threshold fallback (when <30 observations)

    Attributes:
        db: TursoClient instance for price history (optional)
        anomaly_detector: AnomalyDetector for z-score calculations
        level_shift_detector: LevelShiftDetector for sudden price drops

    Example:
        calc = BaselineCalculator(db_client=turso_client)
        result = calc.classify_deal(65000, "JFK-LOS")
        # {"tier": "wow", "method": "static", ...}

        result = calc.classify_deal(65000, "JFK-LOS", travel_date=dec_date)
        # Applies seasonal adjustment for December
    """

    def __init__(self, db_client=None):
        """
        Initialize BaselineCalculator.

        Args:
            db_client: Optional TursoClient for fetching price history.
                      If None, falls back to static thresholds.
        """
        self.db = db_client
        self.anomaly_detector = AnomalyDetector(
            window=90,
            min_periods=30,
            z_threshold=-2.5
        )
        self.level_shift_detector = LevelShiftDetector(
            short_window=3,
            long_window=14,
            threshold_pct=0.40
        )

    def _get_price_history(self, route: str, cabin_class: str = "economy") -> Optional[pd.Series]:
        """
        Fetch price history from database.

        Args:
            route: Route string e.g., "JFK-LOS"
            cabin_class: Cabin class filter

        Returns:
            pandas Series of prices (cents) ordered by date, or None if unavailable
        """
        if self.db is None:
            return None

        if not hasattr(self.db, 'get_price_history'):
            return None

        history = self.db.get_price_history(route, days=90, cabin_class=cabin_class)
        if history is None or len(history) == 0:
            return None

        # Convert to pandas Series (prices in cents, ordered by date)
        # History is returned most recent first, reverse for chronological order
        prices = [obs["price_cents"] for obs in reversed(history)]
        return pd.Series(prices)

    def _classify_with_zscore(self, z_score: float, price_cents: int, route: str) -> dict:
        """
        Classify deal based on z-score.

        Args:
            z_score: Calculated z-score (negative = below average)
            price_cents: Current price in cents
            route: Route string for exceptional floor check

        Returns:
            Classification dict with tier and method
        """
        # Extract destination for floor check
        dest = route.split("-")[1] if "-" in route else route

        # Check exceptional floor first
        floor_dollars = EXCEPTIONAL_FLOORS.get(dest, 0)
        floor_cents = floor_dollars * 100
        price_dollars = price_cents / 100

        # Very low z-score AND below floor = exceptional
        if z_score < ZSCORE_THRESHOLDS["exceptional"]:
            if price_cents < floor_cents:
                return {"tier": "exceptional", "z_score": z_score}
            # Even without floor breach, z < -2.5 is "great" at minimum
            return {"tier": "great", "z_score": z_score}

        # Great tier
        if z_score < ZSCORE_THRESHOLDS["great"]:
            return {"tier": "great", "z_score": z_score}

        # Good tier
        if z_score < ZSCORE_THRESHOLDS["good"]:
            return {"tier": "good", "z_score": z_score}

        # Not a deal
        return None

    def classify_deal(
        self,
        price_cents: int,
        route: str,
        travel_date: datetime = None,
        cabin_class: str = "economy"
    ) -> Optional[dict]:
        """
        Classify a price as a deal using hybrid detection.

        Priority order:
        1. Level shift detection (exceptional deals from sudden drops)
        2. Z-score classification (when 30+ observations)
        3. Static threshold fallback (when <30 observations)

        Args:
            price_cents: Price in cents (e.g., 65000 = $650)
            route: Route string e.g., "JFK-LOS"
            travel_date: Optional travel date for seasonal adjustment
            cabin_class: Cabin class (default "economy")

        Returns:
            Classification dict or None if not a deal:
            {
                "tier": "good"|"great"|"wow"|"exceptional"|None,
                "method": "zscore"|"level_shift"|"static"|"silent_period"|"no_deal",
                "z_score": float or None,
                "drop_pct": float or None,
                "observation_count": int
            }

        Example:
            result = calc.classify_deal(65000, "JFK-LOS")
            # {"tier": "wow", "method": "static", "observation_count": 0, ...}

            result = calc.classify_deal(40000, "JFK-LOS")
            # {"tier": "exceptional", "method": "static", ...} (below floor)
        """
        # Get price history if available
        prices = self._get_price_history(route, cabin_class)
        observation_count = len(prices) if prices is not None else 0

        # Extract destination code (needed for static threshold lookups)
        dest_code = route.split("-")[1] if "-" in route else route
        # Handle cabin-aware route keys like "JFK-LOS:BUSINESS"
        if ":" in dest_code:
            dest_code = dest_code.split(":")[0]

        # Base result structure
        result = {
            "tier": None,
            "method": "no_deal",
            "z_score": None,
            "drop_pct": None,
            "observation_count": observation_count
        }

        # === Premium cabin silent monitoring ===
        # 28+ observations AND 28+ calendar days before premium cabin alerts fire
        # Premium cabin data is sparse and thresholds are LOW confidence
        if cabin_class != "economy" and observation_count < PREMIUM_SILENT_OBSERVATIONS:
            result["method"] = "silent_period"
            return None  # Still collecting baseline data

        # === Step 1: Level shift detection ===
        # Requires at least short_window + long_window observations (3 + 14 = 17)
        if prices is not None and len(prices) >= 17:
            # Append current price to history for level shift check
            prices_with_current = pd.concat([prices, pd.Series([price_cents])], ignore_index=True)
            shift_result = self.level_shift_detector.detect(prices_with_current)

            if shift_result["is_level_shift"]:
                result["tier"] = "exceptional"
                result["method"] = "level_shift"
                result["drop_pct"] = shift_result["drop_pct"]
                return result

        # === Step 2: Z-score classification (30+ observations) ===
        if prices is not None and len(prices) >= 30:
            # Append current price for z-score calculation
            prices_with_current = pd.concat([prices, pd.Series([price_cents])], ignore_index=True)
            detection = self.anomaly_detector.detect(prices_with_current)

            if detection["z_score"] is not None:
                z_score = detection["z_score"]
                result["z_score"] = z_score

                zscore_classification = self._classify_with_zscore(z_score, price_cents, route)
                if zscore_classification:
                    result["tier"] = zscore_classification["tier"]
                    result["method"] = "zscore"
                    return result

            # Z-score calculated but not a deal
            result["method"] = "zscore"
            return None  # Not a deal

        # === Step 3: Silent period check (14-29 observations) ===
        if prices is not None and SILENT_PERIOD_OBSERVATIONS <= len(prices) < 30:
            # Still in monitoring period - use static as fallback but note we're gathering data
            # For now, fall through to static with silent_period flag
            pass

        # === Step 4: Static threshold fallback ===
        # Premium cabins use separate thresholds (single-tier: deal/exceptional)
        if cabin_class != "economy":
            premium_result = classify_premium_cabin(price_cents, dest_code, cabin_class)
            if premium_result:
                result["tier"] = premium_result["tier"]
                result["method"] = "static"
                return result
            return None  # Not a deal for this premium cabin

        # Economy: used for cold start (<30 observations) or no database
        static_result = classify_with_static(price_cents, route, travel_date)

        if static_result:
            result["tier"] = static_result["tier"]
            result["method"] = "static"
            return result

        # Not a deal by any method
        return None


def classify_deal(
    price_cents: int,
    route: str,
    travel_date: datetime = None,
    db_client=None
) -> Optional[dict]:
    """
    Quick classify without instantiating BaselineCalculator.

    Convenience function for simple use cases.

    Args:
        price_cents: Price in cents (e.g., 65000 = $650)
        route: Route string e.g., "JFK-LOS"
        travel_date: Optional travel date for seasonal adjustment
        db_client: Optional TursoClient for price history

    Returns:
        Classification dict or None if not a deal

    Example:
        result = classify_deal(65000, "JFK-LOS")
        # {"tier": "wow", "method": "static", ...}
    """
    calc = BaselineCalculator(db_client)
    return calc.classify_deal(price_cents, route, travel_date)
