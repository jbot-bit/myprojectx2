"""
Daily Update Script
===================
Automatically fetches the latest MGC data and updates features.

This script:
1. Checks the last date in the database
2. Fetches data from that date to today
3. Rebuilds 5-minute bars
4. Updates daily features
5. Runs daily alerts for today

Usage:
  python daily_update.py              # Update to today
  python daily_update.py --dry-run    # Show what would be updated without doing it
  python daily_update.py --days 7     # Fetch last 7 days (useful for catching up)

Recommended: Run this every morning before the Asia session (08:00-08:30 local)
"""

import duckdb
import subprocess
import sys
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
import argparse


class DailyUpdater:
    """Manage incremental daily data updates"""

    def __init__(self, db_path: str = "gold.db", dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run

    def get_last_date(self) -> Optional[date]:
        """Get the last date with data in bars_1m"""
        con = duckdb.connect(self.db_path, read_only=True)
        try:
            result = con.execute("""
                SELECT MAX(ts_utc AT TIME ZONE 'Australia/Brisbane')::DATE
                FROM bars_1m
                WHERE symbol = 'MGC'
            """).fetchone()

            if result and result[0]:
                return result[0]
            return None
        finally:
            con.close()

    def get_date_range_to_update(self, days_back: Optional[int] = None) -> Tuple[date, date]:
        """
        Determine the date range to update.

        Args:
            days_back: If specified, go back this many days from today instead of from last_date

        Returns:
            (start_date, end_date) tuple
        """
        last_date = self.get_last_date()
        today = date.today()

        if days_back:
            # Override: fetch last N days regardless of what's in database
            start_date = today - timedelta(days=days_back)
            end_date = today
        elif last_date:
            # Normal incremental update from last date
            # Go back 2 days to ensure we catch any late data
            start_date = last_date - timedelta(days=2)
            end_date = today
        else:
            # No data in database - prompt user to run full backfill
            print("\nERROR: No data found in database!")
            print("Please run a full backfill first:")
            print(f"  python backfill_databento_continuous.py 2024-01-01 {today.strftime('%Y-%m-%d')}")
            sys.exit(1)

        return start_date, end_date

    def run_backfill(self, start_date: date, end_date: date) -> bool:
        """Run the Databento backfill script"""
        cmd = [
            "python",
            "backfill_databento_continuous.py",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        ]

        print(f"\nRunning: {' '.join(cmd)}")

        if self.dry_run:
            print("[DRY RUN] Would execute backfill but skipping")
            return True

        try:
            result = subprocess.run(cmd, check=True, capture_output=False)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: Backfill failed with exit code {e.returncode}")
            return False

    def run_daily_alerts(self, target_date: date) -> bool:
        """Run daily alerts for target date"""
        cmd = [
            "python",
            "daily_alerts.py",
            target_date.strftime("%Y-%m-%d"),
        ]

        print(f"\nRunning: {' '.join(cmd)}")

        if self.dry_run:
            print("[DRY RUN] Would execute alerts but skipping")
            return True

        try:
            result = subprocess.run(cmd, check=True, capture_output=False)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            print(f"\nWARNING: Daily alerts failed with exit code {e.returncode}")
            return False

    def get_row_counts(self) -> dict:
        """Get current row counts from database"""
        con = duckdb.connect(self.db_path, read_only=True)
        try:
            bars_1m = con.execute("SELECT COUNT(*) FROM bars_1m").fetchone()[0]
            bars_5m = con.execute("SELECT COUNT(*) FROM bars_5m").fetchone()[0]
            daily_features = con.execute("SELECT COUNT(*) FROM daily_features").fetchone()[0]
            daily_features_v2 = con.execute("SELECT COUNT(*) FROM daily_features_v2").fetchone()[0]

            last_1m = con.execute("""
                SELECT MAX(ts_utc AT TIME ZONE 'Australia/Brisbane')::DATE
                FROM bars_1m
            """).fetchone()[0]

            last_feature = con.execute("""
                SELECT MAX(date_local)
                FROM daily_features
            """).fetchone()[0]

            last_feature_v2 = con.execute("""
                SELECT MAX(date_local)
                FROM daily_features_v2
            """).fetchone()[0]

            return {
                "bars_1m": bars_1m,
                "bars_5m": bars_5m,
                "daily_features": daily_features,
                "daily_features_v2": daily_features_v2,
                "last_1m_date": last_1m,
                "last_feature_date": last_feature,
                "last_feature_v2_date": last_feature_v2,
            }
        finally:
            con.close()

    def update(self, days_back: Optional[int] = None) -> None:
        """Run the daily update process"""
        print("="*80)
        print("DAILY UPDATE - Gold (MGC) Data Pipeline")
        print("="*80)

        # Show current state
        print("\nCurrent database state:")
        counts = self.get_row_counts()
        print(f"  bars_1m: {counts['bars_1m']:,} rows (last: {counts['last_1m_date']})")
        print(f"  bars_5m: {counts['bars_5m']:,} rows")
        print(f"  daily_features: {counts['daily_features']:,} rows (last: {counts['last_feature_date']})")
        print(f"  daily_features_v2: {counts['daily_features_v2']:,} rows (last: {counts['last_feature_v2_date']})")

        # Determine update range
        start_date, end_date = self.get_date_range_to_update(days_back)

        days_to_update = (end_date - start_date).days + 1
        print(f"\nUpdate plan:")
        print(f"  Start date: {start_date.strftime('%Y-%m-%d')}")
        print(f"  End date:   {end_date.strftime('%Y-%m-%d')}")
        print(f"  Days:       {days_to_update}")

        if self.dry_run:
            print("\n[DRY RUN MODE] - No changes will be made")

        # Run backfill
        print("\n" + "="*80)
        print("STEP 1: Backfill data from Databento")
        print("="*80)

        success = self.run_backfill(start_date, end_date)
        if not success:
            print("\nERROR: Backfill failed. Aborting update.")
            sys.exit(1)

        # Show updated state
        if not self.dry_run:
            print("\n" + "="*80)
            print("Updated database state:")
            print("="*80)
            counts_after = self.get_row_counts()
            print(f"  bars_1m: {counts_after['bars_1m']:,} rows (last: {counts_after['last_1m_date']})")
            print(f"  bars_5m: {counts_after['bars_5m']:,} rows")
            print(f"  daily_features: {counts_after['daily_features']:,} rows (last: {counts_after['last_feature_date']})")
            print(f"  daily_features_v2: {counts_after['daily_features_v2']:,} rows (last: {counts_after['last_feature_v2_date']})")

            rows_added = counts_after['bars_1m'] - counts['bars_1m']
            if rows_added > 0:
                print(f"\n  Added {rows_added:,} new 1-minute bars")
            else:
                print("\n  No new data (database already up-to-date)")

        # Run daily alerts for today
        print("\n" + "="*80)
        print("STEP 2: Generate daily alerts")
        print("="*80)

        self.run_daily_alerts(date.today())

        # Final summary
        print("\n" + "="*80)
        print("UPDATE COMPLETE")
        print("="*80)

        if not self.dry_run:
            print(f"\nYour database is now up-to-date through {end_date.strftime('%Y-%m-%d')}")
            print("\nNext steps:")
            print("  1. Review the daily alerts above")
            print("  2. Use filter_orb_setups.py to find specific setups")
            print("  3. Run analyze_orb_performance.py for updated statistics")
        else:
            print("\n[DRY RUN] No changes were made to the database")


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally update MGC data and generate daily alerts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it",
    )

    parser.add_argument(
        "--days",
        type=int,
        metavar="N",
        help="Fetch last N days (instead of incremental from last date)",
    )

    args = parser.parse_args()

    updater = DailyUpdater(dry_run=args.dry_run)
    updater.update(days_back=args.days)


if __name__ == "__main__":
    main()
