#!/usr/bin/env python3
"""
Unicorn Backtest Runner - FIXED VERSION
Now properly recomputes outcomes for each RR/SL combination instead of reusing stored values.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, time as dt_time, timedelta
import pandas as pd
import numpy as np
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_app.cloud_mode import get_database_connection

# Paths
ROOT = Path(__file__).parent.parent
CATALOG_PATH = ROOT / "research" / "unicorn_catalog.json"
OUTPUT_DIR = ROOT / "research"

# Date range
START_DATE = "2024-01-02"
END_DATE = "2026-01-10"

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")


def load_catalog():
    """Load setup catalog from JSON."""
    with open(CATALOG_PATH, 'r') as f:
        return json.load(f)


def backtest_setup_from_bars(setup_config):
    """
    Backtest a setup by recomputing outcomes from bars_1m.

    This is the CORRECT approach - each RR/SL combo gets fresh computation.

    Args:
        setup_config: Setup configuration dict from catalog

    Returns:
        List of r_multiples (one per trade)
    """
    conn = get_database_connection()

    instrument = setup_config['instrument']
    orb_time = setup_config['orb_time']
    rr = setup_config['rr']
    sl_mode = setup_config['sl_mode']

    # Parse ORB time
    orb_hour = int(orb_time[:2])
    orb_minute = int(orb_time[2:])
    orb_start_time = dt_time(orb_hour, orb_minute)
    orb_end_time = (datetime.combine(datetime.today(), orb_start_time) + timedelta(minutes=5)).time()

    # Get filters
    filters = setup_config.get('filters', {})

    # Get trading dates
    dates_df = conn.execute(f"""
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = '{instrument}'
        AND date_local >= '{START_DATE}'
        AND date_local <= '{END_DATE}'
        ORDER BY date_local
    """).fetchdf()

    trades = []

    for trading_date_str in dates_df['date_local']:
        trading_date = pd.to_datetime(trading_date_str).date()

        # Load 1-minute bars for this trading day (09:00 → next 09:00)
        start_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))
        end_dt_local = start_dt_local + timedelta(days=1)

        start_dt_utc = start_dt_local.astimezone(pytz.utc)
        end_dt_utc = end_dt_local.astimezone(pytz.utc)

        bars = conn.execute("""
            SELECT ts_utc, open, high, low, close, volume
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc >= ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """, [instrument, start_dt_utc, end_dt_utc]).fetchdf()

        if len(bars) == 0:
            continue

        bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
        bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
        bars['time_local'] = bars['ts_local'].dt.time

        # Calculate ORB from 5-minute window
        orb_bars = bars[
            (bars['time_local'] >= orb_start_time) &
            (bars['time_local'] < orb_end_time)
        ]

        if len(orb_bars) == 0:
            continue

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_size = orb_high - orb_low
        orb_midpoint = (orb_high + orb_low) / 2.0

        # Apply ORB size filters
        if 'orb_size_filter' in filters:
            # Get ATR for this day
            atr_row = conn.execute(f"""
                SELECT atr_20
                FROM daily_features_v2
                WHERE instrument = '{instrument}'
                AND date_local = '{trading_date_str}'
            """).fetchone()

            if atr_row and atr_row[0]:
                atr_20 = atr_row[0]
                filter_value = filters['orb_size_filter']
                filter_type = filters.get('orb_size_filter_type', 'atr_ratio_max')

                if filter_type == 'atr_ratio_max':
                    if orb_size > filter_value * atr_20:
                        continue  # Skip this day

        # Detect breakout (first 1-minute close outside ORB)
        post_orb_bars = bars[bars['time_local'] >= orb_end_time]

        entry_bar = None
        direction = None

        for idx, bar in post_orb_bars.iterrows():
            if bar['close'] > orb_high:
                entry_bar = bar
                direction = 'UP'
                break
            elif bar['close'] < orb_low:
                entry_bar = bar
                direction = 'DOWN'
                break

        if entry_bar is None:
            continue  # No breakout

        # Calculate stop and target based on THIS setup's RR and SL mode
        entry_price = entry_bar['close']

        if sl_mode == 'HALF':
            stop_price = orb_midpoint
        else:  # FULL
            stop_price = orb_low if direction == 'UP' else orb_high

        if direction == 'UP':
            risk = entry_price - stop_price
            target_price = entry_price + (risk * rr)
        else:
            risk = stop_price - entry_price
            target_price = entry_price - (risk * rr)

        if risk <= 0:
            continue  # Invalid risk

        # Get remaining bars and check resolution
        remaining_bars = bars[bars['ts_local'] > entry_bar['ts_local']]

        outcome = None
        r_multiple = 0.0

        for idx, bar in remaining_bars.iterrows():
            if direction == 'UP':
                if bar['low'] <= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['high'] >= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break
            else:
                if bar['high'] >= stop_price:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    break
                if bar['low'] <= target_price:
                    outcome = 'WIN'
                    r_multiple = rr
                    break

        if outcome is None and len(remaining_bars) > 0:
            # Time exit
            final_bar = remaining_bars.iloc[-1]
            final_price = final_bar['close']
            pnl = (final_price - entry_price) if direction == 'UP' else (entry_price - final_price)
            r_multiple = pnl / risk if risk != 0 else 0
            outcome = 'TIME_EXIT'

        if outcome and outcome != 'NO_TRADE':
            trades.append(r_multiple)

    return trades


def calculate_metrics(r_multiples):
    """Calculate performance metrics from R multiples."""
    if len(r_multiples) == 0:
        return {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'max_dd_r': 0.0,
            'annual_trades': 0.0
        }

    arr = np.array(r_multiples)
    total = len(arr)
    wins = (arr > 0).sum()
    losses = (arr < 0).sum()

    win_rate = (wins / total * 100) if total > 0 else 0.0
    avg_r = arr.mean()
    total_r = arr.sum()

    # Max drawdown
    equity_curve = np.cumsum(np.concatenate([[0], arr]))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve - running_max
    max_dd = abs(drawdowns.min()) if len(drawdowns) > 0 else 0.0

    # Annualize
    date_range = (pd.to_datetime(END_DATE) - pd.to_datetime(START_DATE)).days
    years = date_range / 365.25
    annual_trades = total / years if years > 0 else 0.0

    return {
        'trades': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'max_dd_r': max_dd,
        'annual_trades': annual_trades,
        'years': years
    }


def main():
    """Run comprehensive backtest on all catalogued setups."""
    print("=" * 80)
    print("UNICORN BACKTEST RUNNER (FIXED)")
    print("Now properly recomputes outcomes for each RR/SL combination")
    print("=" * 80)
    print()
    print(f"Date Range: {START_DATE} to {END_DATE}")
    print(f"Data Source: bars_1m (recomputed per setup)")
    print()

    # Load catalog
    catalog = load_catalog()
    setups = catalog['setups']

    print(f"Testing {len(setups)} setups...")
    print()

    results = []

    for idx, setup in enumerate(setups, 1):
        setup_id = setup['id']
        print(f"[{idx}/{len(setups)}] {setup_id}...", end=' ', flush=True)

        try:
            # Backtest this setup from bars_1m
            r_multiples = backtest_setup_from_bars(setup)

            # Calculate metrics
            metrics = calculate_metrics(r_multiples)

            # Store results
            result = {
                'setup_id': setup_id,
                'name': setup['name'],
                'source': setup['source'],
                'orb_time': setup['orb_time'],
                'rr': setup['rr'],
                'sl_mode': setup['sl_mode'],
                'scan_window': setup['scan_window'],
                **metrics
            }

            results.append(result)

            print(f"{metrics['trades']} trades | {metrics['win_rate']:.1f}% WR | {metrics['avg_r']:+.3f}R avg | {metrics['total_r']:+.1f}R total")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'setup_id': setup_id,
                'name': setup['name'],
                'error': str(e)
            })

    print()
    print("=" * 80)
    print("CORRECTNESS PROOF")
    print("=" * 80)
    print()

    # Proof: Compare setups with same ORB time but different RR
    results_df = pd.DataFrame(results)
    valid_results = results_df[~results_df['avg_r'].isna()].copy()

    if len(valid_results) > 0:
        # Find 1000 ORB setups with different RRs
        orb_1000 = valid_results[valid_results['orb_time'] == '1000'].copy()
        orb_1000_sorted = orb_1000.sort_values('rr')

        if len(orb_1000_sorted) >= 2:
            print("PROOF: Different RR values produce different avg_r:")
            print()
            for idx, row in orb_1000_sorted.iterrows():
                print(f"  {row['setup_id']}: RR={row['rr']}, avg_r={row['avg_r']:+.3f}R")
            print()
            print("✓ If these avg_r values are DIFFERENT, the fix is working!")
            print("✗ If they are IDENTICAL, there's still a bug.")
            print()

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    if len(valid_results) == 0:
        print("ERROR: No valid results!")
        return

    # Sort by avg_r
    valid_results = valid_results.sort_values('avg_r', ascending=False)

    # Display top 10
    print("TOP 10 SETUPS BY AVG R:")
    print()
    cols = ['setup_id', 'orb_time', 'rr', 'sl_mode', 'trades', 'win_rate', 'avg_r', 'total_r', 'max_dd_r']
    print(valid_results[cols].head(10).to_string(index=False))
    print()

    # Save full results to CSV
    output_csv = OUTPUT_DIR / 'unicorn_scan_results_fixed.csv'
    valid_results.to_csv(output_csv, index=False)
    print(f"[OK] Saved full results to {output_csv}")
    print()

    # Generate markdown report
    generate_markdown_report(valid_results, OUTPUT_DIR / 'unicorn_scan_results_fixed.md')

    print("=" * 80)
    print("DONE")
    print("=" * 80)


def generate_markdown_report(results_df, output_path):
    """Generate markdown report with ranked setups."""

    with open(output_path, 'w') as f:
        f.write("# Unicorn Setups - Comprehensive Backtest Results (FIXED)\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Test Period**: {START_DATE} to {END_DATE}\n")
        f.write(f"**Data Source**: bars_1m (recomputed per setup)\n")
        f.write(f"**Setups Tested**: {len(results_df)}\n\n")
        f.write("**FIX**: Each RR/SL combination now properly recomputes outcomes from bars_1m\n\n")
        f.write("---\n\n")

        f.write("## TOP 10 SETUPS BY AVG R\n\n")
        f.write("| Rank | Setup ID | ORB | RR | SL | Trades | WR% | Avg R | Total R | Max DD |\n")
        f.write("|------|----------|-----|----|----|--------|-----|-------|---------|--------|\n")

        for rank, (idx, row) in enumerate(results_df.head(10).iterrows(), 1):
            f.write(f"| {rank} | {row['setup_id']} | {row['orb_time']} | {row['rr']}R | {row['sl_mode']} | ")
            f.write(f"{row['trades']} | {row['win_rate']:.1f}% | {row['avg_r']:+.3f}R | ")
            f.write(f"{row['total_r']:+.1f}R | {row['max_dd_r']:.1f}R |\n")

        f.write("\n---\n\n")
        f.write("## KEY FINDINGS\n\n")

        winner = results_df.iloc[0]
        f.write(f"**WINNER**: {winner['setup_id']}\n\n")
        f.write(f"- **ORB Time**: {winner['orb_time']}\n")
        f.write(f"- **RR Target**: {winner['rr']}R\n")
        f.write(f"- **Stop Mode**: {winner['sl_mode']}\n")
        f.write(f"- **Trades**: {winner['trades']} ({winner['annual_trades']:.0f}/year)\n")
        f.write(f"- **Win Rate**: {winner['win_rate']:.1f}%\n")
        f.write(f"- **Avg R**: {winner['avg_r']:+.3f}R\n")
        f.write(f"- **Total R**: {winner['total_r']:+.1f}R over {winner['years']:.1f} years\n")
        f.write(f"- **Max Drawdown**: {winner['max_dd_r']:.1f}R\n\n")

        f.write("---\n\n")
        f.write("## FULL RESULTS\n\n")
        f.write("See `unicorn_scan_results_fixed.csv` for complete data.\n")

    print(f"[OK] Saved markdown report to {output_path}")


if __name__ == "__main__":
    main()
