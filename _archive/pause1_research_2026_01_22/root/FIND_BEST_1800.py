"""
COMPREHENSIVE 1800 LONDON ORB SCANNER
======================================

Find the BEST 1800 ORB setups with:
- Multiple durations, SL modes, RR targets
- Pre-session filters (ATR, Asia behavior, directional bias)
- Extended scan windows (until next Asia open)
- Zero lookahead compliance

User wants to trade in 30 minutes - find optimal setups NOW!
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass
import pandas as pd
import numpy as np

SYMBOL = "MGC"
TICK_SIZE = 0.1

@dataclass
class Result:
    duration_min: int
    sl_mode: str
    rr: float
    filter_name: str
    trades: int
    wins: int
    win_rate: float
    avg_r: float
    total_r: float
    annual_r: float
    median_hold_hours: float
    sharpe: float


def get_orb_from_bars(con, date_local, hour, minute, duration_min):
    """Calculate ORB dynamically from 1m bars"""
    start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"
    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration_min)
    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    query = f"""
    SELECT high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{end_ts}'::TIMESTAMPTZ
    """
    rows = con.execute(query).fetchall()
    if not rows:
        return None

    orb_high = max(float(r[0]) for r in rows)
    orb_low = min(float(r[1]) for r in rows)

    if orb_high <= orb_low:
        return None

    return {'high': orb_high, 'low': orb_low, 'size': orb_high - orb_low, 'end_ts': end_ts}


def detect_orb_break(con, orb, entry_start_ts, scan_end_ts):
    """Detect first 1m close outside ORB"""
    query = f"""
    SELECT ts_utc, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{entry_start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    rows = con.execute(query).fetchall()
    if not rows:
        return None, None, None

    for ts, close in rows:
        if float(close) > orb['high']:
            return 'UP', str(ts), float(close)
        elif float(close) < orb['low']:
            return 'DOWN', str(ts), float(close)
    return None, None, None


def simulate_trade(con, date_local, duration_min, sl_mode, rr, features):
    """Simulate 1800 ORB trade with extended scan window"""

    # Get ORB
    orb = get_orb_from_bars(con, date_local, 18, 0, duration_min)
    if not orb:
        return None

    entry_start_ts = orb['end_ts']
    scan_end_ts = f"{date_local + timedelta(days=1)} 09:00:00"

    break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
    if not break_dir:
        return None

    orb_mid = (orb['high'] + orb['low']) / 2.0
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']

    # Calculate stop
    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    elif sl_mode == "QUARTER":
        stop = orb_edge - (orb['size'] * 0.25) if break_dir == 'UP' else orb_edge + (orb['size'] * 0.25)
    else:
        return None

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

    # Get bars after entry
    bars_query = f"""
    SELECT ts_utc, high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    bars = con.execute(bars_query).fetchall()
    if not bars:
        return None

    entry_dt = datetime.fromisoformat(entry_ts.replace('+00:00', ''))

    # Simulate outcome
    for ts_utc, h, l in bars:
        h, l = float(h), float(l)

        if break_dir == 'UP':
            if l <= stop and h >= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}
            if h >= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}
            if l <= stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}
        else:  # DOWN
            if h >= stop and l <= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}
            if l <= target:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'WIN', 'r_multiple': float(rr), 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}
            if h >= stop:
                exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                return {'outcome': 'LOSS', 'r_multiple': -1.0, 'hold_hours': (exit_dt - entry_dt).total_seconds() / 3600,
                       'orb_size': orb['size'], 'break_dir': break_dir}

    return None


def apply_filter(result, features, filter_config):
    """Apply pre-session filters (zero lookahead)"""

    if result is None:
        return False

    filter_name = filter_config['name']

    # No filter = accept all
    if filter_name == "NONE":
        return True

    # ATR-based ORB size filter
    if filter_name.startswith("ATR_"):
        max_ratio = float(filter_name.split('_')[1])
        if features['atr_20'] is None or features['atr_20'] == 0:
            return False
        return result['orb_size'] <= (max_ratio * features['atr_20'])

    # Asia range filter (small Asia range = coiled, ready for London)
    if filter_name.startswith("ASIA_RANGE_"):
        max_ratio = float(filter_name.split('_')[2])
        if features['atr_20'] is None or features['atr_20'] == 0:
            return False
        if features['asia_range'] is None:
            return False
        return features['asia_range'] <= (max_ratio * features['atr_20'])

    # Directional alignment: 1800 breaks same direction as 0900/1000
    if filter_name == "ALIGN_ASIA":
        if features['orb_0900_break_dir'] is None and features['orb_1000_break_dir'] is None:
            return True  # No prior ORBs to align with

        # At least one Asia ORB must align with 1800 direction
        if features['orb_0900_break_dir'] == result['break_dir']:
            return True
        if features['orb_1000_break_dir'] == result['break_dir']:
            return True
        return False

    # Combination: Small Asia range + directional alignment
    if filter_name == "COMBO_COILED_ALIGNED":
        # Small Asia range
        if features['atr_20'] is None or features['atr_20'] == 0:
            return False
        if features['asia_range'] is None or features['asia_range'] > (0.30 * features['atr_20']):
            return False

        # Directional alignment
        if features['orb_0900_break_dir'] is None and features['orb_1000_break_dir'] is None:
            return True
        if features['orb_0900_break_dir'] == result['break_dir']:
            return True
        if features['orb_1000_break_dir'] == result['break_dir']:
            return True
        return False

    return True


def test_configuration(con, dates_df, duration, sl_mode, rr, filter_config):
    """Test one configuration across all dates with filter"""

    results = []

    for _, row in dates_df.iterrows():
        d = row['date']

        features = {
            'atr_20': row['atr_20'],
            'asia_range': row['asia_range'],
            'asia_high': row['asia_high'],
            'asia_low': row['asia_low'],
            'orb_0900_break_dir': row['orb_0900_break_dir'],
            'orb_1000_break_dir': row['orb_1000_break_dir'],
        }

        result = simulate_trade(con, d, duration, sl_mode, rr, features)

        if result and apply_filter(result, features, filter_config):
            results.append(result)

    if len(results) < 30:  # Need at least 30 trades
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    r_multiples = [r['r_multiple'] for r in results]
    total_r = sum(r_multiples)
    avg_r = total_r / trades

    if avg_r <= 0.05:  # Must be meaningfully profitable
        return None

    # Calculate Sharpe (volatility-adjusted return)
    sharpe = avg_r / np.std(r_multiples) if np.std(r_multiples) > 0 else 0

    return Result(
        duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        filter_name=filter_config['name'],
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=total_r / 2.0,  # 2-year dataset
        median_hold_hours=np.median([r['hold_hours'] for r in results]),
        sharpe=sharpe
    )


def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE 1800 LONDON ORB SCANNER")
    print("="*80)
    print("\nSearching for BEST 1800 ORB setups with filters...")
    print("Extended scan window: Until next Asia open (09:00)")
    print("Zero lookahead: All filters use pre-18:00 data only\n")

    con = duckdb.connect("data/db/gold.db", read_only=True)

    # Get all dates with features
    dates_query = """
    SELECT date_local as date,
           atr_20,
           asia_high, asia_low, asia_range,
           orb_0900_break_dir,
           orb_1000_break_dir
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    dates_df = pd.DataFrame(con.execute(dates_query).fetchall(),
                           columns=['date', 'atr_20', 'asia_high', 'asia_low', 'asia_range',
                                   'orb_0900_break_dir', 'orb_1000_break_dir'])

    print(f"Testing across {len(dates_df)} trading days...\n")

    # Test configurations
    durations = [5, 10, 15, 30]
    sl_modes = ["FULL", "HALF", "QUARTER"]
    rr_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

    # Filter configurations (zero lookahead)
    filters = [
        {'name': 'NONE'},
        {'name': 'ATR_0.10'},  # ORB size ≤ 10% of ATR
        {'name': 'ATR_0.15'},  # ORB size ≤ 15% of ATR
        {'name': 'ATR_0.20'},  # ORB size ≤ 20% of ATR
        {'name': 'ASIA_RANGE_0.25'},  # Asia range ≤ 25% ATR (coiled)
        {'name': 'ASIA_RANGE_0.30'},  # Asia range ≤ 30% ATR
        {'name': 'ALIGN_ASIA'},  # 1800 aligns with 0900/1000 direction
        {'name': 'COMBO_COILED_ALIGNED'},  # Small Asia + aligned
    ]

    results = []
    total_configs = len(durations) * len(sl_modes) * len(rr_values) * len(filters)
    configs_tested = 0

    print(f"Total configurations to test: {total_configs}")
    print(f"This will take ~2-3 minutes...\n")

    for duration in durations:
        for sl_mode in sl_modes:
            for rr in rr_values:
                for filter_config in filters:
                    configs_tested += 1
                    result = test_configuration(con, dates_df, duration, sl_mode, rr, filter_config)
                    if result:
                        results.append(result)

                    if configs_tested % 50 == 0:
                        print(f"Progress: {configs_tested}/{total_configs} ({configs_tested/total_configs*100:.0f}%) - Found {len(results)} profitable setups", flush=True)

    con.close()

    print(f"\n{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}\n")
    print(f"Tested: {configs_tested} configurations")
    print(f"Found: {len(results)} profitable setups\n")

    if not results:
        print("⚠️ No profitable setups found for 1800 ORB!")
        print("This is unusual - check database and date range.\n")
        return

    # Sort by avg_r (best expectancy)
    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save comprehensive results
    df = pd.DataFrame([{
        'duration_min': r.duration_min,
        'sl_mode': r.sl_mode,
        'rr': r.rr,
        'filter': r.filter_name,
        'trades': r.trades,
        'wins': r.wins,
        'win_rate': r.win_rate,
        'avg_r': r.avg_r,
        'total_r': r.total_r,
        'annual_r': r.annual_r,
        'median_hold_hours': r.median_hold_hours,
        'sharpe': r.sharpe
    } for r in results])
    df.to_csv("BEST_1800_SETUPS.csv", index=False)
    print(f"✅ Full results saved: BEST_1800_SETUPS.csv\n")

    # Print TOP 30 setups
    print("="*120)
    print("TOP 30 BEST 1800 LONDON ORB SETUPS")
    print("="*120)
    print(f"{'Rank':<5} {'Dur':<5} {'SL':<8} {'RR':<5} {'Filter':<25} {'Trades':<7} {'WR%':<7} {'Avg R':<9} {'Ann R':<8} {'Sharpe':<7} {'Hold(h)':<8}")
    print("-"*120)

    for i, r in enumerate(results[:30], 1):
        print(f"{i:<5} {r.duration_min:<5} {r.sl_mode:<8} {r.rr:<5.1f} {r.filter_name:<25} {r.trades:<7} {r.win_rate*100:<7.1f} {r.avg_r:<+9.3f} {r.annual_r:<+8.0f} {r.sharpe:<7.2f} {r.median_hold_hours:<8.1f}")

    # Highlight BEST setup
    print("\n" + "="*120)
    print("🏆 BEST 1800 LONDON ORB SETUP:")
    print("="*120)
    best = results[0]
    print(f"\n  Configuration:")
    print(f"    - ORB Window: 18:00-18:{best.duration_min:02d} ({best.duration_min} minutes)")
    print(f"    - Stop Loss: {best.sl_mode}")
    print(f"    - Target: {best.rr}R")
    print(f"    - Filter: {best.filter_name}")
    print(f"\n  Performance:")
    print(f"    - Trades: {best.trades} over 2 years ({best.trades/740*100:.1f}% of days)")
    print(f"    - Win Rate: {best.win_rate*100:.1f}% ({best.wins} wins)")
    print(f"    - Avg R per trade: {best.avg_r:+.3f}R")
    print(f"    - Total return: {best.total_r:+.0f}R over 2 years")
    print(f"    - Annual return: ~{best.annual_r:+.0f}R/year")
    print(f"    - Sharpe ratio: {best.sharpe:.2f}")
    print(f"    - Median hold time: {best.median_hold_hours:.1f} hours")
    print(f"\n  Trading:")
    print(f"    - Entry: First 1m close outside ORB at 18:{best.duration_min:02d}+")
    print(f"    - Scan window: Until next Asia open (09:00)")
    print(f"    - Risk per trade: 0.10-0.25% (based on {best.annual_r:+.0f}R/year potential)")
    print("="*120)

    # Show top setups by filter type
    print("\n" + "="*120)
    print("TOP SETUP BY FILTER TYPE:")
    print("="*120)

    filter_types = list(set(r.filter_name for r in results))
    for ftype in sorted(filter_types):
        filtered_results = [r for r in results if r.filter_name == ftype]
        if filtered_results:
            best_for_filter = filtered_results[0]
            print(f"\n{ftype}:")
            print(f"  {best_for_filter.duration_min}min, {best_for_filter.sl_mode}, RR={best_for_filter.rr:.1f} → "
                  f"{best_for_filter.trades} trades, WR={best_for_filter.win_rate*100:.1f}%, "
                  f"Avg R={best_for_filter.avg_r:+.3f}, Annual={best_for_filter.annual_r:+.0f}R")

    print("\n" + "="*120)
    print("🎯 READY TO TRADE!")
    print("="*120)
    print(f"\nUse the BEST setup above, or review BEST_1800_SETUPS.csv for alternatives.")
    print(f"All setups use EXTENDED scan windows (until 09:00) and are ZERO LOOKAHEAD compliant.\n")


if __name__ == "__main__":
    main()
