"""
Test Backtest Engine Zero-Lookahead Invariants

Validates that the backtest engine never uses future information:
- ORB calculation uses only bars within ORB window
- Entry detection never references future candles
- Exit logic obeys stop-first priority (conservative)
- No data leakage from future bars

Run:
    pytest tests/test_backtest_zero_lookahead.py -v
"""

import pytest
import pandas as pd
import pytz
from datetime import datetime, date, time as dt_time, timedelta
from trading_app.backtest.engine import (
    CandidateSpec,
    calculate_orb,
    detect_breakout_entry,
    simulate_trade
)


@pytest.fixture
def sample_spec():
    """Create a sample candidate spec for testing."""
    return CandidateSpec(
        candidate_id=1,
        name="TEST_0900_RR2_HALF",
        instrument="MGC",
        orb_time="0900",
        orb_minutes=5,
        entry_rule="breakout",
        sl_mode="HALF",
        rr=2.0,
        scan_start_local=dt_time(9, 5),
        scan_end_local=dt_time(17, 0),
        max_hold_end_local=dt_time(17, 0),
        filters={},
        crosses_midnight=False
    )


@pytest.fixture
def sample_bars():
    """
    Create sample bars with known ORB and breakout.

    ORB window: 09:00-09:05 (5 bars)
    ORB high: 2030, ORB low: 2020
    Breakout: 09:10 bar closes at 2031 (above ORB high)
    """
    tz_local = pytz.timezone("Australia/Brisbane")
    base_date = date(2025, 1, 10)

    bars_data = []

    # ORB bars (09:00-09:04)
    for minute in range(5):
        ts_local = tz_local.localize(datetime.combine(base_date, dt_time(9, minute)))
        bars_data.append({
            'ts_utc': ts_local.astimezone(pytz.utc),
            'ts_local': ts_local,
            'time_local': ts_local.time(),
            'open': 2025.0,
            'high': 2030.0 if minute == 2 else 2027.0,  # High at 09:02
            'low': 2020.0 if minute == 0 else 2023.0,   # Low at 09:00
            'close': 2025.0,
            'volume': 100
        })

    # Post-ORB bars (09:05-09:15)
    for minute in range(5, 16):
        ts_local = tz_local.localize(datetime.combine(base_date, dt_time(9, minute)))

        # Breakout at 09:10 (close above ORB high)
        if minute == 10:
            close_price = 2031.0  # Above ORB high (2030)
            high_price = 2032.0
        else:
            close_price = 2028.0
            high_price = 2029.0

        bars_data.append({
            'ts_utc': ts_local.astimezone(pytz.utc),
            'ts_local': ts_local,
            'time_local': ts_local.time(),
            'open': 2027.0,
            'high': high_price,
            'low': 2026.0,
            'close': close_price,
            'volume': 100
        })

    return pd.DataFrame(bars_data)


def test_orb_calculation_uses_only_orb_window(sample_spec, sample_bars):
    """Test that ORB calculation uses only bars within the ORB window."""
    orb = calculate_orb(sample_bars, sample_spec)

    assert orb is not None, "ORB should be calculated"
    assert orb['high'] == 2030.0, "ORB high should match max high in ORB window"
    assert orb['low'] == 2020.0, "ORB low should match min low in ORB window"
    assert orb['size'] == 10.0, "ORB size should be 10 points"

    # Verify ORB does NOT include post-ORB data
    # Post-ORB bars have high=2032 (at breakout), but ORB high is 2030
    assert orb['high'] < 2032.0, "ORB must not include future bars outside window"


def test_entry_detection_never_references_future_bars(sample_spec, sample_bars):
    """Test that entry detection processes bars sequentially, never looking ahead."""
    orb = calculate_orb(sample_bars, sample_spec)
    trading_date = date(2025, 1, 10)

    entry_result = detect_breakout_entry(sample_bars, orb, sample_spec, trading_date)

    assert entry_result is not None, "Entry should be detected"
    entry_bar, direction = entry_result

    # Entry should be at 09:10 (first close above ORB high)
    assert entry_bar['time_local'] == dt_time(9, 10), "Entry should be at 09:10"
    assert direction == 'long', "Direction should be long (broke above ORB)"
    assert entry_bar['close'] > orb['high'], "Entry close must be outside ORB"

    # Verify entry bar is the FIRST bar to break out (not cherry-picked from later bars)
    scan_bars = sample_bars[
        (sample_bars['time_local'] >= dt_time(9, 5)) &
        (sample_bars['time_local'] < dt_time(17, 0))
    ]

    first_breakout_idx = None
    for idx, bar in scan_bars.iterrows():
        if bar['close'] > orb['high']:
            first_breakout_idx = idx
            break

    assert first_breakout_idx is not None, "Should find first breakout"
    assert entry_bar.name == first_breakout_idx, "Entry must be the FIRST breakout, not a later one"


def test_exit_logic_obeys_stop_first_priority():
    """Test that if stop and target are both hit in same bar, stop is executed first."""
    tz_local = pytz.timezone("Australia/Brisbane")
    base_date = date(2025, 1, 10)

    # Entry bar
    entry_ts = tz_local.localize(datetime.combine(base_date, dt_time(9, 10)))
    entry_bar = pd.Series({
        'ts_local': entry_ts,
        'close': 2031.0,  # Entry at 2031
        'high': 2032.0,
        'low': 2030.0
    })

    # ORB with midpoint at 2025
    orb = {
        'high': 2030.0,
        'low': 2020.0,
        'size': 10.0,
        'midpoint': 2025.0
    }

    # Candidate spec (HALF mode, RR=2.0)
    spec = CandidateSpec(
        candidate_id=1,
        name="TEST",
        instrument="MGC",
        orb_time="0900",
        orb_minutes=5,
        entry_rule="breakout",
        sl_mode="HALF",
        rr=2.0,
        scan_start_local=dt_time(9, 5),
        scan_end_local=dt_time(17, 0),
        max_hold_end_local=dt_time(17, 0),
        filters={},
        crosses_midnight=False
    )

    # Calculate stop and target
    # Entry: 2031, Stop: 2025 (midpoint), Risk: 6 points, Target: 2043 (2031 + 6*2)

    # Create a bar that hits BOTH stop and target
    # Low touches stop (2025), High touches target (2043)
    remaining_bars = pd.DataFrame([{
        'ts_local': entry_ts + timedelta(minutes=1),
        'time_local': dt_time(9, 11),
        'open': 2031.0,
        'high': 2043.0,  # Hits target
        'low': 2024.0,   # Hits stop (below 2025)
        'close': 2030.0,
        'volume': 100
    }])

    trade = simulate_trade(entry_bar, 'long', orb, remaining_bars, spec)

    # CRITICAL: Stop should execute first (conservative behavior)
    assert trade.outcome == 'LOSS', "Stop must execute before target (stop-first priority)"
    assert trade.r_multiple == -1.0, "Should lose 1R when stopped out"
    assert trade.exit_price == orb['midpoint'], "Exit price should be stop price"


def test_no_future_bar_leakage_in_mae_mfe():
    """Test that MAE/MFE calculations don't use future bars."""
    tz_local = pytz.timezone("Australia/Brisbane")
    base_date = date(2025, 1, 10)

    entry_ts = tz_local.localize(datetime.combine(base_date, dt_time(9, 10)))
    entry_bar = pd.Series({
        'ts_local': entry_ts,
        'close': 2031.0,
        'high': 2032.0,
        'low': 2030.0
    })

    orb = {
        'high': 2030.0,
        'low': 2020.0,
        'size': 10.0,
        'midpoint': 2025.0
    }

    spec = CandidateSpec(
        candidate_id=1,
        name="TEST",
        instrument="MGC",
        orb_time="0900",
        orb_minutes=5,
        entry_rule="breakout",
        sl_mode="HALF",
        rr=2.0,
        scan_start_local=dt_time(9, 5),
        scan_end_local=dt_time(17, 0),
        max_hold_end_local=dt_time(17, 0),
        filters={},
        crosses_midnight=False
    )

    # Entry at 2031, Stop at 2025 (midpoint), Risk = 6 points, Target = 2043 (2031 + 6*2)
    # Create bars with known MAE (goes against us first, then hits target)
    remaining_bars = pd.DataFrame([
        {
            'ts_local': entry_ts + timedelta(minutes=1),
            'time_local': dt_time(9, 11),
            'open': 2031.0,
            'high': 2032.0,
            'low': 2028.0,  # MAE: drops to 2028 (3 points against us)
            'close': 2030.0,
            'volume': 100
        },
        {
            'ts_local': entry_ts + timedelta(minutes=2),
            'time_local': dt_time(9, 12),
            'open': 2030.0,
            'high': 2035.0,  # Moving up
            'low': 2029.0,
            'close': 2034.0,
            'volume': 100
        },
        {
            'ts_local': entry_ts + timedelta(minutes=3),
            'time_local': dt_time(9, 13),
            'open': 2034.0,
            'high': 2043.0,  # Hits target!
            'low': 2033.0,
            'close': 2042.0,
            'volume': 100
        }
    ])

    trade = simulate_trade(entry_bar, 'long', orb, remaining_bars, spec)

    # MAE should reflect the worst point BEFORE exit
    # Risk = 6 points (2031 - 2025), MAE = 3 points (2031 - 2028)
    # MAE in R = 3/6 = 0.5R
    assert trade.outcome == 'WIN', "Trade should win"
    assert trade.mae_r > 0, "MAE should be positive (went against us)"
    assert trade.mae_r <= 1.0, "MAE should not exceed 1R (would have stopped out)"

    # MFE should be the target (2R) since we hit target
    assert trade.mfe_r == 2.0, "MFE should be 2R (target)"


def test_scan_window_respects_time_boundaries():
    """Test that scan window doesn't process bars outside the defined window."""
    spec = CandidateSpec(
        candidate_id=1,
        name="TEST",
        instrument="MGC",
        orb_time="0900",
        orb_minutes=5,
        entry_rule="breakout",
        sl_mode="HALF",
        rr=2.0,
        scan_start_local=dt_time(9, 5),
        scan_end_local=dt_time(12, 0),  # Scan ends at noon
        max_hold_end_local=dt_time(12, 0),
        filters={},
        crosses_midnight=False
    )

    tz_local = pytz.timezone("Australia/Brisbane")
    base_date = date(2025, 1, 10)

    # Create bars with breakout AFTER scan window ends
    bars_data = []

    # ORB bars (09:00-09:04)
    for minute in range(5):
        ts_local = tz_local.localize(datetime.combine(base_date, dt_time(9, minute)))
        bars_data.append({
            'ts_utc': ts_local.astimezone(pytz.utc),
            'ts_local': ts_local,
            'time_local': ts_local.time(),
            'open': 2025.0,
            'high': 2030.0,
            'low': 2020.0,
            'close': 2025.0,
            'volume': 100
        })

    # Bars within scan window (09:05-11:59) - no breakout
    for hour in [9, 10, 11]:
        for minute in (range(5, 60) if hour == 9 else range(60)):
            if hour == 11 and minute >= 60:
                break
            ts_local = tz_local.localize(datetime.combine(base_date, dt_time(hour, minute)))
            bars_data.append({
                'ts_utc': ts_local.astimezone(pytz.utc),
                'ts_local': ts_local,
                'time_local': ts_local.time(),
                'open': 2025.0,
                'high': 2028.0,  # Below ORB high
                'low': 2022.0,   # Above ORB low
                'close': 2025.0,
                'volume': 100
            })

    # Breakout AFTER scan window ends (13:00)
    ts_local = tz_local.localize(datetime.combine(base_date, dt_time(13, 0)))
    bars_data.append({
        'ts_utc': ts_local.astimezone(pytz.utc),
        'ts_local': ts_local,
        'time_local': ts_local.time(),
        'open': 2025.0,
        'high': 2035.0,
        'low': 2025.0,
        'close': 2035.0,  # Breaks above ORB high, but OUTSIDE scan window
        'volume': 100
    })

    bars = pd.DataFrame(bars_data)
    orb = calculate_orb(bars, spec)

    entry_result = detect_breakout_entry(bars, orb, spec, base_date)

    # Entry should be None - breakout happened outside scan window
    assert entry_result is None, "Entry should not be detected outside scan window (zero-lookahead violated if detected)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
