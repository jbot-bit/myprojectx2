"""
Trading Journal
===============
Track and analyze your discretionary MGC ORB trades.

Features:
- Log trades with full context (ORB time, direction, session types)
- Calculate P&L and R-multiples
- Compare your performance vs historical backtests
- Track win rate, avg R, max drawdown
- Export to CSV for deeper analysis

Usage:
  python journal.py add                     # Add new trade (interactive)
  python journal.py list                    # List all trades
  python journal.py list --last 30          # Last 30 days
  python journal.py stats                   # Performance statistics
  python journal.py compare                 # Compare vs historical
  python journal.py export                  # Export to CSV

Journal stored in: trades.db (SQLite database)
"""

import duckdb
import sqlite3
import argparse
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
import json


@dataclass
class Trade:
    """Represents a single ORB trade"""
    id: Optional[int]
    trade_date: date
    orb_time: str  # 0900, 1000, 1100, 1800, 2300, 0030
    direction: str  # UP, DOWN
    entry_price: float
    stop_price: float
    exit_price: Optional[float]
    orb_size: float
    outcome: Optional[str]  # WIN, LOSS, SCRATCH, OPEN
    r_multiple: Optional[float]
    pnl_usd: Optional[float]
    contracts: int
    notes: str
    asia_type: Optional[str]
    london_type: Optional[str]
    ny_type: Optional[str]
    created_at: datetime


class TradingJournal:
    """Manage trading journal database"""

    def __init__(self, db_path: str = "trades.db", mgc_db_path: str = "gold.db"):
        self.db_path = db_path
        self.mgc_db_path = mgc_db_path
        self._init_database()

    def _init_database(self):
        """Initialize journal database schema"""
        con = sqlite3.connect(self.db_path)
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date DATE NOT NULL,
                orb_time TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                exit_price REAL,
                orb_size REAL NOT NULL,
                outcome TEXT,
                r_multiple REAL,
                pnl_usd REAL,
                contracts INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
                asia_type TEXT,
                london_type TEXT,
                ny_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()
        con.close()

    def get_session_context(self, trade_date: date) -> Dict:
        """Get session types from MGC database for context"""
        con = duckdb.connect(self.mgc_db_path, read_only=True)
        try:
            result = con.execute("""
                SELECT asia_type, london_type, ny_type
                FROM daily_features_v2
                WHERE date_local = ?
            """, [trade_date]).fetchone()

            if result:
                return {
                    "asia_type": result[0],
                    "london_type": result[1],
                    "ny_type": result[2],
                }
            return {}
        finally:
            con.close()

    def add_trade_interactive(self):
        """Add trade through interactive prompts"""
        print("\n" + "="*80)
        print("ADD NEW TRADE")
        print("="*80)

        # Trade date
        date_input = input("\nTrade date (YYYY-MM-DD) [today]: ").strip()
        trade_date = date.fromisoformat(date_input) if date_input else date.today()

        # Get session context
        context = self.get_session_context(trade_date)
        if context:
            print(f"\nSession context for {trade_date}:")
            print(f"  Asia: {context.get('asia_type', 'N/A')}")
            print(f"  London: {context.get('london_type', 'N/A')}")
            print(f"  NY: {context.get('ny_type', 'N/A')}")

        # ORB time
        print("\nORB time:")
        print("  1) 09:00   2) 10:00   3) 11:00")
        print("  4) 18:00   5) 23:00   6) 00:30")
        orb_choice = input("Choice (1-6): ").strip()
        orb_map = {"1": "0900", "2": "1000", "3": "1100", "4": "1800", "5": "2300", "6": "0030"}
        orb_time = orb_map.get(orb_choice)

        if not orb_time:
            print("Invalid choice")
            return

        # Direction
        direction = input("\nDirection (UP/DOWN): ").strip().upper()
        if direction not in ["UP", "DOWN"]:
            print("Invalid direction")
            return

        # Entry price
        entry_price = float(input("\nEntry price: ").strip())

        # Stop price
        stop_price = float(input("Stop price: ").strip())

        # Calculate ORB size
        orb_size = abs(entry_price - stop_price)

        # Contracts
        contracts_input = input("Number of contracts [1]: ").strip()
        contracts = int(contracts_input) if contracts_input else 1

        # Exit price (optional if still open)
        exit_input = input("\nExit price (leave blank if still open): ").strip()
        exit_price = float(exit_input) if exit_input else None

        # Calculate outcome and R
        outcome = None
        r_multiple = None
        pnl_usd = None

        if exit_price:
            # Determine outcome
            if direction == "UP":
                pnl_points = exit_price - entry_price
            else:  # DOWN
                pnl_points = entry_price - exit_price

            # R-multiple
            r_multiple = pnl_points / orb_size if orb_size > 0 else 0

            # Outcome
            if r_multiple > 0.1:
                outcome = "WIN"
            elif r_multiple < -0.1:
                outcome = "LOSS"
            else:
                outcome = "SCRATCH"

            # P&L in USD (MGC: $10 per $1 move)
            pnl_usd = pnl_points * 10 * contracts

            print(f"\nCalculated:")
            print(f"  Outcome: {outcome}")
            print(f"  R-multiple: {r_multiple:+.2f}")
            print(f"  P&L: ${pnl_usd:,.2f}")
        else:
            outcome = "OPEN"
            print(f"\nTrade marked as OPEN")

        # Notes
        notes = input("\nNotes (optional): ").strip()

        # Confirm
        print("\n" + "="*80)
        print("CONFIRM TRADE")
        print("="*80)
        print(f"Date: {trade_date}")
        print(f"ORB: {orb_time} {direction}")
        print(f"Entry: {entry_price:.2f} | Stop: {stop_price:.2f} | Exit: {exit_price if exit_price else 'OPEN'}")
        print(f"Contracts: {contracts} | ORB Size: {orb_size:.2f}")
        if outcome:
            print(f"Outcome: {outcome} | R: {r_multiple:+.2f} | P&L: ${pnl_usd:,.2f}")

        confirm = input("\nSave this trade? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Trade not saved")
            return

        # Save to database
        con = sqlite3.connect(self.db_path)
        con.execute("""
            INSERT INTO trades (
                trade_date, orb_time, direction, entry_price, stop_price,
                exit_price, orb_size, outcome, r_multiple, pnl_usd,
                contracts, notes, asia_type, london_type, ny_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_date.isoformat(), orb_time, direction, entry_price, stop_price,
            exit_price, orb_size, outcome, r_multiple, pnl_usd,
            contracts, notes,
            context.get('asia_type'), context.get('london_type'), context.get('ny_type')
        ))
        con.commit()
        trade_id = con.lastrowid
        con.close()

        print(f"\nTrade #{trade_id} saved successfully!")

    def list_trades(self, last_days: Optional[int] = None, limit: int = 50):
        """List trades"""
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row

        where_clause = ""
        params = []

        if last_days:
            cutoff = date.today() - timedelta(days=last_days)
            where_clause = "WHERE trade_date >= ?"
            params.append(cutoff.isoformat())

        query = f"""
            SELECT *
            FROM trades
            {where_clause}
            ORDER BY trade_date DESC, created_at DESC
            LIMIT ?
        """
        params.append(limit)

        rows = con.execute(query, params).fetchall()
        con.close()

        if not rows:
            print("\nNo trades found")
            return

        print("\n" + "="*120)
        print(f"TRADING JOURNAL ({len(rows)} trades)")
        print("="*120)

        for row in rows:
            trade_id = row['id']
            trade_date = row['trade_date']
            orb_time = row['orb_time']
            direction = row['direction']
            entry = row['entry_price']
            stop = row['stop_price']
            exit_price = row['exit_price']
            outcome = row['outcome'] or 'OPEN'
            r = row['r_multiple']
            pnl = row['pnl_usd']
            contracts = row['contracts']
            notes = row['notes']

            print(f"\n#{trade_id:03d} | {trade_date} | {orb_time} {direction}")
            print(f"      Entry: {entry:.2f} | Stop: {stop:.2f} | Exit: {exit_price if exit_price else 'OPEN':.2f if exit_price else 'OPEN'}")

            if r is not None and pnl is not None:
                print(f"      {outcome} | R: {r:+.2f} | P&L: ${pnl:,.2f} | Contracts: {contracts}")
            else:
                print(f"      OPEN | Contracts: {contracts}")

            if notes:
                print(f"      Notes: {notes}")

        print("\n" + "="*120)

    def get_stats(self) -> Dict:
        """Calculate performance statistics"""
        con = sqlite3.connect(self.db_path)

        # Overall stats
        stats = con.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome = 'SCRATCH' THEN 1 ELSE 0 END) as scratches,
                SUM(CASE WHEN outcome = 'OPEN' THEN 1 ELSE 0 END) as open_trades,
                AVG(r_multiple) as avg_r,
                SUM(pnl_usd) as total_pnl,
                MAX(pnl_usd) as best_trade,
                MIN(pnl_usd) as worst_trade,
                AVG(pnl_usd) as avg_pnl
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS', 'SCRATCH')
        """).fetchone()

        total = stats[0] or 0
        wins = stats[1] or 0
        losses = stats[2] or 0
        scratches = stats[3] or 0
        open_trades = stats[4] or 0
        avg_r = stats[5] or 0
        total_pnl = stats[6] or 0
        best_trade = stats[7] or 0
        worst_trade = stats[8] or 0
        avg_pnl = stats[9] or 0

        win_rate = wins / total if total > 0 else 0

        # Drawdown calculation
        trades_ordered = con.execute("""
            SELECT pnl_usd
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS', 'SCRATCH')
            ORDER BY trade_date, created_at
        """).fetchall()

        cumulative_pnl = 0
        peak_pnl = 0
        max_drawdown = 0

        for (pnl,) in trades_ordered:
            if pnl:
                cumulative_pnl += pnl
                if cumulative_pnl > peak_pnl:
                    peak_pnl = cumulative_pnl
                drawdown = peak_pnl - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        con.close()

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "scratches": scratches,
            "open_trades": open_trades,
            "win_rate": win_rate,
            "avg_r": avg_r,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "max_drawdown": max_drawdown,
        }

    def print_stats(self):
        """Print performance statistics"""
        stats = self.get_stats()

        print("\n" + "="*80)
        print("TRADING PERFORMANCE")
        print("="*80)

        print(f"\nTrade Summary:")
        print(f"  Total Trades: {stats['total_trades']}")
        print(f"  Wins: {stats['wins']} | Losses: {stats['losses']} | Scratches: {stats['scratches']}")
        print(f"  Open: {stats['open_trades']}")
        print(f"  Win Rate: {stats['win_rate']:.1%}")

        print(f"\nR-Multiple:")
        print(f"  Average R: {stats['avg_r']:+.2f}")

        print(f"\nP&L:")
        print(f"  Total P&L: ${stats['total_pnl']:,.2f}")
        print(f"  Avg P&L per trade: ${stats['avg_pnl']:,.2f}")
        print(f"  Best trade: ${stats['best_trade']:,.2f}")
        print(f"  Worst trade: ${stats['worst_trade']:,.2f}")
        print(f"  Max Drawdown: ${stats['max_drawdown']:,.2f}")

        # Per-setup stats
        con = sqlite3.connect(self.db_path)
        setup_stats = con.execute("""
            SELECT
                orb_time || ' ' || direction as setup,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(r_multiple) as avg_r,
                SUM(pnl_usd) as total_pnl
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS', 'SCRATCH')
            GROUP BY orb_time, direction
            HAVING COUNT(*) >= 1
            ORDER BY avg_r DESC
        """).fetchall()

        if setup_stats:
            print("\n" + "="*80)
            print("PERFORMANCE BY SETUP")
            print("="*80)
            print(f"\n{'Setup':<15} {'Trades':>8} {'Wins':>6} {'WR':>8} {'Avg R':>10} {'Total P&L':>15}")
            print("-"*80)

            for setup, trades, wins, avg_r, total_pnl in setup_stats:
                wr = wins / trades if trades > 0 else 0
                print(f"{setup:<15} {trades:>8} {wins:>6} {wr:>7.1%} {avg_r:>+9.2f} ${total_pnl:>13,.2f}")

        con.close()

        print("\n" + "="*80)

    def compare_to_historical(self):
        """Compare journal performance to historical backtests"""
        stats = self.get_stats()

        if stats['total_trades'] == 0:
            print("\nNo completed trades in journal to compare")
            return

        print("\n" + "="*80)
        print("COMPARISON: Your Trades vs Historical Performance")
        print("="*80)

        con_journal = sqlite3.connect(self.db_path)
        con_mgc = duckdb.connect(self.mgc_db_path, read_only=True)

        # Get journal stats by setup
        journal_setups = con_journal.execute("""
            SELECT
                orb_time,
                direction,
                COUNT(*) as trades,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(r_multiple) as avg_r
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS')
            GROUP BY orb_time, direction
            HAVING COUNT(*) >= 3
        """).fetchall()

        if not journal_setups:
            print("\nNeed at least 3 completed trades per setup for comparison")
            con_journal.close()
            con_mgc.close()
            return

        print(f"\n{'Setup':<15} | {'Your WR':>10} {'Hist WR':>10} {'Diff':>8} | {'Your R':>10} {'Hist R':>10} {'Diff':>8} | {'Trades':>8}")
        print("-"*100)

        for orb_time, direction, trades, wins, avg_r in journal_setups:
            journal_wr = wins / trades if trades > 0 else 0

            # Get historical stats for same setup
            hist = con_mgc.execute(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    AVG(orb_{orb_time}_r_multiple) as avg_r
                FROM daily_features_v2
                WHERE orb_{orb_time}_break_dir = ?
                  AND orb_{orb_time}_outcome IN ('WIN', 'LOSS')
            """, [direction]).fetchone()

            hist_total, hist_wins, hist_avg_r = hist
            hist_wr = hist_wins / hist_total if hist_total > 0 else 0

            wr_diff = journal_wr - hist_wr
            r_diff = avg_r - hist_avg_r if avg_r and hist_avg_r else 0

            setup_name = f"{orb_time} {direction}"
            print(f"{setup_name:<15} | {journal_wr:>9.1%} {hist_wr:>9.1%} {wr_diff:>+7.1%} | "
                  f"{avg_r:>+9.2f} {hist_avg_r:>+9.2f} {r_diff:>+7.2f} | {trades:>8}")

        con_journal.close()
        con_mgc.close()

        print("\n" + "="*80)
        print("Interpretation:")
        print("  Positive Diff = You're outperforming historical average")
        print("  Negative Diff = You're underperforming historical average")
        print("="*80 + "\n")

    def export_to_csv(self, filename: str = "journal_export.csv"):
        """Export all trades to CSV"""
        con = sqlite3.connect(self.db_path)

        query = """
            SELECT
                id,
                trade_date,
                orb_time,
                direction,
                entry_price,
                stop_price,
                exit_price,
                orb_size,
                outcome,
                r_multiple,
                pnl_usd,
                contracts,
                notes,
                asia_type,
                london_type,
                ny_type,
                created_at
            FROM trades
            ORDER BY trade_date, created_at
        """

        import csv
        rows = con.execute(query).fetchall()
        con.close()

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Date', 'ORB Time', 'Direction', 'Entry', 'Stop', 'Exit',
                'ORB Size', 'Outcome', 'R Multiple', 'P&L USD', 'Contracts',
                'Notes', 'Asia Type', 'London Type', 'NY Type', 'Created At'
            ])
            writer.writerows(rows)

        print(f"\nExported {len(rows)} trades to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="MGC Trading Journal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add trade
    subparsers.add_parser('add', help='Add new trade (interactive)')

    # List trades
    list_parser = subparsers.add_parser('list', help='List trades')
    list_parser.add_argument('--last', type=int, metavar='N', help='Show last N days only')
    list_parser.add_argument('--limit', type=int, default=50, help='Max trades to show')

    # Stats
    subparsers.add_parser('stats', help='Show performance statistics')

    # Compare
    subparsers.add_parser('compare', help='Compare vs historical performance')

    # Export
    export_parser = subparsers.add_parser('export', help='Export to CSV')
    export_parser.add_argument('-o', '--output', default='journal_export.csv', help='Output filename')

    args = parser.parse_args()

    journal = TradingJournal()

    if args.command == 'add':
        journal.add_trade_interactive()
    elif args.command == 'list':
        journal.list_trades(last_days=args.last, limit=args.limit)
    elif args.command == 'stats':
        journal.print_stats()
    elif args.command == 'compare':
        journal.compare_to_historical()
    elif args.command == 'export':
        journal.export_to_csv(args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
