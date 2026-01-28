"""
Level Shift Detector for discovering exceptional flight deals.

Detects sudden price drops ("mistake fares") by comparing recent prices
against historical baseline using median comparisons.

DISC-05: Discover own "mistake fares" via sudden price drop detection

Usage:
    from anomaly import LevelShiftDetector, detect_level_shift

    # Class-based for detailed analysis
    detector = LevelShiftDetector(short_window=3, long_window=14, threshold_pct=0.40)
    result = detector.detect(price_series)
    if result["is_level_shift"]:
        print(f"Exceptional deal! {result['drop_pct']:.0%} drop detected")

    # Function for quick check
    if detect_level_shift(price_series):
        alert("Potential mistake fare detected!")
"""

import pandas as pd
from typing import Union


class LevelShiftDetector:
    """
    Detect sudden price drops by comparing short-term vs long-term medians.

    A level shift indicates a sudden change in price regime, often signaling
    a mistake fare or exceptional deal opportunity.

    Algorithm:
        1. Calculate median of recent short_window observations
        2. Calculate median of previous long_window observations (baseline)
        3. If (baseline - recent) / baseline >= threshold_pct, flag as level shift

    Attributes:
        short_window: Number of recent observations to compare (default 3)
        long_window: Number of baseline observations (default 14)
        threshold_pct: Minimum percentage drop to trigger (default 0.40 = 40%)
    """

    def __init__(
        self,
        short_window: int = 3,
        long_window: int = 14,
        threshold_pct: float = 0.40
    ):
        """
        Initialize LevelShiftDetector.

        Args:
            short_window: Recent observations to compare (e.g., last 3 checks)
            long_window: Baseline period (e.g., previous 14 observations)
            threshold_pct: Percentage drop to trigger (0.40 = 40% drop)
        """
        self.short_window = short_window
        self.long_window = long_window
        self.threshold_pct = threshold_pct

    def detect(self, prices: pd.Series) -> dict:
        """
        Detect if recent prices represent a level shift (sudden drop).

        Compares median of recent short window vs previous long window.
        A 40%+ drop from the previous baseline indicates potential mistake fare.

        Args:
            prices: Time series of prices (most recent last)

        Returns:
            Dictionary with detection results:
                - is_level_shift: bool - True if level shift detected
                - drop_pct: float or None - Percentage drop (0.0-1.0 scale)
                - recent_median: int - Median of recent observations
                - baseline_median: int - Median of baseline observations
                - method: str - "level_shift" or "insufficient_data"
        """
        min_required = self.short_window + self.long_window

        # Insufficient data
        if len(prices) < min_required:
            return {
                "is_level_shift": False,
                "drop_pct": None,
                "recent_median": None,
                "baseline_median": None,
                "method": "insufficient_data"
            }

        # Calculate medians
        recent_median = prices.iloc[-self.short_window:].median()
        baseline_median = prices.iloc[-(self.short_window + self.long_window):-self.short_window].median()

        # Convert to int if they are valid numbers
        recent_median_int = int(recent_median) if pd.notna(recent_median) else None
        baseline_median_int = int(baseline_median) if pd.notna(baseline_median) else None

        # Handle zero baseline (avoid division by zero)
        if baseline_median_int is None or baseline_median_int == 0:
            return {
                "is_level_shift": False,
                "drop_pct": None,
                "recent_median": recent_median_int,
                "baseline_median": baseline_median_int,
                "method": "level_shift"
            }

        # Calculate drop percentage
        drop_pct = (baseline_median - recent_median) / baseline_median

        # Determine if level shift
        is_level_shift = drop_pct >= self.threshold_pct

        return {
            "is_level_shift": is_level_shift,
            "drop_pct": float(drop_pct),
            "recent_median": recent_median_int,
            "baseline_median": baseline_median_int,
            "method": "level_shift"
        }


def detect_level_shift(
    prices: pd.Series,
    threshold_pct: float = 0.40,
    short_window: int = 3,
    long_window: int = 14
) -> bool:
    """
    Quick check for level shift in price series.

    Convenience function that returns True/False without full result dict.

    Args:
        prices: Time series of prices (most recent last)
        threshold_pct: Percentage drop to trigger (default 0.40 = 40%)
        short_window: Recent observations to compare (default 3)
        long_window: Baseline period (default 14)

    Returns:
        True if level shift detected (exceptional deal), False otherwise
    """
    detector = LevelShiftDetector(
        short_window=short_window,
        long_window=long_window,
        threshold_pct=threshold_pct
    )
    result = detector.detect(prices)
    return result["is_level_shift"]
