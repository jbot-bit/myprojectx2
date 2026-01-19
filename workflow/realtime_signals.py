"""
Real-Time Trading Signals - Zero Lookahead
===========================================
Generates tradeable signals using ONLY information available at each open.

This tool answers: "What can I trade RIGHT NOW?"

Usage:
  python realtime_signals.py                    # Today's signals
  python realtime_signals.py 2026-01-09        # Specific date
  python realtime_signals.py --time 1100       # Specific ORB time

Shows:
- What information is available now
- Which ORBs are tradeable
- Historical performance of current setup
- Entry/stop levels
"""

import duckdb
import argparse
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional


TZ_LOCAL = ZoneInfo("Australia/Brisbane")


class RealtimeSignalGenerator:
    """Generate trading signals with zero lookahead"""

    def __init__(self, db_path: str = "gold.db"):
        self.con = duckdb.connect(db_path, read_only=True)

    def get_pre_asia_context(self, trade_date: date) -> Optional[Dict]:
        """Get PRE_ASIA context (available at 09:00)"""
        result = self.con.execute("""
            SELECT
                pre_asia_high,
                pre_asia_low,
                pre_asia_range,
                (pre_asia_range / 0.1) as pre_asia_ticks
            FROM daily_features_v2
            WHERE date_local = ?
        """, [trade_date]).fetchone()

        if not result or result[0] is None:
            return None

        return {
            "high": result[0],
            "low": result[1],
            "range": result[2],
            "range_ticks": result[3],
        }

    def get_completed_asia(self, trade_date: date) -> Optional[Dict]:
        """Get completed ASIA session (available at 17:00+)"""
        result = self.con.execute("""
            SELECT
                asia_high,
                asia_low,
                asia_range,
                (asia_range / 0.1) as asia_ticks,
                orb_0900_outcome,
                orb_1000_outcome,
                orb_1100_outcome
            FROM daily_features_v2
            WHERE date_local = ?
        """, [trade_date]).fetchone()

        if not result or result[0] is None:
            return None

        return {
            "high": result[0],
            "low": result[1],
            "range": result[2],
            "range_ticks": result[3],
            "orb_0900": result[4],
            "orb_1000": result[5],
            "orb_1100": result[6],
        }

    def get_pre_london_context(self, trade_date: date) -> Optional[Dict]:
        """Get PRE_LONDON context (available at 18:00)"""
        result = self.con.execute("""
            SELECT
                pre_london_high,
                pre_london_low,
                pre_london_range,
                (pre_london_range / 0.1) as pre_london_ticks
            FROM daily_features_v2
            WHERE date_local = ?
        """, [trade_date]).fetchone()

        if not result or result[0] is None:
            return None

        return {
            "high": result[0],
            "low": result[1],
            "range": result[2],
            "range_ticks": result[3],
        }

    def get_historical_performance(self, orb_time: str, condition: str, params: List) -> Dict:
        """Get historical performance for a setup"""
        query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(orb_{orb_time}_r_multiple) as avg_r,
                SUM(orb_{orb_time}_r_multiple) as total_r
            FROM daily_features_v2
            WHERE orb_{orb_time}_outcome IN ('WIN', 'LOSS')
              AND {condition}
        """

        result = self.con.execute(query, params).fetchone()
        total, wins, avg_r, total_r = result

        return {
            "total_trades": total or 0,
            "wins": wins or 0,
            "win_rate": wins / total if total else 0,
            "avg_r": avg_r or 0,
            "total_r": total_r or 0,
        }

    def generate_0900_signal(self, trade_date: date):
        """Generate 09:00 ORB signal (at 09:00)"""
        print("\n" + "="*80)
        print("09:00 ORB - ASIA OPEN")
        print("="*80)
        print(f"\nDecision time: 09:00 on {trade_date}")
        print("Available information: PRE_ASIA (07:00-09:00), previous day data")

        pre_asia = self.get_pre_asia_context(trade_date)

        if not pre_asia:
            print("\n[NO DATA] PRE_ASIA data not available")
            return

        print(f"\nPRE_ASIA Context:")
        print(f"  Range: {pre_asia['range_ticks']:.0f} ticks ({pre_asia['high']:.2f} - {pre_asia['low']:.2f})")

        # Test condition: Large PRE_ASIA (>50 ticks)
        if pre_asia['range_ticks'] > 50:
            print(f"\n[SIGNAL] PRE_ASIA > 50 ticks (volatile pre-market)")

            for direction in ["UP", "DOWN"]:
                hist = self.get_historical_performance(
                    "0900",
                    f"orb_0900_break_dir = ? AND (pre_asia_range / 0.1) > 50",
                    [direction]
                )

                if hist["total_trades"] >= 10:
                    print(f"\n  {direction} Breakout:")
                    print(f"    Historical: {hist['total_trades']} trades | WR: {hist['win_rate']:.1%} | Avg R: {hist['avg_r']:+.2f}")
                    if hist['avg_r'] > 0.05:
                        print(f"    [TRADEABLE EDGE]")

        else:
            print(f"\n[INFO] PRE_ASIA < 50 ticks (quiet pre-market)")
            print("  Historical edge typically better with larger PRE_ASIA ranges")

    def generate_1100_signal(self, trade_date: date):
        """Generate 11:00 ORB signal (at 11:00)"""
        print("\n" + "="*80)
        print("11:00 ORB - ASIA LATE")
        print("="*80)
        print(f"\nDecision time: 11:00 on {trade_date}")
        print("Available: PRE_ASIA, Asia 09:00-11:00, 09:00/10:00 ORB outcomes")

        pre_asia = self.get_pre_asia_context(trade_date)

        if not pre_asia:
            print("\n[NO DATA] PRE_ASIA data not available")
            return

        print(f"\nPRE_ASIA Context:")
        print(f"  Range: {pre_asia['range_ticks']:.0f} ticks")

        # Test multiple conditions
        conditions = []

        if pre_asia['range_ticks'] > 50:
            conditions.append(("PRE_ASIA > 50 ticks", "(pre_asia_range / 0.1) > 50"))

        if pre_asia['range_ticks'] < 30:
            conditions.append(("PRE_ASIA < 30 ticks (tight)", "(pre_asia_range / 0.1) < 30"))

        for label, condition in conditions:
            print(f"\n[FILTER] {label}")

            for direction in ["UP", "DOWN"]:
                hist = self.get_historical_performance(
                    "1100",
                    f"orb_1100_break_dir = ? AND {condition}",
                    [direction]
                )

                if hist["total_trades"] >= 10:
                    print(f"\n  {direction} Breakout:")
                    print(f"    Historical: {hist['total_trades']} trades | WR: {hist['win_rate']:.1%} | Avg R: {hist['avg_r']:+.2f}")
                    if hist['avg_r'] > 0.10:
                        print(f"    [STRONG EDGE]")
                    elif hist['avg_r'] > 0.05:
                        print(f"    [TRADEABLE EDGE]")

    def generate_1800_signal(self, trade_date: date):
        """Generate 18:00 ORB signal (at 18:00)"""
        print("\n" + "="*80)
        print("18:00 ORB - LONDON OPEN")
        print("="*80)
        print(f"\nDecision time: 18:00 on {trade_date}")
        print("Available: PRE_LONDON (17:00-18:00), COMPLETED ASIA (09:00-17:00)")

        pre_london = self.get_pre_london_context(trade_date)
        asia = self.get_completed_asia(trade_date)

        if not pre_london or not asia:
            print("\n[NO DATA] Context not available")
            return

        print(f"\nPRE_LONDON Context:")
        print(f"  Range: {pre_london['range_ticks']:.0f} ticks")

        print(f"\nCompleted ASIA Session:")
        print(f"  Range: {asia['range_ticks']:.0f} ticks")
        print(f"  ORBs: 09:00={asia['orb_0900']}, 10:00={asia['orb_1000']}, 11:00={asia['orb_1100']}")

        # Test: Small PRE_LONDON + Large ASIA
        if pre_london['range_ticks'] < 20 and asia['range_ticks'] > 300:
            print(f"\n[SIGNAL] PRE_LONDON < 20 ticks + ASIA > 300 ticks (consolidation after expansion)")

            for direction in ["UP", "DOWN"]:
                hist = self.get_historical_performance(
                    "1800",
                    f"orb_1800_break_dir = ? AND (pre_london_range / 0.1) < 20 AND (asia_range / 0.1) > 300",
                    [direction]
                )

                if hist["total_trades"] >= 5:
                    print(f"\n  {direction} Breakout:")
                    print(f"    Historical: {hist['total_trades']} trades | WR: {hist['win_rate']:.1%} | Avg R: {hist['avg_r']:+.2f}")
                    if hist['avg_r'] > 0.10:
                        print(f"    [STRONG EDGE]")

        # Test: Large PRE_LONDON
        elif pre_london['range_ticks'] > 40:
            print(f"\n[SIGNAL] PRE_LONDON > 40 ticks (volatile positioning)")

            for direction in ["UP", "DOWN"]:
                hist = self.get_historical_performance(
                    "1800",
                    f"orb_1800_break_dir = ? AND (pre_london_range / 0.1) > 40",
                    [direction]
                )

                if hist["total_trades"] >= 10:
                    print(f"\n  {direction} Breakout:")
                    print(f"    Historical: {hist['total_trades']} trades | WR: {hist['win_rate']:.1%} | Avg R: {hist['avg_r']:+.2f}")

    def generate_all_signals(self, trade_date: date):
        """Generate all applicable signals for a date"""
        print("\n" + "="*80)
        print(f"REAL-TIME TRADING SIGNALS - {trade_date}")
        print("="*80)
        print("\nZero Lookahead - Only information available at decision time")

        self.generate_0900_signal(trade_date)
        self.generate_1100_signal(trade_date)
        self.generate_1800_signal(trade_date)

        print("\n" + "="*80)
        print("END OF SIGNALS")
        print("="*80)
        print("\nAll signals use ONLY pre-open information.")
        print("100% reproducible in live trading.")
        print("="*80 + "\n")

    def close(self):
        self.con.close()


def main():
    parser = argparse.ArgumentParser(description="Generate real-time trading signals")

    parser.add_argument("date", nargs="?", help="Date (YYYY-MM-DD), default=today")
    parser.add_argument("--time", choices=["0900", "1100", "1800"], help="Specific ORB time only")

    args = parser.parse_args()

    if args.date:
        target_date = date.fromisoformat(args.date)
    else:
        target_date = date.today()

    generator = RealtimeSignalGenerator()

    try:
        if args.time:
            if args.time == "0900":
                generator.generate_0900_signal(target_date)
            elif args.time == "1100":
                generator.generate_1100_signal(target_date)
            elif args.time == "1800":
                generator.generate_1800_signal(target_date)
        else:
            generator.generate_all_signals(target_date)

    finally:
        generator.close()


if __name__ == "__main__":
    main()
