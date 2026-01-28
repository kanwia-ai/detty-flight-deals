"""
Anomaly detection for flight prices using rolling z-scores.

DISC-04: Detects anomalously cheap fares via rolling z-score (z < -2.5)

The rolling z-score approach adapts to recent price trends rather than using
global statistics, which captures seasonality and market changes.

Key thresholds:
- z < -2.5: Approximately bottom 0.6% of distribution (anomalous deal)
- z < -2.0: Bottom ~2.3% (potential deal)
- z < -1.5: Bottom ~6.7% (minor deal)
"""

import pandas as pd
import numpy as np


class AnomalyDetector:
    """
    Anomaly detection for flight prices using rolling z-scores.

    Calculates z-scores using a rolling window approach, which adapts to
    recent price trends rather than using global statistics.

    Args:
        window: Rolling window size in observations (default: 90 days)
        min_periods: Minimum observations required for calculation (default: 30)
        z_threshold: Z-score threshold for anomaly detection (default: -2.5)

    Example:
        detector = AnomalyDetector(window=90, min_periods=30)
        prices = pd.Series([1000, 1050, 980, ...])  # historical prices in cents
        result = detector.detect(prices)
        if result['is_anomaly']:
            print(f"Deal detected! Z-score: {result['z_score']}")
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

        Args:
            prices: Time series of prices (in cents, as integers)

        Returns:
            Series of z-scores where negative values indicate below-average prices
        """
        rolling_mean = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).mean()

        rolling_std = prices.rolling(
            window=self.window,
            min_periods=self.min_periods
        ).std()

        # Handle zero std (constant prices) by replacing with NaN
        # This prevents division by zero and marks as insufficient variance
        rolling_std = rolling_std.replace(0, np.nan)

        z_scores = (prices - rolling_mean) / rolling_std
        return z_scores

    def is_anomaly(self, z_score: float) -> bool:
        """
        Check if z-score indicates an anomalously cheap fare.

        Args:
            z_score: The calculated z-score

        Returns:
            True if z-score is below threshold (negative = cheaper than average)
        """
        if pd.isna(z_score):
            return False
        return z_score < self.z_threshold

    def detect(self, prices: pd.Series) -> dict:
        """
        Run detection on price series.

        Analyzes the most recent price in the series against the rolling
        historical average.

        Args:
            prices: Time series of prices (in cents, as integers).
                    The last value is the current price to evaluate.

        Returns:
            dict with:
                - is_anomaly: bool - True if current price is anomalously low
                - z_score: float or None - The calculated z-score
                - method: str - "zscore" or "insufficient_data"
                - rolling_mean: float or None - The rolling mean
                - rolling_std: float or None - The rolling standard deviation

        Example:
            result = detector.detect(prices)
            # result = {
            #     'is_anomaly': True,
            #     'z_score': -3.2,
            #     'method': 'zscore',
            #     'rolling_mean': 95000.0,
            #     'rolling_std': 15000.0
            # }
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
