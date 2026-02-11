"""
Anomaly detection package for flight price analysis.

This package provides:
- AnomalyDetector: Rolling z-score calculations for deal detection
- SeasonalAdjuster: Month-based threshold multipliers for peak travel periods
- Static thresholds: Cold-start fallback classification for new routes
- LevelShiftDetector: Sudden price drop detection for mistake fares
- BaselineCalculator: Hybrid classification combining all detection methods
"""

from .anomaly_detector import AnomalyDetector
from .seasonal_adjustments import SeasonalAdjuster
from .static_thresholds import (
    STATIC_THRESHOLDS,
    EXCEPTIONAL_FLOORS,
    classify_with_static,
    PREMIUM_STATIC_THRESHOLDS,
    classify_premium_cabin,
)
from .level_shift_detector import LevelShiftDetector, detect_level_shift
from .baseline_calculator import BaselineCalculator, classify_deal

__all__ = [
    "AnomalyDetector",
    "SeasonalAdjuster",
    "STATIC_THRESHOLDS",
    "EXCEPTIONAL_FLOORS",
    "classify_with_static",
    "PREMIUM_STATIC_THRESHOLDS",
    "classify_premium_cabin",
    "LevelShiftDetector",
    "detect_level_shift",
    "BaselineCalculator",
    "classify_deal",
]
