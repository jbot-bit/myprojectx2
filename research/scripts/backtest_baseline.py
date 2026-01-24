"""
Baseline ORB Backtest - Works for Both MGC and NQ
==================================================

Simple, honest backtest that:
- Tests all 6 ORBs (0900, 1000, 1100, 1800, 2300, 0030)
- Uses daily_features_v2 table (MGC) or daily_features_v2_nq (NQ)
- Reports: trades, win rate, avg R, total R
- NO filters, NO optimizations - pure baseline

This is the HONEST way to compare MGC vs NQ performance.

Usage:
  python scripts/backtest_baseline.py MGC
  python scripts/backtest_baseline.py NQ
  python scripts/backtest_baseline.py MGC --start-date 2024-01-01 --end-date 2025-12-31
"""

import sys
import duckdb
from datetime import date
from typing import Dict, List, Optional

DB_PATH = "gold.db"

# ORB times to test
ORBS = ['0900', '1000', '1100', '1800', '2300', '0030']


def get_table_name(symbol: str) -> str:
    """Get feature table name for symbol"""
    if symbol == "MGC":
        return "daily_features_v2"
    elif symbol == "NQ":
        return "daily_features_v2_nq"
    else:
        raise ValueError(f"Unknown symbol: {symbol}")


def backtest_orb(
    con: duckdb.DuckDBPyConnection,
    symbol: str,
    orb: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict:
    """
    Backtest a single ORB

    Args:
        con: Database connection
        symbol: 'MGC' or 'NQ'
        orb: ORB time ('0900', '1000', etc.)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        Dict with results: trades, wins, losses, win_rate, avg_r, total_r
    """
    table = get_table_name(symbol)

    # Build query
    where_clauses = [
        f"orb_{orb}_outcome IN ('WIN', 'LOSS')",
        f"orb_{orb}_break_dir IN ('UP', 'DOWN')"
    ]

    if start_date:
        where_clauses.append(f"date_local >= '{start_date}'")
    if end_date:
        where_clauses.append(f"date_local <= '{end_date}'")

    where_clause = " AND ".join(where_clauses)

    query = f"""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN orb_{orb}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN orb_{orb}_outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
            AVG(orb_{orb}_r_multiple) as avg_r,
            SUM(orb_{orb}_r_multiple) as total_r,
            MIN(date_local) as first_trade,
            MAX(date_local) as last_trade
        FROM {table}
        WHERE {where_clause}
    """

    result = con.execute(query).fetchone()

    if not result or result[0] == 0:
        return {
            'orb': orb,
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'first_trade': None,
            'last_trade': None
        }

    trades = result[0]
    wins = result[1]
    losses = result[2]
    avg_r = result[3]
    total_r = result[4]
    first_trade = result[5]
    last_trade = result[6]

    return {
        'orb': orb,
        'trades': trades,
        'wins': wins,
        'losses': losses,
        'win_rate': (wins / trades * 100) if trades > 0 else 0.0,
        'avg_r': avg_r,
        'total_r': total_r,
        'first_trade': first_trade,
        'last_trade': last_trade
    }


def print_results(symbol: str, results: List[Dict], start_date: Optional[str], end_date: Optional[str]):
    """Print formatted backtest results"""

    print("=" * 90)
    print(f"BASELINE ORB BACKTEST - {symbol}")
    print("=" * 90)
    print()

    # Date range
    if results and results[0]['first_trade']:
        first = min(r['first_trade'] for r in results if r['first_trade'])
        last = max(r['last_trade'] for r in results if r['last_trade'])
        print(f"Date Range: {first} to {last}")
        if start_date or end_date:
            print(f"  (filtered: start={start_date or 'none'}, end={end_date or 'none'})")
    print()

    # Table header
    print(f"{'ORB':<6} {'Trades':>7} {'Wins':>6} {'Losses':>7} {'Win%':>7} {'Avg R':>9} {'Total R':>10} {'Rank':<6}")
    print("-" * 90)

    # Sort by avg_r descending
    sorted_results = sorted(results, key=lambda x: x['avg_r'], reverse=True)

    for i, r in enumerate(sorted_results):
        rank = f"#{i+1}"
        if i == 0:
            rank = "1st"
        elif i == 1:
            rank = "2nd"
        elif i == 2:
            rank = "3rd"
        else:
            rank = f"{i+1}th"

        print(f"{r['orb']:<6} {r['trades']:>7} {r['wins']:>6} {r['losses']:>7} "
              f"{r['win_rate']:>6.1f}% {r['avg_r']:>+9.3f} {r['total_r']:>+10.1f} {rank:<6}")

    # Summary
    total_trades = sum(r['trades'] for r in results)
    total_r = sum(r['total_r'] for r in results)
    avg_r_all = sum(r['avg_r'] for r in results) / len(results) if results else 0

    print("-" * 90)
    print(f"{'TOTAL':<6} {total_trades:>7} {'':>6} {'':>7} {'':>7} {avg_r_all:>+9.3f} {total_r:>+10.1f}")
    print()

    # Winners vs losers
    profitable = [r for r in results if r['avg_r'] > 0]
    unprofitable = [r for r in results if r['avg_r'] <= 0]

    print(f"Profitable ORBs: {len(profitable)}/6")
    print(f"Best ORB: {sorted_results[0]['orb']} ({sorted_results[0]['avg_r']:+.3f}R avg, {sorted_results[0]['win_rate']:.1f}% WR)")
    print(f"Worst ORB: {sorted_results[-1]['orb']} ({sorted_results[-1]['avg_r']:+.3f}R avg, {sorted_results[-1]['win_rate']:.1f}% WR)")
    print()


def main():
    """Run baseline backtest"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    symbol = sys.argv[1].upper()
    if symbol not in ['MGC', 'NQ']:
        print(f"Error: Symbol must be MGC or NQ, got: {symbol}")
        sys.exit(1)

    # Parse optional date filters
    start_date = None
    end_date = None

    if '--start-date' in sys.argv:
        idx = sys.argv.index('--start-date')
        if idx + 1 < len(sys.argv):
            start_date = sys.argv[idx + 1]

    if '--end-date' in sys.argv:
        idx = sys.argv.index('--end-date')
        if idx + 1 < len(sys.argv):
            end_date = sys.argv[idx + 1]

    # Connect to database
    con = duckdb.connect(DB_PATH, read_only=True)

    try:
        # Test each ORB
        results = []
        for orb in ORBS:
            result = backtest_orb(con, symbol, orb, start_date, end_date)
            results.append(result)

        # Print results
        print_results(symbol, results, start_date, end_date)

        # Save to CSV
        output_file = f"outputs/{symbol}_baseline_backtest.csv"
        import csv
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['orb', 'trades', 'wins', 'losses', 'win_rate', 'avg_r', 'total_r'], extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)

        print(f"Results saved to: {output_file}")
        print()

    finally:
        con.close()


if __name__ == "__main__":
    main()
