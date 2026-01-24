"""
Temporal Integrity Test Suite

Validates ORB window alignment across DST regimes and timezone transitions.

CRITICAL: These tests prevent timezone bugs that could cause:
- 1-hour offset in session windows
- Wrong ORB detection timing
- Incorrect entry signals

Test Coverage:
1. AEST period (Brisbane standard time, no US DST)
2. US DST start (March 2nd Sunday 2am)
3. US DST end (November 1st Sunday 2am)
4. Midnight-crossing windows (NY 23:00→00:30)
5. All 6 ORB alignments (09:00, 10:00, 11:00, 18:00, 23:00, 00:30)
"""

import pytest
import duckdb
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Tuple

TZ_LOCAL = ZoneInfo("Australia/Brisbane")  # UTC+10, no DST
TZ_UTC = ZoneInfo("UTC")

DB_PATH = "gold.db"
SYMBOL = "MGC"


def _dt_local(d: date, hh: int, mm: int) -> datetime:
    """Create Brisbane-aware datetime."""
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ_LOCAL)


def local_window_to_utc(start_local: datetime, end_local: datetime) -> Tuple[datetime, datetime]:
    """Convert local window to UTC."""
    return start_local.astimezone(TZ_UTC), end_local.astimezone(TZ_UTC)


class TestTemporalIntegrity:
    """Temporal integrity test suite."""

    def setup_method(self):
        """Setup database connection."""
        self.con = duckdb.connect(DB_PATH, read_only=True)

    def teardown_method(self):
        """Close database connection."""
        self.con.close()

    # -------------------------------------------------------------------------
    # 1. AEST Period (Brisbane Standard Time, Winter)
    # -------------------------------------------------------------------------

    def test_orb_window_aest_winter(self):
        """
        Verify ORB windows during AEST (Brisbane standard time, winter).

        Test Date: 2025-06-15 (June, Southern Hemisphere winter)
        Brisbane: UTC+10, no DST
        US: No DST active (between DST end and start)

        Expected:
        - 09:00 Brisbane = 23:00 UTC (previous day)
        - 18:00 Brisbane = 08:00 UTC (same day)
        """
        test_date = date(2025, 6, 15)

        # 09:00 ORB (Asia open)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_end_local = _dt_local(test_date, 9, 5)
        orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

        # Assert: 09:00 Brisbane = 23:00 UTC (previous day)
        assert orb_start_utc.hour == 23
        assert orb_start_utc.day == 14  # Previous day
        assert orb_end_utc.hour == 23
        assert orb_end_utc.minute == 5

        # 18:00 ORB (London open)
        london_start_local = _dt_local(test_date, 18, 0)
        london_end_local = _dt_local(test_date, 18, 5)
        london_start_utc, london_end_utc = local_window_to_utc(london_start_local, london_end_local)

        # Assert: 18:00 Brisbane = 08:00 UTC (same day)
        assert london_start_utc.hour == 8
        assert london_start_utc.day == 15
        assert london_end_utc.hour == 8
        assert london_end_utc.minute == 5

    # -------------------------------------------------------------------------
    # 2. US DST Start (March 2nd Sunday 2am)
    # -------------------------------------------------------------------------

    def test_orb_window_us_dst_start(self):
        """
        Verify ORB windows during US DST start (March 2nd Sunday 2am).

        Test Date: 2025-03-09 (US DST starts - clocks spring forward 1 hour)
        Brisbane: UTC+10, no DST (never changes)
        US: Clocks jump 2am → 3am

        Expected:
        - Brisbane time remains stable (always UTC+10)
        - ORB windows should NOT shift despite US clock change
        - 09:00 Brisbane = 23:00 UTC (previous day) - SAME AS WINTER
        """
        test_date = date(2025, 3, 9)

        # 09:00 ORB (Asia open)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_end_local = _dt_local(test_date, 9, 5)
        orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

        # Assert: No change in Brisbane→UTC mapping (Brisbane has no DST)
        assert orb_start_utc.hour == 23
        assert orb_start_utc.day == 8  # Previous day
        assert orb_end_utc.hour == 23
        assert orb_end_utc.minute == 5

        # Verify midnight-crossing window still works
        ny_start_local = _dt_local(test_date, 23, 0)
        ny_end_local = _dt_local(test_date + timedelta(days=1), 0, 30)
        ny_start_utc, ny_end_utc = local_window_to_utc(ny_start_local, ny_end_local)

        assert ny_start_utc.hour == 13
        assert ny_start_utc.day == 9
        assert ny_end_utc.hour == 14
        assert ny_end_utc.minute == 30
        assert ny_end_utc.day == 9  # Same UTC day

    # -------------------------------------------------------------------------
    # 3. US DST End (November 1st Sunday 2am)
    # -------------------------------------------------------------------------

    def test_orb_window_us_dst_end(self):
        """
        Verify ORB windows during US DST end (November 1st Sunday 2am).

        Test Date: 2025-11-02 (US DST ends - clocks fall back 1 hour)
        Brisbane: UTC+10, no DST (never changes)
        US: Clocks jump 2am → 1am (repeats 1am-2am hour)

        Expected:
        - Brisbane time remains stable
        - ORB windows should NOT shift
        """
        test_date = date(2025, 11, 2)

        # 09:00 ORB (Asia open)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_end_local = _dt_local(test_date, 9, 5)
        orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

        # Assert: Still 23:00 UTC (previous day) - Brisbane never changes
        assert orb_start_utc.hour == 23
        assert orb_start_utc.day == 1  # Previous day
        assert orb_end_utc.hour == 23
        assert orb_end_utc.minute == 5

    # -------------------------------------------------------------------------
    # 4. Midnight-Crossing Windows
    # -------------------------------------------------------------------------

    def test_midnight_crossing_ny_session(self):
        """
        Verify NY session (23:00→00:30) correctly crosses midnight.

        Window: D 23:00 → (D+1) 00:30 Brisbane time

        Expected:
        - Window spans 90 minutes (1.5 hours)
        - No off-by-one errors in bar counting
        - UTC conversion handles date change correctly
        """
        test_date = date(2025, 6, 15)

        # NY session: 23:00 Brisbane → 00:30 next day Brisbane
        start_local = _dt_local(test_date, 23, 0)
        end_local = _dt_local(test_date + timedelta(days=1), 0, 30)
        start_utc, end_utc = local_window_to_utc(start_local, end_local)

        # Verify window duration
        duration = (end_utc - start_utc).total_seconds() / 60
        assert duration == 90, f"Expected 90 minutes, got {duration}"

        # Verify UTC timestamps
        assert start_utc.hour == 13
        assert end_utc.hour == 14
        assert end_utc.minute == 30

        # Both should be same UTC day
        assert start_utc.day == end_utc.day

    def test_midnight_crossing_0030_orb(self):
        """
        Verify 00:30 ORB (next day Brisbane time) correctly handled.

        ORB: (D+1) 00:30 → (D+1) 00:35 Brisbane time

        Expected:
        - ORB is on next calendar day (Brisbane local)
        - UTC conversion correct
        """
        test_date = date(2025, 6, 15)

        # 00:30 ORB is NEXT DAY in Brisbane time
        orb_start_local = _dt_local(test_date + timedelta(days=1), 0, 30)
        orb_end_local = _dt_local(test_date + timedelta(days=1), 0, 35)
        orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

        # Verify UTC conversion
        assert orb_start_utc.hour == 14
        assert orb_start_utc.minute == 30
        assert orb_end_utc.hour == 14
        assert orb_end_utc.minute == 35

        # Duration: 5 minutes
        duration = (orb_end_utc - orb_start_utc).total_seconds() / 60
        assert duration == 5

    # -------------------------------------------------------------------------
    # 5. All 6 ORB Alignment (Integration Test)
    # -------------------------------------------------------------------------

    def test_all_six_orb_alignment(self):
        """
        Verify all 6 ORBs align correctly to Brisbane time.

        ORBs: 09:00, 10:00, 11:00, 18:00, 23:00, 00:30 (next day)
        All should be exactly 5 minutes duration.
        """
        test_date = date(2025, 6, 15)

        orb_times = [
            (test_date, 9, 0, "0900"),
            (test_date, 10, 0, "1000"),
            (test_date, 11, 0, "1100"),
            (test_date, 18, 0, "1800"),
            (test_date, 23, 0, "2300"),
            (test_date + timedelta(days=1), 0, 30, "0030"),  # Next day
        ]

        for d, hh, mm, name in orb_times:
            orb_start_local = _dt_local(d, hh, mm)
            orb_end_local = orb_start_local + timedelta(minutes=5)
            orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

            # Verify duration: exactly 5 minutes
            duration = (orb_end_utc - orb_start_utc).total_seconds() / 60
            assert duration == 5, f"ORB {name}: Expected 5 minutes, got {duration}"

            # Verify UTC minute precision
            assert orb_start_utc.second == 0, f"ORB {name}: Start should be at :00 seconds"
            assert orb_end_utc.second == 0, f"ORB {name}: End should be at :00 seconds"

    # -------------------------------------------------------------------------
    # 6. Database Integration Test (Optional - requires data)
    # -------------------------------------------------------------------------

    @pytest.mark.skipif(True, reason="Requires database with actual bars")
    def test_orb_bars_count_integrity(self):
        """
        Verify ORB window fetches exactly 5 bars from database.

        This test requires actual 1-minute bars in the database.
        """
        test_date = date(2025, 6, 15)

        orb_start_local = _dt_local(test_date, 9, 0)
        orb_end_local = _dt_local(test_date, 9, 5)
        orb_start_utc, orb_end_utc = local_window_to_utc(orb_start_local, orb_end_local)

        # Fetch bars from database
        result = self.con.execute(
            """
            SELECT COUNT(*)
            FROM bars_1m
            WHERE symbol = ?
              AND ts_utc >= ?
              AND ts_utc < ?
            """,
            [SYMBOL, orb_start_utc, orb_end_utc]
        ).fetchone()

        bar_count = result[0] if result else 0

        # Should be exactly 5 bars (09:00, 09:01, 09:02, 09:03, 09:04)
        assert bar_count == 5, f"Expected 5 bars in ORB window, got {bar_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
