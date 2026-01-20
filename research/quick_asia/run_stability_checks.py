#!/usr/bin/env python3
"""
TASK 2: Stability Checks - 365 days + 3 time splits
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import date
from asia_backtest_core import compute_metrics
from run_quick_asia_backtests import run_backtest, ORB_CONFIGS, RR_VALUES, SL_MODES

# Database
root = Path(__file__).parent.parent.parent
db_path = root / "data" / "db" / "gold.db"

def get_all_trading_days(conn, instrument, min_days=365):
    """Get maximum available trading days (up to min_days)."""
    query = """
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = ?
        AND date_local >= '2024-01-02'
        ORDER BY date_local DESC
        LIMIT ?
    """
    result = conn.execute(query, [instrument, min_days]).fetchall()
    dates = [row[0] for row in result]
    return sorted(dates)

def split_dates_into_thirds(dates):
    """Split dates into 3 equal parts."""
    n = len(dates)
    third = n // 3

    split1 = dates[:third]
    split2 = dates[third:2*third]
    split3 = dates[2*third:]

    return split1, split2, split3

def main():
    conn = duckdb.connect(str(db_path), read_only=True)

    print("="*80)
    print("TASK 2: STABILITY CHECKS")
    print("="*80)
    print()

    # Get all available days
    all_days = get_all_trading_days(conn, "MGC", 365)
    print(f"Total trading days available: {len(all_days)}")
    print(f"Date range: {min(all_days)} to {max(all_days)}")
    print()

    # === PART A: 365-day backtest ===
    print("Running 365-day backtest...")
    print("-" * 80)

    results_365 = []

    for orb_time in sorted(ORB_CONFIGS.keys()):
        for rr in RR_VALUES:
            for sl_mode in SL_MODES:
                print(f"  {orb_time} | RR={rr} | SL={sl_mode}...", end=" ")

                result = run_backtest(conn, orb_time, rr, sl_mode, "ISOLATION", all_days)

                result_clean = {k: v for k, v in result.items() if k != 'trades_list'}
                results_365.append(result_clean)

                print(f"Trades={result['trades']}, AvgR={result['avg_r']:.3f}")

    df_365 = pd.DataFrame(results_365)

    # Save
    outdir = Path("research/quick_asia")
    csv_path_365 = outdir / "asia_results_365d.csv"
    df_365.to_csv(csv_path_365, index=False)
    print(f"\nOK Saved 365-day results to: {csv_path_365}")

    # === PART B: 3 time splits ===
    print("\nRunning 3-split stability check...")
    print("-" * 80)

    split1, split2, split3 = split_dates_into_thirds(all_days)
    print(f"Split 1: {len(split1)} days ({min(split1)} to {max(split1)})")
    print(f"Split 2: {len(split2)} days ({min(split2)} to {max(split2)})")
    print(f"Split 3: {len(split3)} days ({min(split3)} to {max(split3)})")
    print()

    results_splits = []

    for orb_time in sorted(ORB_CONFIGS.keys()):
        for rr in RR_VALUES:
            for sl_mode in SL_MODES:
                print(f"  {orb_time} | RR={rr} | SL={sl_mode}...", end=" ")

                # Run on each split
                r1 = run_backtest(conn, orb_time, rr, sl_mode, "ISOLATION", split1)
                r2 = run_backtest(conn, orb_time, rr, sl_mode, "ISOLATION", split2)
                r3 = run_backtest(conn, orb_time, rr, sl_mode, "ISOLATION", split3)

                # Count positive splits
                positive_splits = sum([
                    1 if r1['avg_r'] > 0 else 0,
                    1 if r2['avg_r'] > 0 else 0,
                    1 if r3['avg_r'] > 0 else 0
                ])

                results_splits.append({
                    'orb_time': orb_time,
                    'rr': rr,
                    'sl_mode': sl_mode,
                    'split1_avg_r': r1['avg_r'],
                    'split2_avg_r': r2['avg_r'],
                    'split3_avg_r': r3['avg_r'],
                    'positive_splits': positive_splits,
                    'all_positive': positive_splits == 3,
                    'majority_positive': positive_splits >= 2
                })

                print(f"Positive splits: {positive_splits}/3")

    df_splits = pd.DataFrame(results_splits)

    # Save
    csv_path_splits = outdir / "asia_results_splits.csv"
    df_splits.to_csv(csv_path_splits, index=False)
    print(f"\nOK Saved split results to: {csv_path_splits}")

    # === Generate summary report ===
    print("\n" + "="*80)
    print("STABILITY SUMMARY")
    print("="*80)
    print()

    print("Configs with >=2/3 positive splits:")
    print("-" * 80)

    stable_configs = df_splits[df_splits['majority_positive'] == True].sort_values('positive_splits', ascending=False)

    if len(stable_configs) == 0:
        print("  No configs passed >=2/3 positive splits test")
    else:
        for idx, row in stable_configs.iterrows():
            print(f"  {row['orb_time']} | RR={row['rr']:.1f} | SL={row['sl_mode']:4s} | "
                  f"Pos splits: {row['positive_splits']}/3 | "
                  f"Split R: [{row['split1_avg_r']:+.3f}, {row['split2_avg_r']:+.3f}, {row['split3_avg_r']:+.3f}]")

    print("\n365-day top performers:")
    print("-" * 80)

    top_365 = df_365[df_365['mode'] == 'ISOLATION'].nlargest(10, 'avg_r')
    for idx, row in top_365.iterrows():
        print(f"  {row['orb_time']} | RR={row['rr']:.1f} | SL={row['sl_mode']:4s} | "
              f"AvgR={row['avg_r']:+.3f} | Trades={row['trades']}")

    # Write summary markdown
    summary_lines = []
    summary_lines.append("# STABILITY CHECK SUMMARY")
    summary_lines.append("")
    summary_lines.append(f"**Total Days**: {len(all_days)}")
    summary_lines.append(f"**Date Range**: {min(all_days)} to {max(all_days)}")
    summary_lines.append("")
    summary_lines.append("## Configs with >=2/3 Positive Splits")
    summary_lines.append("")

    if len(stable_configs) > 0:
        summary_lines.append("| ORB | RR | SL Mode | Pos Splits | Split 1 | Split 2 | Split 3 |")
        summary_lines.append("|-----|-----|---------|------------|---------|---------|---------|")

        for idx, row in stable_configs.iterrows():
            summary_lines.append(
                f"| {row['orb_time']} | {row['rr']:.1f} | {row['sl_mode']} | "
                f"{row['positive_splits']}/3 | {row['split1_avg_r']:+.3f} | "
                f"{row['split2_avg_r']:+.3f} | {row['split3_avg_r']:+.3f} |"
            )
    else:
        summary_lines.append("No configs passed >=2/3 positive splits test.")

    summary_lines.append("")
    summary_lines.append("## 365-Day Top 10")
    summary_lines.append("")
    summary_lines.append("| ORB | RR | SL Mode | Avg R | Trades | Win Rate | Total R |")
    summary_lines.append("|-----|-----|---------|-------|--------|----------|---------|")

    for idx, row in top_365.iterrows():
        summary_lines.append(
            f"| {row['orb_time']} | {row['rr']:.1f} | {row['sl_mode']} | "
            f"{row['avg_r']:+.3f}R | {row['trades']} | {row['win_rate']*100:.1f}% | "
            f"{row['total_r']:+.1f}R |"
        )

    summary_path = outdir / "asia_stability_summary.md"
    with open(summary_path, 'w') as f:
        f.write("\n".join(summary_lines))

    print(f"\nOK Saved stability summary to: {summary_path}")
    print("\n" + "="*80)
    print("STABILITY CHECKS COMPLETE")
    print("="*80)

    conn.close()

if __name__ == "__main__":
    main()
