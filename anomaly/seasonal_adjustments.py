"""
Seasonal threshold adjustments for flight pricing.

DISC-07: Seasonal adjustments based on research:
- Dec-Jan: +50% (Detty December - prices roughly double)
- Jun-Aug: +25% (Summer vacation season)

These multipliers raise the "deal threshold" during peak seasons,
so a $900 fare in December is treated like a $600 fare in March.

All prices are in CENTS (INTEGER) per Phase 2 decision.
"""

from datetime import datetime


class SeasonalAdjuster:
    """
    Apply seasonal threshold adjustments to avoid false positives during peak travel.

    Seasonal multipliers based on market research:
    - December-January: 1.50 (Detty December peak, prices roughly double)
    - June-August: 1.25 (Summer vacation season)
    - Other months: 1.00 (shoulder/off-peak seasons)

    Example:
        dec_date = datetime(2026, 12, 15)
        multiplier = SeasonalAdjuster.get_multiplier(dec_date)  # 1.50

        # A $700 WOW threshold in December becomes $1050
        adjusted = SeasonalAdjuster.adjust_threshold(70000, dec_date)  # 105000 cents
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
        """
        Get seasonal multiplier for a travel date.

        Args:
            travel_date: The travel departure date

        Returns:
            Multiplier value (1.0 = no adjustment, 1.5 = 50% higher threshold)
        """
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
