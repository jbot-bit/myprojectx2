"""
NQ Massive Moves Research - Trend Following & Continuation Patterns
===================================================================

Goal: Find repeatable 3R+ same-day runners (not just mean-reversion scalps)

Search Windows:
- Afternoon: 16:00-21:00 (London close into NY)
- Night: 23:00-02:00 (NY futures/cash)

Candidate Patterns:
1. Trend day detector (early impulse + no deep pullback)
2. Breakout + retest continuation
3. Opening drive continuation (first 15-30 min efficiency)
4. Compression → expansion
5. Sweep → continuation

Robustness Tests:
- IS/OOS 70/30 split
- Outlier removal (top 1%)
- Slippage sensitivity (0/1/2 ticks)
- Parameter stability

Conservative Execution:
- Entry: Next bar after signal
- Same-bar TP+SL = LOSS
"""

import sys
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional
import duckdb
import pandas as pd
import numpy as np

DB_PATH = "gold.db"
TZ_LOCAL = ZoneInfo("Australia/Brisbane")
TZ_UTC = ZoneInfo("UTC")
TICK_SIZE = 0.25

# Search windows (Brisbane UTC+10)
AFTERNOON_START = time(16, 0)  # 16:00 local
AFTERNOON_END = time(21, 0)    # 21:00 local
NIGHT_START = time(23, 0)      # 23:00 local
NIGHT_END = time(2, 0)         # 02:00 next day local


def load_nq_bars() -> pd.DataFrame:
    """Load all NQ 1-minute bars with local timestamp"""
    con = duckdb.connect(DB_PATH, read_only=True)

    query = """
        SELECT
            ts_utc,
            ts_utc AT TIME ZONE 'Australia/Brisbane' as ts_local,
            DATE(ts_utc AT TIME ZONE 'Australia/Brisbane') as date_local,
            open, high, low, close, volume
        FROM bars_1m_nq
        ORDER BY ts_utc
    """

    df = con.execute(query).df()
    con.close()

    df['ts_local'] = pd.to_datetime(df['ts_local'])
    df['time_local'] = df['ts_local'].dt.time
    df['hour'] = df['ts_local'].dt.hour
    df['minute'] = df['ts_local'].dt.minute

    return df


def is_in_search_window(t: time) -> bool:
    """Check if time is in our search windows"""
    # Afternoon: 16:00-21:00
    if AFTERNOON_START <= t < AFTERNOON_END:
        return True

    # Night: 23:00-02:00 (crosses midnight)
    if t >= NIGHT_START or t < NIGHT_END:
        return True

    return False


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate ATR (Average True Range)"""
    high = df['high']
    low = df['low']
    close_prev = df['close'].shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr


def pattern_1_trend_day_detector(df: pd.DataFrame, min_r: float = 3.0) -> List[Dict]:
    """
    Pattern 1: Trend Day Detector

    Logic:
    - Identify strong directional move in first 30-60 min of search window
    - Enter on continuation if no deep pullback (>50% retracement)
    - Hold for 3R+ runner

    Entry: Next bar after signal confirms
    Stop: Initial swing low/high
    Target: 3R minimum
    """
    results = []

    # Group by date
    for date, day_df in df.groupby('date_local'):
        day_df = day_df.copy().reset_index(drop=True)

        # Find search window bars
        search_bars = day_df[day_df['time_local'].apply(is_in_search_window)].copy()

        if len(search_bars) < 90:  # Need at least 90 minutes of data
            continue

        search_bars = search_bars.reset_index(drop=True)

        # Look at first 30 bars (30 minutes)
        impulse_bars = search_bars.iloc[:30]

        if len(impulse_bars) < 30:
            continue

        # Calculate impulse metrics
        impulse_high = impulse_bars['high'].max()
        impulse_low = impulse_bars['low'].min()
        impulse_range = impulse_high - impulse_low
        impulse_close = impulse_bars.iloc[-1]['close']
        impulse_open = impulse_bars.iloc[0]['open']

        # Directional efficiency: how much of the range was captured directionally
        directional_move = abs(impulse_close - impulse_open)
        efficiency = directional_move / impulse_range if impulse_range > 0 else 0

        # Require strong efficiency (>60%) and minimum range
        if efficiency < 0.6 or impulse_range < 15:  # 15 points minimum
            continue

        # Determine direction
        if impulse_close > impulse_open:
            direction = 'UP'
            entry_price = impulse_close
            stop_price = impulse_low
        else:
            direction = 'DOWN'
            entry_price = impulse_close
            stop_price = impulse_high

        risk = abs(entry_price - stop_price)

        if risk < 5:  # Minimum risk filter
            continue

        # Entry bar is the next bar after impulse period (bar 30)
        if len(search_bars) <= 30:
            continue

        entry_idx = 30
        entry_bar = search_bars.iloc[entry_idx]
        entry_ts = entry_bar['ts_local']

        # Simulate trade
        target_price = entry_price + min_r * risk if direction == 'UP' else entry_price - min_r * risk

        # Check bars after entry
        trade_bars = search_bars.iloc[entry_idx + 1:]  # Next bar onwards

        outcome = None
        exit_price = None
        exit_ts = None
        r_multiple = None
        mae = 0
        mfe = 0

        for idx, bar in trade_bars.iterrows():
            h = bar['high']
            l = bar['low']

            if direction == 'UP':
                # Update MAE/MFE
                if l < entry_price:
                    mae = max(mae, (entry_price - l) / risk)
                if h > entry_price:
                    mfe = max(mfe, (h - entry_price) / risk)

                # Check stop first (conservative: same bar = loss)
                if l <= stop_price:
                    outcome = 'LOSS'
                    exit_price = stop_price
                    exit_ts = bar['ts_local']
                    r_multiple = -1.0
                    break

                # Check target
                if h >= target_price:
                    outcome = 'WIN'
                    exit_price = target_price
                    exit_ts = bar['ts_local']
                    r_multiple = min_r
                    break
            else:  # DOWN
                # Update MAE/MFE
                if h > entry_price:
                    mae = max(mae, (h - entry_price) / risk)
                if l < entry_price:
                    mfe = max(mfe, (entry_price - l) / risk)

                # Check stop first
                if h >= stop_price:
                    outcome = 'LOSS'
                    exit_price = stop_price
                    exit_ts = bar['ts_local']
                    r_multiple = -1.0
                    break

                # Check target
                if l <= target_price:
                    outcome = 'WIN'
                    exit_price = target_price
                    exit_ts = bar['ts_local']
                    r_multiple = min_r
                    break

        # If no outcome, mark as timeout
        if outcome is None:
            continue  # Skip timeout trades for now

        results.append({
            'date': date,
            'pattern': 'TREND_DAY',
            'direction': direction,
            'entry_ts': entry_ts,
            'entry_price': entry_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'risk': risk,
            'outcome': outcome,
            'exit_ts': exit_ts,
            'exit_price': exit_price,
            'r_multiple': r_multiple,
            'mae': mae,
            'mfe': mfe,
            'impulse_efficiency': efficiency,
            'impulse_range': impulse_range
        })

    return results


def pattern_2_breakout_retest(df: pd.DataFrame, min_r: float = 3.0) -> List[Dict]:
    """
    Pattern 2: Breakout + Retest Continuation

    Logic:
    - Break a key level (prior day H/L, Asia H/L)
    - Retest the level (within 5-10 points)
    - Continue in breakout direction

    Entry: After retest confirms support/resistance
    Stop: Below/above retest low/high
    Target: 3R
    """
    results = []

    # Load daily features for reference levels
    con = duckdb.connect(DB_PATH, read_only=True)
    features = con.execute("""
        SELECT date_local, asia_high, asia_low, london_high, london_low
        FROM daily_features_v2_nq
    """).df()
    con.close()

    features_dict = features.set_index('date_local').to_dict('index')

    for date, day_df in df.groupby('date_local'):
        day_df = day_df.copy().reset_index(drop=True)

        if date not in features_dict:
            continue

        feat = features_dict[date]
        asia_high = feat.get('asia_high')
        asia_low = feat.get('asia_low')

        if asia_high is None or asia_low is None:
            continue

        # Find search window bars
        search_bars = day_df[day_df['time_local'].apply(is_in_search_window)].copy()

        if len(search_bars) < 60:
            continue

        search_bars = search_bars.reset_index(drop=True)

        # Look for breakout of Asia high/low
        for i in range(10, len(search_bars) - 30):  # Need lookback and forward bars
            bar = search_bars.iloc[i]

            # Check if this bar breaks Asia high (for UP continuation)
            if bar['high'] > asia_high and bar['close'] > asia_high:
                # Look for retest in next 20 bars
                retest_bars = search_bars.iloc[i+1:i+21]

                for j, retest_bar in retest_bars.iterrows():
                    # Retest: comes within 5-10 points of breakout level
                    if abs(retest_bar['low'] - asia_high) <= 10 and retest_bar['low'] <= asia_high + 5:
                        # Entry on next bar after retest
                        entry_idx = j + 1
                        if entry_idx >= len(search_bars):
                            break

                        entry_bar = search_bars.iloc[entry_idx]
                        entry_price = entry_bar['open']
                        stop_price = retest_bar['low'] - 2  # 2 points below retest low
                        risk = entry_price - stop_price

                        if risk < 5 or risk > 50:
                            break

                        target_price = entry_price + min_r * risk

                        # Simulate trade
                        trade_result = simulate_trade(
                            search_bars.iloc[entry_idx+1:],
                            'UP', entry_price, stop_price, target_price, risk
                        )

                        if trade_result:
                            trade_result.update({
                                'date': date,
                                'pattern': 'BREAKOUT_RETEST',
                                'direction': 'UP',
                                'entry_ts': entry_bar['ts_local'],
                                'breakout_level': asia_high,
                                'retest_low': retest_bar['low']
                            })
                            results.append(trade_result)

                        break  # Only take first retest

            # Check if this bar breaks Asia low (for DOWN continuation)
            if bar['low'] < asia_low and bar['close'] < asia_low:
                retest_bars = search_bars.iloc[i+1:i+21]

                for j, retest_bar in retest_bars.iterrows():
                    if abs(retest_bar['high'] - asia_low) <= 10 and retest_bar['high'] >= asia_low - 5:
                        entry_idx = j + 1
                        if entry_idx >= len(search_bars):
                            break

                        entry_bar = search_bars.iloc[entry_idx]
                        entry_price = entry_bar['open']
                        stop_price = retest_bar['high'] + 2
                        risk = stop_price - entry_price

                        if risk < 5 or risk > 50:
                            break

                        target_price = entry_price - min_r * risk

                        trade_result = simulate_trade(
                            search_bars.iloc[entry_idx+1:],
                            'DOWN', entry_price, stop_price, target_price, risk
                        )

                        if trade_result:
                            trade_result.update({
                                'date': date,
                                'pattern': 'BREAKOUT_RETEST',
                                'direction': 'DOWN',
                                'entry_ts': entry_bar['ts_local'],
                                'breakout_level': asia_low,
                                'retest_high': retest_bar['high']
                            })
                            results.append(trade_result)

                        break

    return results


def simulate_trade(bars: pd.DataFrame, direction: str, entry_price: float,
                   stop_price: float, target_price: float, risk: float) -> Optional[Dict]:
    """Simulate trade execution with conservative resolution"""
    outcome = None
    exit_price = None
    exit_ts = None
    r_multiple = None
    mae = 0
    mfe = 0

    for idx, bar in bars.iterrows():
        h = bar['high']
        l = bar['low']

        if direction == 'UP':
            if l < entry_price:
                mae = max(mae, (entry_price - l) / risk)
            if h > entry_price:
                mfe = max(mfe, (h - entry_price) / risk)

            # Same bar hit both = LOSS (conservative)
            if l <= stop_price and h >= target_price:
                outcome = 'LOSS'
                exit_price = stop_price
                r_multiple = -1.0
                break

            if l <= stop_price:
                outcome = 'LOSS'
                exit_price = stop_price
                r_multiple = -1.0
                break

            if h >= target_price:
                outcome = 'WIN'
                exit_price = target_price
                r_multiple = (exit_price - entry_price) / risk
                break

        else:  # DOWN
            if h > entry_price:
                mae = max(mae, (h - entry_price) / risk)
            if l < entry_price:
                mfe = max(mfe, (entry_price - l) / risk)

            if h >= stop_price and l <= target_price:
                outcome = 'LOSS'
                exit_price = stop_price
                r_multiple = -1.0
                break

            if h >= stop_price:
                outcome = 'LOSS'
                exit_price = stop_price
                r_multiple = -1.0
                break

            if l <= target_price:
                outcome = 'WIN'
                exit_price = target_price
                r_multiple = (entry_price - exit_price) / risk
                break

        exit_ts = bar['ts_local']

    if outcome is None:
        return None  # Timeout

    return {
        'outcome': outcome,
        'exit_ts': exit_ts,
        'exit_price': exit_price,
        'r_multiple': r_multiple,
        'mae': mae,
        'mfe': mfe,
        'entry_price': entry_price,
        'stop_price': stop_price,
        'target_price': target_price,
        'risk': risk
    }


def analyze_results(trades: List[Dict], pattern_name: str) -> Dict:
    """Analyze trade results with robustness tests"""
    if not trades:
        return {'pattern': pattern_name, 'trades': 0, 'status': 'NO_TRADES'}

    df = pd.DataFrame(trades)

    # Basic stats
    total_trades = len(df)
    wins = len(df[df['outcome'] == 'WIN'])
    losses = len(df[df['outcome'] == 'LOSS'])
    win_rate = wins / total_trades if total_trades > 0 else 0

    r_multiples = df['r_multiple'].values
    avg_r = np.mean(r_multiples)
    median_r = np.median(r_multiples)
    p75_r = np.percentile(r_multiples, 75)

    # IS/OOS split (70/30 by date)
    dates_sorted = sorted(df['date'].unique())
    split_idx = int(len(dates_sorted) * 0.7)
    is_dates = set(dates_sorted[:split_idx])
    oos_dates = set(dates_sorted[split_idx:])

    is_trades = df[df['date'].isin(is_dates)]
    oos_trades = df[df['date'].isin(oos_dates)]

    is_avg_r = np.mean(is_trades['r_multiple'].values) if len(is_trades) > 0 else 0
    oos_avg_r = np.mean(oos_trades['r_multiple'].values) if len(oos_trades) > 0 else 0

    # Outlier removal (remove top 1% days)
    daily_r = df.groupby('date')['r_multiple'].sum()
    threshold = daily_r.quantile(0.99)
    outlier_dates = set(daily_r[daily_r > threshold].index)

    no_outlier_trades = df[~df['date'].isin(outlier_dates)]
    no_outlier_avg_r = np.mean(no_outlier_trades['r_multiple'].values) if len(no_outlier_trades) > 0 else 0

    # Pass/Fail criteria
    pass_tests = []

    # Test 1: Overall positive expectancy
    if avg_r > 0.5:
        pass_tests.append('OVERALL_POSITIVE')

    # Test 2: IS and OOS both positive
    if is_avg_r > 0 and oos_avg_r > 0:
        pass_tests.append('IS_OOS_POSITIVE')

    # Test 3: No outlier dependency
    if no_outlier_avg_r > 0:
        pass_tests.append('NO_OUTLIER_DEPENDENCY')

    # Test 4: Minimum sample size
    if total_trades >= 20:
        pass_tests.append('MIN_SAMPLE')

    # Overall pass/fail
    status = 'PASS' if len(pass_tests) >= 3 else 'FAIL'

    return {
        'pattern': pattern_name,
        'trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'median_r': median_r,
        'p75_r': p75_r,
        'is_trades': len(is_trades),
        'is_avg_r': is_avg_r,
        'oos_trades': len(oos_trades),
        'oos_avg_r': oos_avg_r,
        'no_outlier_avg_r': no_outlier_avg_r,
        'pass_tests': pass_tests,
        'status': status
    }


def main():
    print("=" * 80)
    print("NQ MASSIVE MOVES RESEARCH")
    print("=" * 80)
    print()
    print("Loading NQ data...")

    df = load_nq_bars()
    print(f"Loaded {len(df):,} 1-minute bars")
    print(f"Date range: {df['date_local'].min()} to {df['date_local'].max()}")
    print()

    # Test Pattern 1: Trend Day Detector
    print("Testing Pattern 1: Trend Day Detector...")
    pattern1_trades = pattern_1_trend_day_detector(df, min_r=3.0)
    pattern1_results = analyze_results(pattern1_trades, 'TREND_DAY')
    print(f"  Found {len(pattern1_trades)} trades")
    print(f"  Status: {pattern1_results.get('status', 'N/A')}")
    print()

    # Test Pattern 2: Breakout + Retest
    print("Testing Pattern 2: Breakout + Retest...")
    pattern2_trades = pattern_2_breakout_retest(df, min_r=3.0)
    pattern2_results = analyze_results(pattern2_trades, 'BREAKOUT_RETEST')
    print(f"  Found {len(pattern2_trades)} trades")
    print(f"  Status: {pattern2_results.get('status', 'N/A')}")
    print()

    # Combine all results
    all_results = [pattern1_results, pattern2_results]

    # Sort by avg_r
    all_results = sorted([r for r in all_results if r['trades'] > 0],
                        key=lambda x: x.get('avg_r', 0), reverse=True)

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    if not all_results:
        print("NO PATTERNS FOUND ANY TRADES")
        return

    print(f"{'Pattern':<20} {'Trades':>8} {'WR':>8} {'Avg R':>10} {'IS R':>10} {'OOS R':>10} {'Status':<10}")
    print("-" * 80)

    for r in all_results:
        print(f"{r['pattern']:<20} {r['trades']:>8} {r['win_rate']:>7.1%} {r['avg_r']:>+10.3f} "
              f"{r['is_avg_r']:>+10.3f} {r['oos_avg_r']:>+10.3f} {r['status']:<10}")

    print()

    # Save detailed results
    if all_results:
        results_df = pd.DataFrame(all_results)
        results_df.to_csv('outputs/NQ_MASSIVE_CANDIDATES.csv', index=False)
        print("Saved: outputs/NQ_MASSIVE_CANDIDATES.csv")

    # Save trade details
    all_trades = pattern1_trades + pattern2_trades
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        trades_df.to_csv('outputs/NQ_MASSIVE_TRADES.csv', index=False)
        print("Saved: outputs/NQ_MASSIVE_TRADES.csv")

    print()
    print("Analysis complete.")


if __name__ == "__main__":
    main()
