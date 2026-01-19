"""
Daily Feature Builder for NQ - Port of V2 with NQ-specific parameters
======================================================================

Same session windows and ORB logic as MGC, but adapted for NQ (Nasdaq futures):
- Symbol: NQ (continuous)
- Tables: bars_1m_nq, bars_5m_nq
- Tick size: 0.25 (vs 0.1 for MGC)
- Output: daily_features_v2_nq

Usage:
  python scripts/build_daily_features_nq.py 2025-01-13
  python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21
  python scripts/build_daily_features_nq.py 2025-01-13 2025-11-21 --sl-mode half
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


class NQFeatureBuilder(FeatureBuilderV2):
    """
    NQ-specific feature builder

    Inherits all logic from MGC V2 builder, overrides only:
    - Symbol name
    - Table names
    - Tick size
    - Output table
    """

    def __init__(self, db_path: str = "gold.db", sl_mode: str = "full"):
        # Don't call super().__init__() - we'll override everything
        self.con = duckdb.connect(db_path)
        self.sl_mode = sl_mode
        self.table_name = "daily_features_v2_nq"

        # NQ-specific parameters
        self.symbol = "NQ"
        self.bars_1m_table = "bars_1m_nq"
        self.bars_5m_table = "bars_5m_nq"
        self.tick_size = 0.25  # NQ tick size

    def _window_stats_1m(self, start_local: datetime, end_local: datetime):
        """Override to use NQ tables"""
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
        """Override to use NQ tables"""
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

    def calculate_orb_1m_exec(self, orb_start_local: datetime, scan_end_local: datetime, rr: float = 1.0, sl_mode: str = None):
        """
        Calculate ORB with NQ tick size

        Inherits full logic from parent, but uses NQ-specific tick size (0.25)
        """
        if sl_mode is None:
            sl_mode = self.sl_mode

        # Get ORB window bars (first 5 minutes)
        orb_end = orb_start_local + timedelta(minutes=5)
        orb_bars = self._fetch_1m_bars(orb_start_local, orb_end)
        if not orb_bars:
            return None

        # Calculate ORB range
        orb_high = max(float(bar[1]) for bar in orb_bars)
        orb_low = min(float(bar[2]) for bar in orb_bars)
        orb_size = orb_high - orb_low
        orb_mid = (orb_high + orb_low) / 2.0

        # Get subsequent bars for entry detection
        bars = self._fetch_1m_bars(orb_end, scan_end_local)
        if not bars:
            return {
                "high": orb_high, "low": orb_low, "size": orb_size,
                "break_dir": "NONE", "outcome": "NO_TRADE", "r_multiple": None,
                "mae": None, "mfe": None, "stop_price": None, "risk_ticks": None
            }

        # Find entry: first close outside ORB
        entry_ts = None
        entry_close = None
        break_dir = None

        for ts_utc, h, l, c in bars:
            c = float(c)
            if c > orb_high:
                entry_ts = ts_utc
                entry_close = c
                break_dir = "UP"
                break
            elif c < orb_low:
                entry_ts = ts_utc
                entry_close = c
                break_dir = "DOWN"
                break

        if not entry_ts:
            return {
                "high": orb_high, "low": orb_low, "size": orb_size,
                "break_dir": "NONE", "outcome": "NO_TRADE", "r_multiple": None,
                "mae": None, "mfe": None, "stop_price": None, "risk_ticks": None
            }

        # GUARDRAIL: Entry must NOT be at ORB edge
        if abs(entry_close - orb_high) < 0.01 or abs(entry_close - orb_low) < 0.01:
            return {
                "high": orb_high, "low": orb_low, "size": orb_size,
                "break_dir": break_dir, "outcome": "NO_TRADE", "r_multiple": None,
                "mae": None, "mfe": None, "stop_price": None, "risk_ticks": None
            }

        # Calculate stop and target
        orb_edge = orb_high if break_dir == "UP" else orb_low

        if sl_mode == "full":
            stop = orb_low if break_dir == "UP" else orb_high
        else:  # half
            stop = orb_mid

        # ORB-anchored R
        r_orb = abs(orb_edge - stop)
        risk_ticks = r_orb / self.tick_size  # NQ tick size

        if r_orb <= 0:
            return {
                "high": orb_high, "low": orb_low, "size": orb_size,
                "break_dir": break_dir, "outcome": "NO_TRADE", "r_multiple": None,
                "mae": None, "mfe": None,
                "stop_price": stop, "risk_ticks": 0.0
            }

        # ORB-anchored target
        target = orb_edge + rr * r_orb if break_dir == "UP" else orb_edge - rr * r_orb

        # Track MAE/MFE from ORB EDGE
        mae_raw = 0.0
        mfe_raw = 0.0

        # Start checking AFTER entry bar
        start_i = 0
        for i, (ts_utc, _, _, _) in enumerate(bars):
            if ts_utc == entry_ts:
                start_i = i + 1
                break

        for ts_utc, h, l, c in bars[start_i:]:
            h = float(h)
            l = float(l)

            # Update MAE/MFE
            if break_dir == "UP":
                mae_raw = max(mae_raw, orb_edge - l)
                mfe_raw = max(mfe_raw, h - orb_edge)

                hit_stop = l <= stop
                hit_target = h >= target

                if hit_stop and hit_target:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "LOSS", "r_multiple": -1.0,
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }
                if hit_target:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "WIN", "r_multiple": float(rr),
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }
                if hit_stop:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "LOSS", "r_multiple": -1.0,
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }
            else:  # DOWN
                mae_raw = max(mae_raw, h - orb_edge)
                mfe_raw = max(mfe_raw, orb_edge - l)

                hit_stop = h >= stop
                hit_target = l <= target

                if hit_stop and hit_target:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "LOSS", "r_multiple": -1.0,
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }
                if hit_target:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "WIN", "r_multiple": float(rr),
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }
                if hit_stop:
                    return {
                        "high": orb_high, "low": orb_low, "size": orb_size,
                        "break_dir": break_dir, "outcome": "LOSS", "r_multiple": -1.0,
                        "mae": mae_raw / r_orb, "mfe": mfe_raw / r_orb,
                        "stop_price": stop, "risk_ticks": risk_ticks
                    }

        # No outcome before scan window ended
        return {
            "high": orb_high, "low": orb_low, "size": orb_size,
            "break_dir": break_dir, "outcome": "NO_TRADE", "r_multiple": None,
            "mae": mae_raw / r_orb if r_orb > 0 else None,
            "mfe": mfe_raw / r_orb if r_orb > 0 else None,
            "stop_price": stop, "risk_ticks": risk_ticks
        }

    def calculate_rsi_14(self, end_local: datetime, period: int = 14):
        """Calculate RSI using NQ tables"""
        start_local = end_local - timedelta(minutes=period * 5 + 60)
        bars = self.con.execute(
            f"""
            SELECT close
            FROM {self.bars_5m_table}
            WHERE symbol = ?
              AND ts_utc >= ? AND ts_utc <= ?
            ORDER BY ts_utc
            """,
            [self.symbol, start_local.astimezone(TZ_UTC), end_local.astimezone(TZ_UTC)],
        ).fetchall()

        if len(bars) < period + 1:
            return None

        closes = [float(b[0]) for b in bars]
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi


def main():
    """Run NQ feature building"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse arguments
    start_date = date.fromisoformat(sys.argv[1])
    end_date = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else start_date
    sl_mode = "full"

    if "--sl-mode" in sys.argv:
        idx = sys.argv.index("--sl-mode")
        if idx + 1 < len(sys.argv):
            sl_mode = sys.argv[idx + 1]

    print(f"Building NQ daily features from {start_date} to {end_date} (SL mode: {sl_mode})")

    # Create feature builder
    builder = NQFeatureBuilder(sl_mode=sl_mode)

    # Initialize output table
    builder.con.execute(f"""
        CREATE TABLE IF NOT EXISTS {builder.table_name} (
          date_local DATE NOT NULL,
          instrument VARCHAR NOT NULL,

          pre_asia_high DOUBLE,
          pre_asia_low DOUBLE,
          pre_asia_range DOUBLE,
          pre_london_high DOUBLE,
          pre_london_low DOUBLE,
          pre_london_range DOUBLE,
          pre_ny_high DOUBLE,
          pre_ny_low DOUBLE,
          pre_ny_range DOUBLE,

          asia_high DOUBLE,
          asia_low DOUBLE,
          asia_range DOUBLE,
          london_high DOUBLE,
          london_low DOUBLE,
          london_range DOUBLE,
          ny_high DOUBLE,
          ny_low DOUBLE,
          ny_range DOUBLE,
          asia_type_code VARCHAR,
          london_type_code VARCHAR,
          pre_ny_type_code VARCHAR,

          orb_0900_high DOUBLE,
          orb_0900_low DOUBLE,
          orb_0900_size DOUBLE,
          orb_0900_break_dir VARCHAR,
          orb_0900_outcome VARCHAR,
          orb_0900_r_multiple DOUBLE,

          orb_1000_high DOUBLE,
          orb_1000_low DOUBLE,
          orb_1000_size DOUBLE,
          orb_1000_break_dir VARCHAR,
          orb_1000_outcome VARCHAR,
          orb_1000_r_multiple DOUBLE,

          orb_1100_high DOUBLE,
          orb_1100_low DOUBLE,
          orb_1100_size DOUBLE,
          orb_1100_break_dir VARCHAR,
          orb_1100_outcome VARCHAR,
          orb_1100_r_multiple DOUBLE,

          orb_1800_high DOUBLE,
          orb_1800_low DOUBLE,
          orb_1800_size DOUBLE,
          orb_1800_break_dir VARCHAR,
          orb_1800_outcome VARCHAR,
          orb_1800_r_multiple DOUBLE,

          orb_2300_high DOUBLE,
          orb_2300_low DOUBLE,
          orb_2300_size DOUBLE,
          orb_2300_break_dir VARCHAR,
          orb_2300_outcome VARCHAR,
          orb_2300_r_multiple DOUBLE,

          orb_0030_high DOUBLE,
          orb_0030_low DOUBLE,
          orb_0030_size DOUBLE,
          orb_0030_break_dir VARCHAR,
          orb_0030_outcome VARCHAR,
          orb_0030_r_multiple DOUBLE,

          rsi_at_0030 DOUBLE,
          atr_20 DOUBLE,

          PRIMARY KEY (date_local, instrument)
        );
    """)

    # Build features for date range
    current_date = start_date
    count = 0

    while current_date <= end_date:
        # Check if we have data for this date
        has_data = builder.con.execute(
            f"""
            SELECT COUNT(*)
            FROM {builder.bars_1m_table}
            WHERE symbol = ?
              AND DATE(ts_utc AT TIME ZONE 'Australia/Brisbane') = ?
            """,
            [builder.symbol, current_date],
        ).fetchone()[0]

        if has_data > 0:
            print(f"Processing {current_date}...")

            # Get session stats
            pre_asia = builder.get_pre_asia(current_date) or {}
            pre_london = builder.get_pre_london(current_date) or {}
            pre_ny = builder.get_pre_ny(current_date) or {}
            asia = builder.get_asia_session(current_date) or {}
            london = builder.get_london_session(current_date) or {}
            ny = builder.get_ny_cash_session(current_date) or {}

            # Calculate ORBs (same times as MGC)
            orb_0900 = builder.calculate_orb_1m_exec(
                _dt_local(current_date, 9, 0),
                _dt_local(current_date, 17, 0),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            orb_1000 = builder.calculate_orb_1m_exec(
                _dt_local(current_date, 10, 0),
                _dt_local(current_date, 17, 0),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            orb_1100 = builder.calculate_orb_1m_exec(
                _dt_local(current_date, 11, 0),
                _dt_local(current_date, 17, 0),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            orb_1800 = builder.calculate_orb_1m_exec(
                _dt_local(current_date, 18, 0),
                _dt_local(current_date, 23, 0),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            orb_2300 = builder.calculate_orb_1m_exec(
                _dt_local(current_date, 23, 0),
                _dt_local(current_date + timedelta(days=1), 0, 30),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            orb_0030 = builder.calculate_orb_1m_exec(
                _dt_local(current_date + timedelta(days=1), 0, 30),
                _dt_local(current_date + timedelta(days=1), 2, 0),
                rr=1.0, sl_mode=sl_mode
            ) or {}

            # Calculate RSI at 00:30
            rsi = builder.calculate_rsi_14(_dt_local(current_date + timedelta(days=1), 0, 30))

            # Insert/update
            builder.con.execute(
                f"""
                INSERT OR REPLACE INTO {builder.table_name}
                (date_local, instrument,
                 pre_asia_high, pre_asia_low, pre_asia_range,
                 pre_london_high, pre_london_low, pre_london_range,
                 pre_ny_high, pre_ny_low, pre_ny_range,
                 asia_high, asia_low, asia_range,
                 london_high, london_low, london_range,
                 ny_high, ny_low, ny_range,
                 asia_type_code, london_type_code, pre_ny_type_code,
                 orb_0900_high, orb_0900_low, orb_0900_size, orb_0900_break_dir, orb_0900_outcome, orb_0900_r_multiple, orb_0900_mae, orb_0900_mfe, orb_0900_stop_price, orb_0900_risk_ticks,
                 orb_1000_high, orb_1000_low, orb_1000_size, orb_1000_break_dir, orb_1000_outcome, orb_1000_r_multiple, orb_1000_mae, orb_1000_mfe, orb_1000_stop_price, orb_1000_risk_ticks,
                 orb_1100_high, orb_1100_low, orb_1100_size, orb_1100_break_dir, orb_1100_outcome, orb_1100_r_multiple, orb_1100_mae, orb_1100_mfe, orb_1100_stop_price, orb_1100_risk_ticks,
                 orb_1800_high, orb_1800_low, orb_1800_size, orb_1800_break_dir, orb_1800_outcome, orb_1800_r_multiple, orb_1800_mae, orb_1800_mfe, orb_1800_stop_price, orb_1800_risk_ticks,
                 orb_2300_high, orb_2300_low, orb_2300_size, orb_2300_break_dir, orb_2300_outcome, orb_2300_r_multiple, orb_2300_mae, orb_2300_mfe, orb_2300_stop_price, orb_2300_risk_ticks,
                 orb_0030_high, orb_0030_low, orb_0030_size, orb_0030_break_dir, orb_0030_outcome, orb_0030_r_multiple, orb_0030_mae, orb_0030_mfe, orb_0030_stop_price, orb_0030_risk_ticks,
                 rsi_at_0030, atr_20)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?)
                """,
                [
                    current_date, builder.symbol,
                    pre_asia.get('high'), pre_asia.get('low'), pre_asia.get('range'),
                    pre_london.get('high'), pre_london.get('low'), pre_london.get('range'),
                    pre_ny.get('high'), pre_ny.get('low'), pre_ny.get('range'),
                    asia.get('high'), asia.get('low'), asia.get('range'),
                    london.get('high'), london.get('low'), london.get('range'),
                    ny.get('high'), ny.get('low'), ny.get('range'),
                    None, None, None,  # type codes (not implemented yet)
                    orb_0900.get('high'), orb_0900.get('low'), orb_0900.get('size'),
                    orb_0900.get('break_dir'), orb_0900.get('outcome'), orb_0900.get('r_multiple'),
                    orb_0900.get('mae'), orb_0900.get('mfe'), orb_0900.get('stop_price'), orb_0900.get('risk_ticks'),
                    orb_1000.get('high'), orb_1000.get('low'), orb_1000.get('size'),
                    orb_1000.get('break_dir'), orb_1000.get('outcome'), orb_1000.get('r_multiple'),
                    orb_1000.get('mae'), orb_1000.get('mfe'), orb_1000.get('stop_price'), orb_1000.get('risk_ticks'),
                    orb_1100.get('high'), orb_1100.get('low'), orb_1100.get('size'),
                    orb_1100.get('break_dir'), orb_1100.get('outcome'), orb_1100.get('r_multiple'),
                    orb_1100.get('mae'), orb_1100.get('mfe'), orb_1100.get('stop_price'), orb_1100.get('risk_ticks'),
                    orb_1800.get('high'), orb_1800.get('low'), orb_1800.get('size'),
                    orb_1800.get('break_dir'), orb_1800.get('outcome'), orb_1800.get('r_multiple'),
                    orb_1800.get('mae'), orb_1800.get('mfe'), orb_1800.get('stop_price'), orb_1800.get('risk_ticks'),
                    orb_2300.get('high'), orb_2300.get('low'), orb_2300.get('size'),
                    orb_2300.get('break_dir'), orb_2300.get('outcome'), orb_2300.get('r_multiple'),
                    orb_2300.get('mae'), orb_2300.get('mfe'), orb_2300.get('stop_price'), orb_2300.get('risk_ticks'),
                    orb_0030.get('high'), orb_0030.get('low'), orb_0030.get('size'),
                    orb_0030.get('break_dir'), orb_0030.get('outcome'), orb_0030.get('r_multiple'),
                    orb_0030.get('mae'), orb_0030.get('mfe'), orb_0030.get('stop_price'), orb_0030.get('risk_ticks'),
                    rsi, None  # ATR not implemented yet
                ],
            )

            count += 1

        current_date += timedelta(days=1)

    print(f"\nProcessed {count} days")
    print(f"Features written to: {builder.table_name}")

    builder.con.close()


if __name__ == "__main__":
    main()
