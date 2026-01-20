#!/usr/bin/env python3
"""
Quick Asia Session Backtests - MGC 0900/1000/1100 ORBs

Runs fast backtests with HALF vs FULL SL comparison.
Tests both ISOLATION and CONTINUATION modes.
"""

import duckdb
import pandas as pd
import argparse
from pathlib import Path
from datetime import date, timedelta
from asia_backtest_core import (
    compute_orb_levels,
    simulate_orb_breakout,
    compute_metrics,
    compute_trades_hash
)

# ORB configurations
ORB_CONFIGS = {
    "0900": {"hour": 9, "min": 0, "scan_end_hour": 11, "scan_end_min": 0},
    "1000": {"hour": 10, "min": 0, "scan_end_hour": 12, "scan_end_min": 0},
    "1100": {"hour": 11, "min": 0, "scan_end_hour": 13, "scan_end_min": 0},
}

RR_VALUES = [1.0, 1.5, 2.0, 3.0]
SL_MODES = ["HALF", "FULL"]
BACKTEST_MODES = ["ISOLATION", "CONTINUATION"]

def get_trading_days(conn, instrument, days):
    """Get last N trading days with data."""
    query = """
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = ?
        AND date_local >= '2024-01-02'
        ORDER BY date_local DESC
        LIMIT ?
    """
    result = conn.execute(query, [instrument, days]).fetchall()
    dates = [row[0] for row in result]
    return sorted(dates)  # Return in ascending order

def run_backtest(conn, orb_time, rr, sl_mode, mode, trading_days):
    """Run backtest for a single configuration."""
    config = ORB_CONFIGS[orb_time]
    trades = []

    for trading_date in trading_days:
        # Compute ORB
        orb = compute_orb_levels(
            conn,
            trading_date,
            config["hour"],
            config["min"]
        )

        if orb is None:
            continue

        # Simulate trade
        trade = simulate_orb_breakout(
            conn,
            trading_date,
            orb,
            config["hour"],
            config["min"],
            config["scan_end_hour"],
            config["scan_end_min"],
            rr,
            sl_mode,
            mode
        )

        if trade is not None:
            trades.append(trade)

    # Compute metrics
    metrics = compute_metrics(trades)

    return {
        'orb_time': orb_time,
        'rr': rr,
        'sl_mode': sl_mode,
        'mode': mode,
        **metrics,
        'trades_list': trades  # Keep for hashing
    }

def run_sanity_checks(conn, trading_days):
    """Run hard sanity checks for zero-lookahead compliance."""
    print("\n" + "="*80)
    print("RUNNING SANITY CHECKS")
    print("="*80 + "\n")

    passed = True

    # Test 1: Determinism check
    print("Test 1: Determinism (run same config twice)...")
    result1 = run_backtest(conn, "0900", 1.5, "HALF", "ISOLATION", trading_days)
    result2 = run_backtest(conn, "0900", 1.5, "HALF", "ISOLATION", trading_days)

    hash1 = compute_trades_hash(result1['trades_list'])
    hash2 = compute_trades_hash(result2['trades_list'])

    if hash1 == hash2:
        print(f"  PASS - Trades hash matches: {hash1}")
    else:
        print(f"  FAIL - Trades hash mismatch!")
        print(f"    Run 1: {hash1}")
        print(f"    Run 2: {hash2}")
        passed = False

    # Test 2: No lookahead violations (checked by assertions in core)
    print("\nTest 2: Zero-lookahead compliance...")
    try:
        # Run a config - if assertions fail, exception will be raised
        run_backtest(conn, "1000", 2.0, "FULL", "ISOLATION", trading_days[:10])
        print("  OK PASS - No lookahead violations detected")
    except AssertionError as e:
        print(f"  FAIL - Lookahead violation: {e}")
        passed = False

    # Test 3: Entry after ORB completes
    print("\nTest 3: All entries after ORB completion...")
    test_result = run_backtest(conn, "1100", 1.0, "HALF", "ISOLATION", trading_days[:20])
    early_entries = [t for t in test_result['trades_list']
                     if t.entry_ts.minute < 5 and t.entry_ts.hour == 11]

    if len(early_entries) == 0:
        print(f"  PASS - No entries before ORB completes")
    else:
        print(f"  FAIL - Found {len(early_entries)} entries before ORB completion")
        passed = False

    # Test 4: ISOLATION exits within window
    print("\nTest 4: ISOLATION mode exits within scan window...")
    iso_result = run_backtest(conn, "0900", 1.5, "HALF", "ISOLATION", trading_days[:20])
    late_exits = [t for t in iso_result['trades_list']
                  if t.exit_ts is not None and
                  (t.exit_ts.hour > 11 or (t.exit_ts.hour == 11 and t.exit_ts.minute > 0))]

    if len(late_exits) == 0:
        print(f"  PASS - All ISOLATION exits within window")
    else:
        print(f"  FAIL - Found {len(late_exits)} exits outside window")
        passed = False

    print("\n" + "="*80)
    if passed:
        print("ALL SANITY CHECKS PASSED OK")
    else:
        print("SOME SANITY CHECKS FAILED FAIL")
        print("CRITICAL: Do not use results until failures are resolved")
    print("="*80 + "\n")

    return passed

def main():
    parser = argparse.ArgumentParser(description="Quick Asia Session Backtests")
    parser.add_argument("--instrument", default="MGC", help="Instrument symbol")
    parser.add_argument("--days", type=int, default=120, help="Number of trading days to test")
    parser.add_argument("--outdir", default="research/quick_asia", help="Output directory")

    args = parser.parse_args()

    # Setup
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Database path (relative to project root, not current dir)
    root = Path(__file__).parent.parent.parent
    db_path = root / "data" / "db" / "gold.db"
    conn = duckdb.connect(str(db_path), read_only=True)

    print("="*80)
    print(f"QUICK ASIA BACKTESTS - {args.instrument}")
    print("="*80)
    print(f"Instrument: {args.instrument}")
    print(f"Days: {args.days}")
    print(f"Output: {outdir}")
    print("="*80 + "\n")

    # Get trading days
    trading_days = get_trading_days(conn, args.instrument, args.days)
    print(f"Trading days: {len(trading_days)}")
    print(f"Date range: {min(trading_days)} to {max(trading_days)}\n")

    # Run sanity checks
    sanity_passed = run_sanity_checks(conn, trading_days)

    # Run all configurations
    print("\n" + "="*80)
    print("RUNNING ALL CONFIGURATIONS")
    print("="*80 + "\n")

    all_results = []

    total_configs = len(ORB_CONFIGS) * len(RR_VALUES) * len(SL_MODES) * len(BACKTEST_MODES)
    current = 0

    for orb_time in sorted(ORB_CONFIGS.keys()):
        for rr in RR_VALUES:
            for sl_mode in SL_MODES:
                for mode in BACKTEST_MODES:
                    current += 1
                    print(f"[{current}/{total_configs}] {orb_time} | RR={rr} | SL={sl_mode} | Mode={mode}...", end=" ")

                    result = run_backtest(conn, orb_time, rr, sl_mode, mode, trading_days)

                    # Remove trades_list before storing (too large)
                    result_clean = {k: v for k, v in result.items() if k != 'trades_list'}
                    all_results.append(result_clean)

                    print(f"Trades={result['trades']}, AvgR={result['avg_r']:.3f}")

    conn.close()

    # Convert to DataFrame
    df = pd.DataFrame(all_results)

    # Save CSV
    csv_path = outdir / "asia_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nOK Saved results to: {csv_path}")

    # Generate report
    report_lines = []
    report_lines.append("# QUICK ASIA BACKTESTS - RESULTS")
    report_lines.append("")
    report_lines.append(f"**Instrument**: {args.instrument}")
    report_lines.append(f"**Trading Days**: {len(trading_days)}")
    report_lines.append(f"**Date Range**: {min(trading_days)} to {max(trading_days)}")
    report_lines.append(f"**Configurations Tested**: {total_configs}")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    # Top 5 per ORB per mode
    for mode in BACKTEST_MODES:
        report_lines.append(f"## {mode} MODE")
        report_lines.append("")

        for orb_time in sorted(ORB_CONFIGS.keys()):
            orb_df = df[(df['orb_time'] == orb_time) & (df['mode'] == mode)]
            top5 = orb_df.nlargest(5, 'avg_r')

            report_lines.append(f"### {orb_time} ORB - Top 5 Configs")
            report_lines.append("")
            report_lines.append("| Rank | RR | SL Mode | Trades | Win Rate | Avg R | Total R | PF | Max DD |")
            report_lines.append("|------|-----|---------|--------|----------|-------|---------|-----|--------|")

            for idx, (i, row) in enumerate(top5.iterrows(), 1):
                report_lines.append(
                    f"| {idx} | {row['rr']:.1f} | {row['sl_mode']} | {row['trades']} | "
                    f"{row['win_rate']*100:.1f}% | {row['avg_r']:+.3f}R | "
                    f"{row['total_r']:+.1f}R | {row['profit_factor']:.2f} | {row['max_dd_r']:.1f}R |"
                )

            report_lines.append("")

    # Save report
    report_path = outdir / "asia_report.md"
    with open(report_path, 'w') as f:
        f.write("\n".join(report_lines))

    print(f"OK Saved report to: {report_path}")

    # Save sanity report
    sanity_path = outdir / "asia_sanity.md"
    with open(sanity_path, 'w') as f:
        f.write("# SANITY CHECK RESULTS\n\n")
        if sanity_passed:
            f.write("**Status**: OK ALL CHECKS PASSED\n\n")
            f.write("The backtest engine is zero-lookahead compliant and deterministic.\n")
        else:
            f.write("**Status**: FAIL SOME CHECKS FAILED\n\n")
            f.write("CRITICAL: Do not use results until failures are resolved.\n")

    print(f"OK Saved sanity report to: {sanity_path}")

    # Print top 5 to console
    print("\n" + "="*80)
    print("TOP 5 CONFIGS PER ORB (ISOLATION MODE)")
    print("="*80 + "\n")

    for orb_time in sorted(ORB_CONFIGS.keys()):
        orb_df = df[(df['orb_time'] == orb_time) & (df['mode'] == 'ISOLATION')]
        top5 = orb_df.nlargest(5, 'avg_r')

        print(f"{orb_time} ORB:")
        for idx, (i, row) in enumerate(top5.iterrows(), 1):
            print(f"  {idx}. RR={row['rr']:.1f} {row['sl_mode']:4s} | "
                  f"Trades={row['trades']:3d} | WR={row['win_rate']*100:5.1f}% | "
                  f"AvgR={row['avg_r']:+.3f} | TotalR={row['total_r']:+6.1f}")
        print()

    print("="*80)
    print("BACKTEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
