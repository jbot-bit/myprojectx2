"""
SESSION LIQUIDITY TRACKER

Tracks session highs/lows to identify directional bias.
Helps determine which ORB breakout direction to favor.

Session definitions (Brisbane time UTC+10):
- Asia: 09:00-17:00
- London: 18:00-23:00
- NY: 23:00-02:00 (next day)
"""

from datetime import datetime, time as dt_time
from typing import Dict, Optional, List, Tuple
from zoneinfo import ZoneInfo
import pandas as pd


class SessionLiquidity:
    """
    Tracks session highs/lows and identifies liquidity sweeps.

    Key concepts:
    - High/Low levels are "liquidity"
    - Sweep = price takes out previous session's high/low
    - Bias = direction suggested by liquidity structure
    """

    def __init__(self, tz_str: str = "Australia/Brisbane"):
        self.tz = ZoneInfo(tz_str)

        # Session definitions (local time)
        self.sessions = {
            'ASIA': (dt_time(9, 0), dt_time(17, 0)),
            'LONDON': (dt_time(18, 0), dt_time(23, 0)),
            'NY': (dt_time(23, 0), dt_time(2, 0))  # Crosses midnight
        }

        # Liquidity levels cache
        self.asia_high: Optional[float] = None
        self.asia_low: Optional[float] = None
        self.london_high: Optional[float] = None
        self.london_low: Optional[float] = None
        self.ny_high: Optional[float] = None
        self.ny_low: Optional[float] = None

        # Last update time
        self.last_update: Optional[datetime] = None

    def update_from_bars(self, bars_df: pd.DataFrame, current_time: datetime):
        """
        Update liquidity levels from bars dataframe.

        Args:
            bars_df: DataFrame with columns [ts_local, high, low]
            current_time: Current time (with timezone)
        """
        if bars_df.empty:
            return

        # Ensure timezone aware
        if bars_df['ts_local'].dt.tz is None:
            bars_df['ts_local'] = bars_df['ts_local'].dt.tz_localize(self.tz)

        # Calculate session levels
        today = current_time.date()

        # Asia session (09:00-17:00 today)
        asia_start = datetime.combine(today, dt_time(9, 0)).replace(tzinfo=self.tz)
        asia_end = datetime.combine(today, dt_time(17, 0)).replace(tzinfo=self.tz)
        asia_bars = bars_df[(bars_df['ts_local'] >= asia_start) & (bars_df['ts_local'] < asia_end)]

        if not asia_bars.empty:
            self.asia_high = float(asia_bars['high'].max())
            self.asia_low = float(asia_bars['low'].min())

        # London session (18:00-23:00 today)
        london_start = datetime.combine(today, dt_time(18, 0)).replace(tzinfo=self.tz)
        london_end = datetime.combine(today, dt_time(23, 0)).replace(tzinfo=self.tz)
        london_bars = bars_df[(bars_df['ts_local'] >= london_start) & (bars_df['ts_local'] < london_end)]

        if not london_bars.empty:
            self.london_high = float(london_bars['high'].max())
            self.london_low = float(london_bars['low'].min())

        # NY session (23:00 today to 02:00 tomorrow)
        # Note: This crosses midnight
        ny_start = datetime.combine(today, dt_time(23, 0)).replace(tzinfo=self.tz)
        # For simplicity, check if we're past 23:00 or before 02:00
        if current_time.time() >= dt_time(23, 0) or current_time.time() < dt_time(2, 0):
            # Get bars from 23:00 onwards
            ny_bars = bars_df[bars_df['ts_local'] >= ny_start]

            if not ny_bars.empty:
                self.ny_high = float(ny_bars['high'].max())
                self.ny_low = float(ny_bars['low'].min())

        self.last_update = current_time

    def get_current_session(self, current_time: datetime) -> str:
        """Determine which session we're currently in."""
        local_time = current_time.time()

        if dt_time(9, 0) <= local_time < dt_time(17, 0):
            return 'ASIA'
        elif dt_time(18, 0) <= local_time < dt_time(23, 0):
            return 'LONDON'
        elif local_time >= dt_time(23, 0) or local_time < dt_time(2, 0):
            return 'NY'
        else:
            return 'CLOSED'

    def check_liquidity_sweep(self, current_price: float, current_time: datetime) -> Dict:
        """
        Check if current price has swept any session liquidity levels.

        Returns:
            Dict with sweep information and directional bias
        """
        current_session = self.get_current_session(current_time)

        sweeps = {
            'asia_high_swept': False,
            'asia_low_swept': False,
            'london_high_swept': False,
            'london_low_swept': False,
            'directional_bias': None,  # 'BULLISH', 'BEARISH', or None
            'bias_reason': None,
            'cascade_detected': False,
            'cascade_pattern': None
        }

        # Check Asia liquidity sweeps
        if self.asia_high is not None and current_price > self.asia_high:
            sweeps['asia_high_swept'] = True

        if self.asia_low is not None and current_price < self.asia_low:
            sweeps['asia_low_swept'] = True

        # Check London liquidity sweeps
        if self.london_high is not None and current_price > self.london_high:
            sweeps['london_high_swept'] = True

        if self.london_low is not None and current_price < self.london_low:
            sweeps['london_low_swept'] = True

        # Check for CASCADE patterns (cross-session sweeps)
        # Pattern 1: Asia high swept -> London high swept (bullish cascade)
        if sweeps['asia_high_swept'] and sweeps['london_high_swept']:
            sweeps['cascade_detected'] = True
            sweeps['cascade_pattern'] = 'BULLISH CASCADE (Asia->London highs swept)'

        # Pattern 2: Asia low swept -> London low swept (bearish cascade)
        elif sweeps['asia_low_swept'] and sweeps['london_low_swept']:
            sweeps['cascade_detected'] = True
            sweeps['cascade_pattern'] = 'BEARISH CASCADE (Asia->London lows swept)'

        # Pattern 3: Asia high -> London sweeps Asia low (reversal)
        elif sweeps['asia_high_swept'] and sweeps['london_low_swept']:
            sweeps['cascade_detected'] = True
            sweeps['cascade_pattern'] = 'REVERSAL (Asia high->London swept low)'

        # Pattern 4: Asia low -> London sweeps Asia high (reversal)
        elif sweeps['asia_low_swept'] and sweeps['london_high_swept']:
            sweeps['cascade_detected'] = True
            sweeps['cascade_pattern'] = 'REVERSAL (Asia low->London swept high)'

        # Determine directional bias based on sweeps
        # Logic: If we sweep highs, bias is bullish (continuation)
        #        If we sweep lows, bias is bearish (continuation)
        #        If we sweep both, bias is unclear

        high_sweeps = sum([sweeps['asia_high_swept'], sweeps['london_high_swept']])
        low_sweeps = sum([sweeps['asia_low_swept'], sweeps['london_low_swept']])

        if sweeps['cascade_detected']:
            # Cascade patterns override regular bias
            if 'BULLISH CASCADE' in sweeps['cascade_pattern']:
                sweeps['directional_bias'] = 'STRONG BULLISH'
                sweeps['bias_reason'] = sweeps['cascade_pattern']
            elif 'BEARISH CASCADE' in sweeps['cascade_pattern']:
                sweeps['directional_bias'] = 'STRONG BEARISH'
                sweeps['bias_reason'] = sweeps['cascade_pattern']
            else:
                sweeps['directional_bias'] = 'REVERSAL'
                sweeps['bias_reason'] = sweeps['cascade_pattern']
        elif high_sweeps > low_sweeps:
            sweeps['directional_bias'] = 'BULLISH'
            sweeps['bias_reason'] = f'Swept {high_sweeps} session highs, {low_sweeps} lows'
        elif low_sweeps > high_sweeps:
            sweeps['directional_bias'] = 'BEARISH'
            sweeps['bias_reason'] = f'Swept {low_sweeps} session lows, {high_sweeps} highs'
        elif high_sweeps > 0 and low_sweeps > 0:
            sweeps['directional_bias'] = 'NEUTRAL'
            sweeps['bias_reason'] = 'Swept both highs and lows - choppy'
        else:
            sweeps['directional_bias'] = None
            sweeps['bias_reason'] = 'No sweeps yet'

        return sweeps

    def get_liquidity_structure(self) -> Dict:
        """
        Get current liquidity structure (all session highs/lows).

        Returns:
            Dict with all liquidity levels
        """
        return {
            'asia': {
                'high': self.asia_high,
                'low': self.asia_low,
                'range': (self.asia_high - self.asia_low) if (self.asia_high and self.asia_low) else None
            },
            'london': {
                'high': self.london_high,
                'low': self.london_low,
                'range': (self.london_high - self.london_low) if (self.london_high and self.london_low) else None
            },
            'ny': {
                'high': self.ny_high,
                'low': self.ny_low,
                'range': (self.ny_high - self.ny_low) if (self.ny_high and self.ny_low) else None
            }
        }

    def format_liquidity_report(self, current_price: float, current_time: datetime) -> str:
        """
        Format a human-readable liquidity report.
        """
        current_session = self.get_current_session(current_time)
        structure = self.get_liquidity_structure()
        sweeps = self.check_liquidity_sweep(current_price, current_time)

        report = f"SESSION LIQUIDITY TRACKER\n"
        report += f"{'='*50}\n\n"
        report += f"Current Session: {current_session}\n"
        report += f"Current Price: {current_price:.1f}\n"
        report += f"Last Update: {self.last_update.strftime('%H:%M:%S') if self.last_update else 'Never'}\n\n"

        report += f"LIQUIDITY LEVELS:\n"
        report += f"-" * 50 + "\n"

        # Asia
        if structure['asia']['high'] is not None:
            sweep_mark = " (SWEPT)" if sweeps['asia_high_swept'] else ""
            report += f"Asia High:   {structure['asia']['high']:.1f}{sweep_mark}\n"
        if structure['asia']['low'] is not None:
            sweep_mark = " (SWEPT)" if sweeps['asia_low_swept'] else ""
            report += f"Asia Low:    {structure['asia']['low']:.1f}{sweep_mark}\n"
        if structure['asia']['range']:
            report += f"Asia Range:  {structure['asia']['range']:.1f} pts\n"
        report += "\n"

        # London
        if structure['london']['high'] is not None:
            sweep_mark = " (SWEPT)" if sweeps['london_high_swept'] else ""
            report += f"London High: {structure['london']['high']:.1f}{sweep_mark}\n"
        if structure['london']['low'] is not None:
            sweep_mark = " (SWEPT)" if sweeps['london_low_swept'] else ""
            report += f"London Low:  {structure['london']['low']:.1f}{sweep_mark}\n"
        if structure['london']['range']:
            report += f"London Range: {structure['london']['range']:.1f} pts\n"
        report += "\n"

        # NY
        if structure['ny']['high'] is not None:
            report += f"NY High:     {structure['ny']['high']:.1f}\n"
        if structure['ny']['low'] is not None:
            report += f"NY Low:      {structure['ny']['low']:.1f}\n"
        if structure['ny']['range']:
            report += f"NY Range:    {structure['ny']['range']:.1f} pts\n"
        report += "\n"

        # Cross-session relationships (CASCADE detection)
        if sweeps['cascade_detected']:
            report += f"CASCADE PATTERN DETECTED:\n"
            report += f"-" * 50 + "\n"
            report += f"{sweeps['cascade_pattern']}\n"
            report += f"This is a HIGH PROBABILITY setup!\n\n"

        # Bias
        report += f"DIRECTIONAL BIAS:\n"
        report += f"-" * 50 + "\n"

        if sweeps['directional_bias']:
            report += f"Bias: {sweeps['directional_bias']}\n"
            report += f"Reason: {sweeps['bias_reason']}\n"
        else:
            report += f"No bias yet - waiting for sweeps\n"

        report += "\n"
        report += f"TRADING RECOMMENDATION:\n"
        report += f"-" * 50 + "\n"

        if sweeps['directional_bias'] in ['BULLISH', 'STRONG BULLISH']:
            report += "FAVOR LONG ORB BREAKOUTS\n"
            report += "Skip or reduce size on short breakouts\n"
            if sweeps['cascade_detected']:
                report += "CASCADE detected = INCREASE CONFIDENCE\n"
        elif sweeps['directional_bias'] in ['BEARISH', 'STRONG BEARISH']:
            report += "FAVOR SHORT ORB BREAKOUTS\n"
            report += "Skip or reduce size on long breakouts\n"
            if sweeps['cascade_detected']:
                report += "CASCADE detected = INCREASE CONFIDENCE\n"
        elif sweeps['directional_bias'] == 'REVERSAL':
            report += "REVERSAL pattern - trade carefully\n"
            report += "Wait for confirmation before entering\n"
        elif sweeps['directional_bias'] == 'NEUTRAL':
            report += "CHOPPY - Be cautious with both directions\n"
            report += "Consider skipping or waiting for clarity\n"
        else:
            report += "No clear bias yet - treat both directions equally\n"

        return report


def calculate_pre_orb_trend(bars_df: pd.DataFrame, orb_time: str, orb_date: datetime) -> Optional[str]:
    """
    Calculate pre-ORB trend for a specific ORB.

    Returns 'UP', 'DOWN', or None

    Logic:
    - For 10am ORB: Look at 09:00-10:00 (1 hour before)
    - For 11am ORB: Look at 10:00-11:00 (1 hour before)
    - Check where close is in range (upper 40% = UP, lower 40% = DOWN)
    """
    if bars_df.empty:
        return None

    # Parse ORB time
    orb_hour = int(orb_time[:2])

    # Define pre-ORB window (1 hour before ORB)
    pre_hour = orb_hour - 1
    if pre_hour < 0:
        return None  # Can't calculate for midnight ORBs

    # Get bars from pre-ORB hour
    tz = ZoneInfo("Australia/Brisbane")
    pre_start = datetime.combine(orb_date.date(), dt_time(pre_hour, 0)).replace(tzinfo=tz)
    pre_end = datetime.combine(orb_date.date(), dt_time(orb_hour, 0)).replace(tzinfo=tz)

    pre_bars = bars_df[(bars_df['ts_local'] >= pre_start) & (bars_df['ts_local'] < pre_end)]

    if pre_bars.empty:
        return None

    # Calculate range and close position
    high = pre_bars['high'].max()
    low = pre_bars['low'].min()
    close = pre_bars.iloc[-1]['close']  # Last close before ORB

    range_size = high - low
    if range_size == 0:
        return None

    close_position = (close - low) / range_size

    # Upper 40% = UP bias, Lower 40% = DOWN bias
    if close_position > 0.6:
        return 'UP'
    elif close_position < 0.4:
        return 'DOWN'
    else:
        return None  # Middle 20% = no clear bias


if __name__ == "__main__":
    # Test the liquidity tracker
    print("="*80)
    print("SESSION LIQUIDITY TRACKER - TEST")
    print("="*80)
    print()

    # Create tracker
    tracker = SessionLiquidity()

    # Create some fake bars for testing
    import numpy as np

    now = datetime.now(ZoneInfo("Australia/Brisbane"))
    current_time = now.replace(hour=14, minute=30)  # 2:30pm (Asia session)

    # Generate fake bars from 9am to now
    times = pd.date_range(
        start=now.replace(hour=9, minute=0, second=0, microsecond=0),
        end=current_time,
        freq='1min'
    )

    # Fake price data (uptrend)
    base_price = 2530.0
    bars_df = pd.DataFrame({
        'ts_local': times,
        'high': base_price + np.cumsum(np.random.randn(len(times)) * 0.5) + 5,
        'low': base_price + np.cumsum(np.random.randn(len(times)) * 0.5),
        'close': base_price + np.cumsum(np.random.randn(len(times)) * 0.5) + 2.5
    })

    # Set current price (above Asia high to trigger sweep)
    current_price = bars_df['high'].max() + 1.0

    # Update tracker
    tracker.update_from_bars(bars_df, current_time)

    # Print report
    print(tracker.format_liquidity_report(current_price, current_time))

    # Test pre-ORB trend
    print("\n" + "="*80)
    print("PRE-ORB TREND TEST")
    print("="*80)

    trend = calculate_pre_orb_trend(bars_df, '1000', current_time)
    print(f"10am pre-ORB trend: {trend}")

    trend = calculate_pre_orb_trend(bars_df, '1100', current_time)
    print(f"11am pre-ORB trend: {trend}")
