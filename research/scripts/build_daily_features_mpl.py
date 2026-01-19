"""
Daily Feature Builder for MPL - Port of V2 with MPL-specific parameters
========================================================================

Same session windows and ORB logic as MGC/NQ, but adapted for MPL (Micro Platinum):
- Symbol: MPL (continuous)
- Tables: bars_1m_mpl, bars_5m_mpl
- Tick size: 0.1 (same as MGC)
- Output: daily_features_v2_mpl

Usage:
  python scripts/build_daily_features_mpl.py 2025-01-13
  python scripts/build_daily_features_mpl.py 2025-01-13 2025-11-21
  python scripts/build_daily_features_mpl.py 2025-01-13 2025-11-21 --sl-mode half
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the V2 feature builder
from build_daily_features_v2 import (
    FeatureBuilderV2,
    TZ_LOCAL,
    TZ_UTC,
    _dt_local,
)
from datetime import date, datetime, timedelta
import duckdb


class MPLFeatureBuilder(FeatureBuilderV2):
    """
    MPL-specific feature builder

    Inherits all logic from MGC V2 builder, overrides only:
    - Symbol name
    - Table names
    - Tick size (0.1, same as MGC)
    - Output table
    """

    def __init__(self, db_path: str = "gold.db", sl_mode: str = "full"):
        # Don't call super().__init__() - we'll override everything
        self.con = duckdb.connect(db_path)
        self.sl_mode = sl_mode
        self.table_name = "daily_features_v2_mpl"

        # MPL-specific parameters
        self.symbol = "MPL"
        self.bars_1m_table = "bars_1m_mpl"
        self.bars_5m_table = "bars_5m_mpl"
        self.tick_size = 0.1  # MPL tick size (same as MGC)

    def _window_stats_1m(self, start_local: datetime, end_local: datetime):
        """Override to use MPL tables"""
        start_utc = start_local.astimezone(TZ_UTC)
        end_utc = end_local.astimezone(TZ_UTC)

        row = self.con.execute(
            f"""
            SELECT
              MAX(high) AS high,
              MIN(low)  AS low,
              MAX(high) - MIN(low) AS range,
              SUM(volume) AS volume
            FROM {self.bars_1m_table}
            WHERE symbol = ?
              AND ts_utc >= ? AND ts_utc < ?
            """,
            [self.symbol, start_utc, end_utc],
        ).fetchone()

        if not row or row[0] is None:
            return None

        high, low, rng, vol = row
        return {
            "high": float(high),
            "low": float(low),
            "range": float(rng),
            "range_ticks": float(rng) / self.tick_size if rng is not None else None,
            "volume": int(vol) if vol is not None else 0,
        }

    def _fetch_1m_bars(self, start_local: datetime, end_local: datetime):
        """Override to use MPL tables"""
        start_utc = start_local.astimezone(TZ_UTC)
        end_utc = end_local.astimezone(TZ_UTC)

        return self.con.execute(
            f"""
            SELECT ts_utc, high, low, close
            FROM {self.bars_1m_table}
            WHERE symbol = ?
              AND ts_utc >= ? AND ts_utc < ?
            ORDER BY ts_utc
            """,
            [self.symbol, start_utc, end_utc],
        ).fetchall()

    def _fetch_5m_bars(self, start_local: datetime, end_local: datetime):
        """Override to use MPL tables"""
        start_utc = start_local.astimezone(TZ_UTC)
        end_utc = end_local.astimezone(TZ_UTC)

        return self.con.execute(
            f"""
            SELECT ts_utc, high, low, close
            FROM {self.bars_5m_table}
            WHERE symbol = ?
              AND ts_utc >= ? AND ts_utc < ?
            ORDER BY ts_utc
            """,
            [self.symbol, start_utc, end_utc],
        ).fetchall()


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/build_daily_features_mpl.py YYYY-MM-DD [YYYY-MM-DD] [--sl-mode full|half]")
        print("\nExamples:")
        print("  python scripts/build_daily_features_mpl.py 2025-01-13")
        print("  python scripts/build_daily_features_mpl.py 2025-01-13 2025-11-21")
        print("  python scripts/build_daily_features_mpl.py 2025-01-13 2025-11-21 --sl-mode half")
        sys.exit(1)

    # Parse arguments
    start_date = date.fromisoformat(sys.argv[1])

    if len(sys.argv) >= 3 and not sys.argv[2].startswith("--"):
        end_date = date.fromisoformat(sys.argv[2])
    else:
        end_date = start_date

    # Check for --sl-mode flag
    sl_mode = "full"
    if "--sl-mode" in sys.argv:
        idx = sys.argv.index("--sl-mode")
        if idx + 1 < len(sys.argv):
            sl_mode = sys.argv[idx + 1]
            if sl_mode not in ["full", "half"]:
                print(f"ERROR: Invalid sl_mode '{sl_mode}'. Must be 'full' or 'half'")
                sys.exit(1)

    print(f"MPL Daily Feature Builder V2")
    print(f"Date range: {start_date} -> {end_date}")
    print(f"SL mode: {sl_mode}")
    print()

    builder = MPLFeatureBuilder(sl_mode=sl_mode)

    try:
        # Process each date
        current = start_date
        success_count = 0
        fail_count = 0

        while current <= end_date:
            try:
                builder.build_features(current)
                print(f"OK: {current}")
                success_count += 1
            except Exception as e:
                print(f"FAIL: {current} - {e}")
                fail_count += 1

            current += timedelta(days=1)

        print()
        print(f"DONE: {success_count} days processed, {fail_count} failures")

    finally:
        builder.con.close()


if __name__ == "__main__":
    main()
