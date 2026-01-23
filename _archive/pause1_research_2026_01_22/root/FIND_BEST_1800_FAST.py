"""
FAST 1800 LONDON ORB SCANNER
=============================

Quick scan focused on most promising configs based on research:
- 5-min ORB (standard)
- FULL SL (research shows best for 1800)
- RR: 1.0-4.0 (most practical)
- All filters

Should complete in under 60 seconds.
"""

import duckdb
from datetime import date, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np

SYMBOL = "MGC"

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
    sharpe: float


def test_config_fast(con, orb_col, dates_df, rr, filter_config):
    """Fast test using pre-computed ORBs from daily_features_v2"""

    results = []

    for _, row in dates_df.iterrows():
        # Get ORB data (already computed)
        orb_high = row[f'{orb_col}_high']
        orb_low = row[f'{orb_col}_low']
        break_dir = row[f'{orb_col}_break_dir']
        r_multiple = row[f'{orb_col}_r_multiple']

        if pd.isna(break_dir) or break_dir == 'NONE':
            continue

        # Apply filter (zero lookahead)
        if not apply_filter_fast(row, filter_config, orb_col):
            continue

        # Simulate outcome with new RR
        orb_size = orb_high - orb_low
        orb_edge = orb_high if break_dir == 'UP' else orb_low
        stop = orb_low if break_dir == 'UP' else orb_high  # FULL SL
        r_size = abs(orb_edge - stop)

        if r_size <= 0:
            continue

        # Get actual R achieved (from r_multiple in table)
        actual_r = r_multiple if not pd.isna(r_multiple) else 0.0

        # Determine outcome with new RR target
        if actual_r >= rr:
            results.append({'r': float(rr), 'outcome': 'WIN'})
        elif actual_r <= -1.0:
            results.append({'r': -1.0, 'outcome': 'LOSS'})
        else:
            # Didn't hit either TP or SL (treat as scratch/small loss)
            results.append({'r': actual_r, 'outcome': 'OPEN'})

    if len(results) < 30:
        return None

    wins = sum(1 for r in results if r['outcome'] == 'WIN')
    trades = len(results)
    win_rate = wins / trades
    r_values = [r['r'] for r in results]
    total_r = sum(r_values)
    avg_r = total_r / trades

    if avg_r <= 0.05:
        return None

    sharpe = avg_r / np.std(r_values) if np.std(r_values) > 0 else 0

    return Result(
        duration_min=5,
        sl_mode="FULL",
        rr=rr,
        filter_name=filter_config['name'],
        trades=trades,
        wins=wins,
        win_rate=win_rate,
        avg_r=avg_r,
        total_r=total_r,
        annual_r=total_r / 2.0,
        sharpe=sharpe
    )


def apply_filter_fast(row, filter_config, orb_col):
    """Apply pre-session filters (zero lookahead)"""

    filter_name = filter_config['name']

    if filter_name == "NONE":
        return True

    # ATR-based ORB size filter
    if filter_name.startswith("ATR_"):
        max_ratio = float(filter_name.split('_')[1])
        orb_size = row[f'{orb_col}_size']
        atr = row['atr_20']
        if pd.isna(atr) or atr == 0 or pd.isna(orb_size):
            return False
        return orb_size <= (max_ratio * atr)

    # Asia range filter (coiled = ready to expand)
    if filter_name.startswith("ASIA_RANGE_"):
        max_ratio = float(filter_name.split('_')[2])
        asia_range = row['asia_range']
        atr = row['atr_20']
        if pd.isna(atr) or atr == 0 or pd.isna(asia_range):
            return False
        return asia_range <= (max_ratio * atr)

    # Directional alignment with prior ORBs
    if filter_name == "ALIGN_ASIA":
        break_dir = row[f'{orb_col}_break_dir']
        dir_0900 = row['orb_0900_break_dir']
        dir_1000 = row['orb_1000_break_dir']

        if pd.isna(dir_0900) and pd.isna(dir_1000):
            return True

        if dir_0900 == break_dir or dir_1000 == break_dir:
            return True
        return False

    # Combination: coiled + aligned
    if filter_name == "COMBO_COILED_ALIGNED":
        # Asia coiled
        asia_range = row['asia_range']
        atr = row['atr_20']
        if pd.isna(atr) or atr == 0 or pd.isna(asia_range) or asia_range > (0.30 * atr):
            return False

        # Aligned
        break_dir = row[f'{orb_col}_break_dir']
        dir_0900 = row['orb_0900_break_dir']
        dir_1000 = row['orb_1000_break_dir']

        if pd.isna(dir_0900) and pd.isna(dir_1000):
            return True

        if dir_0900 == break_dir or dir_1000 == break_dir:
            return True
        return False

    return True


def main():
    print("\n" + "="*80)
    print("FAST 1800 LONDON ORB SCANNER")
    print("="*80)
    print("\nOptimized for speed using pre-computed daily_features_v2")
    print("Testing: 5-min ORB, FULL SL, RR 1.0-5.0, all filters\n")

    con = duckdb.connect("data/db/gold.db", read_only=True)

    # Get all 1800 ORB data with context
    query = """
    SELECT date_local as date,
           atr_20,
           asia_high, asia_low, asia_range,
           orb_0900_break_dir,
           orb_1000_break_dir,
           orb_1800_high,
           orb_1800_low,
           orb_1800_size,
           orb_1800_break_dir,
           orb_1800_r_multiple
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    dates_df = pd.DataFrame(con.execute(query).fetchall(),
                           columns=['date', 'atr_20', 'asia_high', 'asia_low', 'asia_range',
                                   'orb_0900_break_dir', 'orb_1000_break_dir',
                                   'orb_1800_high', 'orb_1800_low', 'orb_1800_size',
                                   'orb_1800_break_dir', 'orb_1800_r_multiple'])

    print(f"Found {len(dates_df)} trading days\n")

    # Test configurations
    rr_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]

    filters = [
        {'name': 'NONE'},
        {'name': 'ATR_0.10'},
        {'name': 'ATR_0.15'},
        {'name': 'ATR_0.20'},
        {'name': 'ATR_0.25'},
        {'name': 'ASIA_RANGE_0.20'},
        {'name': 'ASIA_RANGE_0.25'},
        {'name': 'ASIA_RANGE_0.30'},
        {'name': 'ALIGN_ASIA'},
        {'name': 'COMBO_COILED_ALIGNED'},
    ]

    total_configs = len(rr_values) * len(filters)
    print(f"Total configs: {total_configs}")
    print("Running...\n")

    results = []

    for rr in rr_values:
        for filter_config in filters:
            result = test_config_fast(con, 'orb_1800', dates_df, rr, filter_config)
            if result:
                results.append(result)

    con.close()

    print(f"{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}\n")
    print(f"Found: {len(results)} profitable setups\n")

    if not results:
        print("[WARNING] No profitable setups found!")
        return

    # Sort by avg_r
    results.sort(key=lambda x: x.avg_r, reverse=True)

    # Save
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
        'sharpe': r.sharpe
    } for r in results])
    df.to_csv("BEST_1800_SETUPS_FAST.csv", index=False)
    print(f"[OK] Results saved: BEST_1800_SETUPS_FAST.csv\n")

    # Print TOP 20
    print("="*100)
    print("TOP 20 BEST 1800 LONDON ORB SETUPS")
    print("="*100)
    print(f"{'Rank':<5} {'RR':<5} {'Filter':<25} {'Trades':<7} {'WR%':<7} {'Avg R':<9} {'Ann R':<8} {'Sharpe':<7}")
    print("-"*100)

    for i, r in enumerate(results[:20], 1):
        print(f"{i:<5} {r.rr:<5.1f} {r.filter_name:<25} {r.trades:<7} {r.win_rate*100:<7.1f} {r.avg_r:<+9.3f} {r.annual_r:<+8.0f} {r.sharpe:<7.2f}")

    # Best setup
    print("\n" + "="*100)
    print("[BEST] 1800 LONDON ORB SETUP FOR LIVE TRADING:")
    print("="*100)
    best = results[0]
    print(f"\n  [CONFIG]:")
    print(f"     ORB Window: 18:00-18:05 (5 minutes)")
    print(f"     Stop Loss: FULL (opposite ORB edge)")
    print(f"     Target: {best.rr}R")
    print(f"     Filter: {best.filter_name}")
    print(f"\n  [PERFORMANCE] (2024-01-02 to 2026-01-10):")
    print(f"     Trades: {best.trades} ({best.trades/740*100:.1f}% of days)")
    print(f"     Win Rate: {best.win_rate*100:.1f}% ({best.wins} winners)")
    print(f"     Avg R: {best.avg_r:+.3f}R per trade")
    print(f"     Total: {best.total_r:+.0f}R over 2 years")
    print(f"     Annual: ~{best.annual_r:+.0f}R/year")
    print(f"     Sharpe: {best.sharpe:.2f}")
    print(f"\n  [ENTRY RULES]:")
    print(f"     1. Wait for 18:00-18:05 ORB to form")
    print(f"     2. Check filter: {best.filter_name}")
    print(f"     3. Enter on FIRST 1m close outside ORB")
    print(f"     4. Stop: Opposite ORB edge")
    print(f"     5. Target: {best.rr}R from entry")
    print(f"\n  [POSITION SIZING]:")
    print(f"     Risk per trade: 0.10-0.25% (conservative for {best.annual_r:+.0f}R/year edge)")
    print("="*100)

    # Top by filter type
    print("\n" + "="*100)
    print("TOP SETUP BY EACH FILTER:")
    print("="*100)

    filter_types = sorted(list(set(r.filter_name for r in results)))
    for ftype in filter_types:
        filtered_results = [r for r in results if r.filter_name == ftype]
        if filtered_results:
            best_for_filter = filtered_results[0]
            print(f"\n{ftype:25} RR={best_for_filter.rr:.1f} -> "
                  f"{best_for_filter.trades} trades, WR={best_for_filter.win_rate*100:.1f}%, "
                  f"Avg R={best_for_filter.avg_r:+.3f}, Annual={best_for_filter.annual_r:+.0f}R")

    print("\n" + "="*100)
    print("[READY] READY TO TRADE IN 30 MINUTES!")
    print("="*100)
    print(f"\nUse the BEST setup above for your 18:00 London session today.")
    print(f"Full results available in: BEST_1800_SETUPS_FAST.csv\n")


if __name__ == "__main__":
    main()
