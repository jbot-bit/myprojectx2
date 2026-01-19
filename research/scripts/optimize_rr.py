"""
RR Optimization - Universal (MGC, NQ & MPL)
============================================

Tests different Risk:Reward ratios for each ORB to find optimal target distance.

Usage:
  python scripts/optimize_rr.py MGC          # Test all ORBs for MGC
  python scripts/optimize_rr.py NQ           # Test all ORBs for NQ
  python scripts/optimize_rr.py MPL          # Test all ORBs for MPL
  python scripts/optimize_rr.py MGC 0030     # Test specific ORB only
  python scripts/optimize_rr.py NQ 0030 --sl-mode half  # Test with HALF SL

Strategy:
  - Test RR values: 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0
  - For each RR, calculate win rate and avg R from existing features
  - Find RR with highest expectancy (avg R)
  - Report if optimal differs from baseline (1.0)
"""

import sys
import duckdb
from typing import Dict, List, Optional

DB_PATH = "gold.db"

# ORB times to test
ORBS = ['0900', '1000', '1100', '1800', '2300', '0030']

# RR values to test
RR_VALUES = [1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]


def get_table_name(symbol: str) -> str:
    """Get feature table name for symbol"""
    if symbol == "MGC":
        return "daily_features_v2"
    elif symbol == "NQ":
        return "daily_features_v2_nq"
    elif symbol == "MPL":
        return "daily_features_v2_mpl"
    else:
        raise ValueError(f"Unknown symbol: {symbol}")


def get_tick_size(symbol: str) -> float:
    """Get tick size for symbol"""
    if symbol == "MGC":
        return 0.1
    elif symbol == "NQ":
        return 0.25
    elif symbol == "MPL":
        return 0.1
    else:
        raise ValueError(f"Unknown symbol: {symbol}")


def optimize_orb_rr(con: duckdb.DuckDBPyConnection, symbol: str, orb: str, sl_mode: str = "full") -> Dict:
    """
    Find optimal RR for a specific ORB by testing multiple values.

    Uses existing feature calculations to avoid recalculating outcomes.
    For each RR value, counts wins (where MFE >= RR) and calculates expectancy.

    Args:
        con: Database connection
        symbol: 'MGC' or 'NQ'
        orb: ORB time ('0900', '1000', etc.)
        sl_mode: 'full' or 'half' (currently assumes features match this)

    Returns:
        Dict with optimization results
    """
    table = get_table_name(symbol)
    tick_size = get_tick_size(symbol)

    # Get all trades with MAE/MFE data
    query = f"""
        SELECT
            orb_{orb}_break_dir as direction,
            orb_{orb}_mae as mae,
            orb_{orb}_mfe as mfe,
            orb_{orb}_size as orb_size
        FROM {table}
        WHERE orb_{orb}_break_dir IN ('UP', 'DOWN')
            AND orb_{orb}_mae IS NOT NULL
            AND orb_{orb}_mfe IS NOT NULL
    """

    trades = con.execute(query).fetchall()

    if len(trades) == 0:
        return {
            'orb': orb,
            'symbol': symbol,
            'total_trades': 0,
            'optimal_rr': None,
            'optimal_win_rate': 0,
            'optimal_avg_r': 0,
            'improvement_vs_1r': 0
        }

    results = []

    # Test each RR value
    for rr in RR_VALUES:
        wins = 0
        losses = 0
        total_r = 0

        for direction, mae, mfe, orb_size in trades:
            # Check if trade hits target (MFE >= RR)
            if mfe >= rr:
                wins += 1
                total_r += rr
            # Check if trade hits stop (MAE >= 1.0)
            elif mae >= 1.0:
                losses += 1
                total_r -= 1.0
            # else: trade still open at scan end, ignore

        n_resolved = wins + losses

        if n_resolved > 0:
            win_rate = wins / n_resolved * 100
            avg_r = total_r / n_resolved

            results.append({
                'rr': rr,
                'trades': n_resolved,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'avg_r': avg_r,
                'total_r': total_r
            })

    # Find optimal RR (highest avg R)
    if not results:
        return {
            'orb': orb,
            'symbol': symbol,
            'total_trades': len(trades),
            'optimal_rr': None,
            'optimal_win_rate': 0,
            'optimal_avg_r': 0,
            'improvement_vs_1r': 0
        }

    optimal = max(results, key=lambda x: x['avg_r'])
    baseline_1r = next((r for r in results if r['rr'] == 1.0), None)

    improvement = 0
    if baseline_1r and baseline_1r['avg_r'] != 0:
        improvement = ((optimal['avg_r'] - baseline_1r['avg_r']) / abs(baseline_1r['avg_r'])) * 100

    return {
        'orb': orb,
        'symbol': symbol,
        'total_trades': len(trades),
        'optimal_rr': optimal['rr'],
        'optimal_win_rate': optimal['win_rate'],
        'optimal_avg_r': optimal['avg_r'],
        'optimal_total_r': optimal['total_r'],
        'baseline_1r_avg_r': baseline_1r['avg_r'] if baseline_1r else 0,
        'improvement_vs_1r': improvement,
        'all_results': results
    }


def print_results(symbol: str, optimization_results: List[Dict]):
    """Print formatted optimization results"""

    print("=" * 100)
    print(f"RR OPTIMIZATION - {symbol}")
    print("=" * 100)
    print()

    print(f"{'ORB':<6} {'Trades':<8} {'Optimal RR':<12} {'Win Rate':<10} {'Avg R':<10} {'Total R':<10} {'vs 1.0R':<12}")
    print("-" * 100)

    for result in optimization_results:
        orb = result['orb']
        trades = result['total_trades']
        opt_rr = result['optimal_rr']
        opt_wr = result['optimal_win_rate']
        opt_avg_r = result['optimal_avg_r']
        opt_total_r = result['optimal_total_r']
        improvement = result['improvement_vs_1r']

        if opt_rr is None:
            print(f"{orb:<6} {trades:<8} {'N/A':<12} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'N/A':<12}")
        else:
            improvement_str = f"{improvement:+.1f}%" if improvement != 0 else "baseline"
            print(f"{orb:<6} {trades:<8} {opt_rr:<12.2f} {opt_wr:<10.1f}% {opt_avg_r:<+10.3f} {opt_total_r:<+10.1f} {improvement_str:<12}")

    print()

    # Summary by improvement
    significant = [r for r in optimization_results if r['optimal_rr'] and r['improvement_vs_1r'] > 10]
    moderate = [r for r in optimization_results if r['optimal_rr'] and 5 < r['improvement_vs_1r'] <= 10]
    minimal = [r for r in optimization_results if r['optimal_rr'] and r['improvement_vs_1r'] <= 5]

    print("IMPROVEMENT SUMMARY:")
    print(f"  Significant (>10%): {len(significant)} ORBs")
    if significant:
        for r in significant:
            print(f"    {r['orb']}: RR {r['optimal_rr']:.2f} (+{r['improvement_vs_1r']:.1f}%)")

    print(f"  Moderate (5-10%): {len(moderate)} ORBs")
    if moderate:
        for r in moderate:
            print(f"    {r['orb']}: RR {r['optimal_rr']:.2f} (+{r['improvement_vs_1r']:.1f}%)")

    print(f"  Minimal (<5%): {len(minimal)} ORBs - likely optimal at RR 1.0")
    print()

    # Detailed results for each ORB
    print("=" * 100)
    print("DETAILED RR TESTING RESULTS")
    print("=" * 100)
    print()

    for result in optimization_results:
        if not result.get('all_results'):
            continue

        print(f"{result['orb']} ORB:")
        print("-" * 100)
        print(f"{'RR':<8} {'Trades':<10} {'Wins':<10} {'Losses':<10} {'Win Rate':<12} {'Avg R':<12} {'Total R':<12}")
        print("-" * 100)

        for r in result['all_results']:
            marker = " <-- OPTIMAL" if r['rr'] == result['optimal_rr'] else ""
            print(f"{r['rr']:<8.2f} {r['trades']:<10} {r['wins']:<10} {r['losses']:<10} "
                  f"{r['win_rate']:<12.1f}% {r['avg_r']:<+12.3f} {r['total_r']:<+12.1f}{marker}")

        print()


def main():
    """Run RR optimization"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    symbol = sys.argv[1].upper()
    if symbol not in ['MGC', 'NQ', 'MPL']:
        print(f"Error: Symbol must be MGC, NQ, or MPL, got: {symbol}")
        sys.exit(1)

    # Optional: specific ORB
    specific_orb = None
    if len(sys.argv) >= 3 and sys.argv[2] in ORBS:
        specific_orb = sys.argv[2]

    # Optional: SL mode
    sl_mode = "full"
    if '--sl-mode' in sys.argv:
        idx = sys.argv.index('--sl-mode')
        if idx + 1 < len(sys.argv):
            sl_mode = sys.argv[idx + 1].lower()

    # Determine which ORBs to test
    orbs_to_test = [specific_orb] if specific_orb else ORBS

    # Connect to database
    con = duckdb.connect(DB_PATH, read_only=True)

    try:
        # Optimize each ORB
        results = []
        for orb in orbs_to_test:
            print(f"Optimizing {orb} ORB for {symbol}...")
            result = optimize_orb_rr(con, symbol, orb, sl_mode)
            results.append(result)

        # Print results
        print()
        print_results(symbol, results)

        # Save to CSV
        import csv
        output_file = f"outputs/{symbol}_rr_optimization.csv"
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['orb', 'symbol', 'total_trades', 'optimal_rr', 'optimal_win_rate',
                         'optimal_avg_r', 'optimal_total_r', 'baseline_1r_avg_r', 'improvement_vs_1r']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: v for k, v in r.items() if k in fieldnames})

        print(f"Results saved to: {output_file}")
        print()

    finally:
        con.close()


if __name__ == "__main__":
    main()
