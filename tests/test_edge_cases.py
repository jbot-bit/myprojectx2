"""
Edge Case Test Suite

Validates system behavior on data quality issues and edge cases.

CRITICAL: These tests ensure the system "fails loudly" instead of silently
producing incorrect results.

Test Coverage:
1. Missing bars in ORB window
2. Duplicate timestamps
3. Out-of-order bars
4. Holiday/weekend (no data)
5. DST boundary day
6. ORB window with gap
7. Partial trading day (early close)
"""

import pytest
import duckdb
import tempfile
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

TZ_LOCAL = ZoneInfo("Australia/Brisbane")
TZ_UTC = ZoneInfo("UTC")

SYMBOL = "MGC"


def _dt_local(d: date, hh: int, mm: int) -> datetime:
    """Create Brisbane-aware datetime."""
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ_LOCAL)


class TestEdgeCases:
    """Edge case test suite."""

    def setup_method(self):
        """Setup temporary database for testing."""
        # Create temporary database - delete empty file first so DuckDB can create it
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = self.temp_db.name
        self.temp_db.close()
        os.unlink(self.db_path)  # Delete empty file

        self.con = duckdb.connect(self.db_path)

        # Create schema
        self.con.execute("""
            CREATE TABLE bars_1m (
                ts_utc TIMESTAMPTZ NOT NULL,
                symbol VARCHAR NOT NULL,
                source_symbol VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume BIGINT,
                PRIMARY KEY (symbol, ts_utc)
            )
        """)

    def teardown_method(self):
        """Cleanup temporary database."""
        self.con.close()
        try:
            os.unlink(self.db_path)
        except:
            pass

    def _insert_bar(self, ts_utc: datetime, symbol: str = SYMBOL,
                    open_price: float = 100.0, high: float = 100.5,
                    low: float = 99.5, close: float = 100.0, volume: int = 100):
        """Helper: Insert a single bar."""
        self.con.execute(
            """
            INSERT INTO bars_1m (ts_utc, symbol, source_symbol, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [ts_utc, symbol, 'MGCG4', open_price, high, low, close, volume]
        )

    def _fetch_orb_stats(self, start_utc: datetime, end_utc: datetime):
        """Helper: Fetch ORB statistics (mimics build_daily_features_v2.py logic)."""
        row = self.con.execute(
            """
            SELECT
              MAX(high) AS high,
              MIN(low)  AS low,
              MAX(high) - MIN(low) AS range,
              SUM(volume) AS volume
            FROM bars_1m
            WHERE symbol = ?
              AND ts_utc >= ? AND ts_utc < ?
            """,
            [SYMBOL, start_utc, end_utc],
        ).fetchone()

        if not row or row[0] is None:
            return None

        high, low, rng, vol = row
        return {
            "high": float(high),
            "low": float(low),
            "range": float(rng),
            "volume": int(vol) if vol is not None else 0,
        }

    # -------------------------------------------------------------------------
    # 1. Missing Bars in ORB Window
    # -------------------------------------------------------------------------

    def test_missing_bars_in_orb_window(self):
        """
        Test ORB calculation when bars are missing in ORB window.

        Scenario: 09:00-09:05 ORB missing 09:02 bar
        Expected: ORB should still calculate (using available bars) or return None
        """
        test_date = date(2025, 6, 15)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)

        # Insert 4 bars (missing 09:02 -> missing UTC equivalent)
        for i in [0, 1, 3, 4]:  # Skip i=2 (missing bar)
            ts_utc = orb_start_utc + timedelta(minutes=i)
            self._insert_bar(ts_utc, high=100.0 + i * 0.1, low=100.0, close=100.0 + i * 0.05)

        # Fetch ORB stats
        orb_end_utc = orb_start_utc + timedelta(minutes=5)
        stats = self._fetch_orb_stats(orb_start_utc, orb_end_utc)

        # Should still calculate using available bars
        assert stats is not None, "ORB should calculate with partial bars"
        assert stats["high"] == 100.4, "High should be from 09:04 bar"
        assert stats["low"] == 100.0

        # Volume should reflect only 4 bars
        assert stats["volume"] == 400  # 4 bars * 100 volume each

    def test_completely_missing_orb_window(self):
        """
        Test ORB calculation when entire ORB window has no data.

        Scenario: Weekend or holiday - no bars at all
        Expected: Return None (no data)
        """
        test_date = date(2025, 12, 25)  # Christmas (likely no trading)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)
        orb_end_utc = orb_start_utc + timedelta(minutes=5)

        # No bars inserted (empty database)

        stats = self._fetch_orb_stats(orb_start_utc, orb_end_utc)

        # Should return None (no data)
        assert stats is None, "ORB should return None when no data available"

    # -------------------------------------------------------------------------
    # 2. Duplicate Timestamps
    # -------------------------------------------------------------------------

    def test_duplicate_timestamps_rejected(self):
        """
        Test that duplicate timestamps are rejected by database.

        Scenario: Attempt to insert same timestamp twice
        Expected: Database raises constraint violation (PRIMARY KEY)
        """
        test_date = date(2025, 6, 15)
        ts_utc = _dt_local(test_date, 9, 0).astimezone(TZ_UTC)

        # Insert first bar
        self._insert_bar(ts_utc, close=100.0)

        # Attempt to insert duplicate timestamp
        with pytest.raises(Exception) as exc_info:
            self._insert_bar(ts_utc, close=101.0)  # Different price, same timestamp

        # Should raise constraint violation
        assert "constraint" in str(exc_info.value).lower() or "unique" in str(exc_info.value).lower()

    # -------------------------------------------------------------------------
    # 3. Out-of-Order Bars
    # -------------------------------------------------------------------------

    def test_out_of_order_bars_query_handles_correctly(self):
        """
        Test that query ordering handles out-of-order inserts.

        Scenario: Insert bars in non-chronological order
        Expected: Query returns bars in correct order (ORDER BY ts_utc)
        """
        test_date = date(2025, 6, 15)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)

        # Insert bars OUT OF ORDER
        timestamps = [
            orb_start_utc + timedelta(minutes=3),  # 09:03 (inserted first)
            orb_start_utc + timedelta(minutes=0),  # 09:00 (inserted second)
            orb_start_utc + timedelta(minutes=4),  # 09:04
            orb_start_utc + timedelta(minutes=1),  # 09:01
            orb_start_utc + timedelta(minutes=2),  # 09:02
        ]

        for i, ts_utc in enumerate(timestamps):
            self._insert_bar(ts_utc, close=100.0 + i)  # Different close prices

        # Fetch bars with ORDER BY
        result = self.con.execute(
            """
            SELECT ts_utc, close
            FROM bars_1m
            WHERE symbol = ?
              AND ts_utc >= ?
              AND ts_utc < ?
            ORDER BY ts_utc
            """,
            [SYMBOL, orb_start_utc, orb_start_utc + timedelta(minutes=5)]
        ).fetchall()

        # Verify returned in chronological order (not insert order)
        assert len(result) == 5
        for i in range(1, 5):
            assert result[i][0] > result[i-1][0], "Bars should be in chronological order"

    # -------------------------------------------------------------------------
    # 4. Holiday/Weekend (No Data)
    # -------------------------------------------------------------------------

    def test_weekend_no_data_handled_gracefully(self):
        """
        Test weekend (no trading) is handled gracefully.

        Scenario: Query for bars on Saturday (no market data)
        Expected: Return None, no crash
        """
        test_date = date(2025, 6, 14)  # Saturday
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)
        orb_end_utc = orb_start_utc + timedelta(minutes=5)

        # No bars inserted (weekend)

        stats = self._fetch_orb_stats(orb_start_utc, orb_end_utc)

        # Should return None gracefully
        assert stats is None

    # -------------------------------------------------------------------------
    # 5. DST Boundary Day
    # -------------------------------------------------------------------------

    def test_dst_boundary_day_no_offset_errors(self):
        """
        Test DST boundary day doesn't cause offset errors.

        Scenario: US DST start (March 2nd Sunday) - 1am-2am "missing"
        Expected: Brisbane time remains stable, no offset errors
        """
        test_date = date(2025, 3, 9)  # US DST start
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)

        # Insert 5 bars for ORB window
        for i in range(5):
            ts_utc = orb_start_utc + timedelta(minutes=i)
            self._insert_bar(ts_utc, high=100.0 + i * 0.1, low=100.0, close=100.0 + i * 0.05)

        # Fetch ORB stats
        orb_end_utc = orb_start_utc + timedelta(minutes=5)
        stats = self._fetch_orb_stats(orb_start_utc, orb_end_utc)

        # Should calculate normally (Brisbane unaffected by US DST)
        assert stats is not None
        assert stats["volume"] == 500  # 5 bars

        # Verify UTC hour is still 23 (prev day) for 09:00 Brisbane
        assert orb_start_utc.hour == 23
        assert orb_start_utc.day == 8  # Previous day

    # -------------------------------------------------------------------------
    # 6. ORB Window with Gap (Missing Middle Bars)
    # -------------------------------------------------------------------------

    def test_orb_window_with_gap_in_middle(self):
        """
        Test ORB calculation when gap exists in middle of window.

        Scenario: 09:00-09:05 window with 09:01, 09:02, 09:03 missing
        Expected: ORB calculated from available bars (09:00, 09:04 only)
        """
        test_date = date(2025, 6, 15)
        orb_start_local = _dt_local(test_date, 9, 0)
        orb_start_utc = orb_start_local.astimezone(TZ_UTC)

        # Insert only first and last bar (gap in middle)
        self._insert_bar(orb_start_utc, high=100.5, low=100.0, close=100.2)  # 09:00
        self._insert_bar(orb_start_utc + timedelta(minutes=4), high=101.0, low=100.3, close=100.8)  # 09:04

        # Fetch ORB stats
        orb_end_utc = orb_start_utc + timedelta(minutes=5)
        stats = self._fetch_orb_stats(orb_start_utc, orb_end_utc)

        # Should calculate using available bars
        assert stats is not None
        assert stats["high"] == 101.0  # From 09:04 bar
        assert stats["low"] == 100.0  # From 09:00 bar
        assert stats["range"] == 1.0
        assert stats["volume"] == 200  # Only 2 bars

    # -------------------------------------------------------------------------
    # 7. Partial Trading Day (Early Close)
    # -------------------------------------------------------------------------

    def test_partial_trading_day_early_close(self):
        """
        Test partial trading day (e.g., early close before holiday).

        Scenario: Market closes at 12:00 (early close)
        Expected: ORBs before 12:00 calculate normally, after 12:00 return None
        """
        test_date = date(2025, 6, 15)

        # Insert bars from 09:00 to 11:59 (market closes at 12:00)
        start_local = _dt_local(test_date, 9, 0)
        start_utc = start_local.astimezone(TZ_UTC)

        # Insert bars for 3 hours (09:00-11:59)
        for i in range(180):  # 180 minutes
            ts_utc = start_utc + timedelta(minutes=i)
            self._insert_bar(ts_utc, close=100.0 + i * 0.01)

        # Test 11:00 ORB (should work - before close)
        orb_1100_local = _dt_local(test_date, 11, 0)
        orb_1100_utc = orb_1100_local.astimezone(TZ_UTC)
        stats_1100 = self._fetch_orb_stats(orb_1100_utc, orb_1100_utc + timedelta(minutes=5))

        assert stats_1100 is not None, "11:00 ORB should work (before early close)"
        assert stats_1100["volume"] == 500  # 5 bars

        # Test 18:00 ORB (should fail - after early close, no data)
        orb_1800_local = _dt_local(test_date, 18, 0)
        orb_1800_utc = orb_1800_local.astimezone(TZ_UTC)
        stats_1800 = self._fetch_orb_stats(orb_1800_utc, orb_1800_utc + timedelta(minutes=5))

        assert stats_1800 is None, "18:00 ORB should return None (no data after early close)"


class TestDataQualityLogging:
    """Test data quality logging behavior (if implemented)."""

    @pytest.mark.skip(reason="Data quality logging not yet implemented")
    def test_missing_bars_logged_as_warning(self):
        """
        Test that missing bars are logged as warnings.

        Expected: Logger.warning() called when bars are missing
        """
        # TODO: Implement when logging is added to build_daily_features_v2.py
        pass

    @pytest.mark.skip(reason="Data quality logging not yet implemented")
    def test_gap_detection_logged(self):
        """
        Test that gaps in data are detected and logged.

        Expected: Logger.warning() called when gap > 5 minutes detected
        """
        # TODO: Implement when gap detection is added
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
