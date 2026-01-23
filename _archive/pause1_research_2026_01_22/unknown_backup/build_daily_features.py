from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import duckdb

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
DB_PATH = Path("gold.db")
INSTRUMENT = "MGC"  # Micro Gold Futures
TZ_LOCAL = ZoneInfo("Australia/Brisbane")  # UTC+10 (no DST)

# Session blocks (UTC+10)
ASIA_START = time(9, 0)
ASIA_END = time(17, 0)

LONDON_START = time(18, 0)
LONDON_END = time(23, 0)

NY_START = time(23, 0)
NY_END = time(2, 0)  # crosses midnight

# Travel windows (UTC+10)
PRE_NY_START = time(18, 0)
PRE_NY_END = time(23, 0)

PRE_ORB_START = time(23, 0)
PRE_ORB_END = time(0, 30)

# NYSE ORB (UTC+10)
ORB_START = time(0, 30)
ORB_END = time(0, 35)
ORB_BREAK_LOOKAHEAD_END = time(2, 0)

RSI_LEN = 14
ATR_LEN = 20


# ─────────────────────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────────────────────
@dataclass
class Bar1m:
    ts_utc: datetime
    o: float
    h: float
    l: float
    c: float
    v: int


@dataclass
class Bar5m:
    ts_utc: datetime  # bucket start (UTC)
    o: float
    h: float
    l: float
    c: float
    v: int


# ─────────────────────────────────────────────────────────────
# TIME HELPERS
# ─────────────────────────────────────────────────────────────
def local_window_to_utc(
    for_local_date: date, start_local: time, end_local: time
) -> Tuple[datetime, datetime]:
    start_dt_local = datetime.combine(for_local_date, start_local, tzinfo=TZ_LOCAL)
    end_dt_local = datetime.combine(for_local_date, end_local, tzinfo=TZ_LOCAL)
    if end_dt_local <= start_dt_local:
        end_dt_local += timedelta(days=1)
    return start_dt_local.astimezone(timezone.utc), end_dt_local.astimezone(timezone.utc)


# ─────────────────────────────────────────────────────────────
# DATA FETCH
# Assumes you have bars_1m(ts_utc, symbol, open, high, low, close, volume)
# ─────────────────────────────────────────────────────────────
def fetch_bars_1m(
    con: duckdb.DuckDBPyConnection, start_utc: datetime, end_utc: datetime
) -> List[Bar1m]:
    rows = con.execute(
        """
        SELECT ts_utc, open, high, low, close, volume
        FROM bars_1m
        WHERE symbol = ?
          AND ts_utc >= ?
          AND ts_utc < ?
        ORDER BY ts_utc ASC
        """,
        [INSTRUMENT, start_utc, end_utc],
    ).fetchall()

    out: List[Bar1m] = []
    for ts_utc, o, h, l, c, v in rows:
        if ts_utc.tzinfo is None:
            ts_utc = ts_utc.replace(tzinfo=timezone.utc)
        out.append(Bar1m(ts_utc=ts_utc, o=float(o), h=float(h), l=float(l), c=float(c), v=int(v)))
    return out


def fetch_bars_5m(
    con: duckdb.DuckDBPyConnection, start_utc: datetime, end_utc: datetime
) -> List[Bar5m]:
    # Aggregate 1m -> 5m buckets in SQL.
    # bucket_start = epoch_seconds - (epoch_seconds % 300)
    rows = con.execute(
        """
        WITH base AS (
          SELECT
            to_timestamp(floor(extract(epoch from ts_utc)/300)*300) AS bucket_utc,
            ts_utc,
            open, high, low, close, volume
          FROM bars_1m
          WHERE symbol = ?
            AND ts_utc >= ?
            AND ts_utc < ?
        ),
        agg AS (
          SELECT
            bucket_utc AS ts_utc,
            -- open = first open in bucket
            arg_min(open, ts_utc) AS open,
            max(high) AS high,
            min(low) AS low,
            -- close = last close in bucket
            arg_max(close, ts_utc) AS close,
            sum(volume) AS volume
          FROM base
          GROUP BY bucket_utc
        )
        SELECT ts_utc, open, high, low, close, volume
        FROM agg
        ORDER BY ts_utc ASC
        """,
        [INSTRUMENT, start_utc, end_utc],
    ).fetchall()

    out: List[Bar5m] = []
    for ts_utc, o, h, l, c, v in rows:
        if ts_utc.tzinfo is None:
            ts_utc = ts_utc.replace(tzinfo=timezone.utc)
        out.append(Bar5m(ts_utc=ts_utc, o=float(o), h=float(h), l=float(l), c=float(c), v=int(v)))
    return out


# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────
def high_low_1m(bars: List[Bar1m]) -> Tuple[Optional[float], Optional[float]]:
    if not bars:
        return None, None
    return max(b.h for b in bars), min(b.l for b in bars)


def travel_range_1m(bars: List[Bar1m]) -> Optional[float]:
    hi, lo = high_low_1m(bars)
    if hi is None or lo is None:
        return None
    return float(hi - lo)


def orb_break_dir_from_5m_closes(orb_hi: float, orb_lo: float, bars_5m_after: List[Bar5m]) -> str:
    # Rule: first FULL 5m CLOSE outside the box
    for b in bars_5m_after:
        if b.c > orb_hi:
            return "UP"
        if b.c < orb_lo:
            return "DOWN"
    return "NONE"


def rsi_wilder(closes: List[float], length: int = 14) -> List[Optional[float]]:
    """
    Returns RSI values aligned to closes (same length), using Wilder's smoothing.
    RSI is None until enough history exists.
    """
    n = len(closes)
    if n == 0:
        return []
    out: List[Optional[float]] = [None] * n
    if n < length + 1:
        return out

    gains = []
    losses = []
    for i in range(1, length + 1):
        ch = closes[i] - closes[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))

    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length

    def calc_rsi(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    out[length] = calc_rsi(avg_gain, avg_loss)

    for i in range(length + 1, n):
        ch = closes[i] - closes[i - 1]
        gain = max(ch, 0.0)
        loss = max(-ch, 0.0)
        avg_gain = (avg_gain * (length - 1) + gain) / length
        avg_loss = (avg_loss * (length - 1) + loss) / length
        out[i] = calc_rsi(avg_gain, avg_loss)

    return out


def atr_wilder(highs: List[float], lows: List[float], closes: List[float], length: int = 20) -> List[Optional[float]]:
    """
    Returns ATR values using Wilder's smoothing.
    ATR is None until enough history exists.
    """
    n = len(closes)
    if n == 0:
        return []
    if n != len(highs) or n != len(lows):
        raise ValueError("highs, lows, closes must have same length")

    out: List[Optional[float]] = [None] * n
    if n < length + 1:
        return out

    # True Range for first `length` bars
    trs = []
    for i in range(1, length + 1):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)

    atr = sum(trs) / length
    out[length] = atr

    # Wilder's smoothing
    for i in range(length + 1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        atr = (atr * (length - 1) + tr) / length
        out[i] = atr

    return out


def classify_asia_type(asia_range: Optional[float], atr_20: Optional[float]) -> str:
    """TIGHT < 0.3, EXPANDED > 0.8, else NORMAL"""
    if asia_range is None:
        return "NO_DATA"
    if atr_20 is None or atr_20 == 0.0:
        return "NO_DATA"
    ratio = asia_range / atr_20
    if ratio < 0.3:
        return "TIGHT"
    elif ratio > 0.8:
        return "EXPANDED"
    else:
        return "NORMAL"


def classify_london_type(
    london_high: Optional[float],
    london_low: Optional[float],
    asia_high: Optional[float],
    asia_low: Optional[float],
) -> str:
    """EXPANSION first, then SWEEP_HIGH, then SWEEP_LOW, else CONSOLIDATION"""
    if london_high is None or london_low is None:
        return "NO_DATA"
    if asia_high is None or asia_low is None:
        return "NO_DATA"

    took_high = london_high > asia_high
    took_low = london_low < asia_low

    if took_high and took_low:
        return "EXPANSION"
    elif took_high:
        return "SWEEP_HIGH"
    elif took_low:
        return "SWEEP_LOW"
    else:
        return "CONSOLIDATION"


def classify_ny_type(
    ny_high: Optional[float],
    ny_low: Optional[float],
    london_high: Optional[float],
    london_low: Optional[float],
) -> str:
    """EXPANSION first, then SWEEP_HIGH, then SWEEP_LOW, else CONSOLIDATION"""
    if ny_high is None or ny_low is None:
        return "NO_DATA"
    if london_high is None or london_low is None:
        return "NO_DATA"

    took_high = ny_high > london_high
    took_low = ny_low < london_low

    if took_high and took_low:
        return "EXPANSION"
    elif took_high:
        return "SWEEP_HIGH"
    elif took_low:
        return "SWEEP_LOW"
    else:
        return "CONSOLIDATION"


def compute_orb_outcome(
    orb_high: Optional[float],
    orb_low: Optional[float],
    orb_break_dir: str,
    bars_5m_after: List[Bar5m],
) -> Dict[str, Optional[object]]:
    """
    Compute ORB outcome: WIN/LOSS/NO_TRADE, R-multiple, MAE, MFE

    Rules:
    - If no break (orb_break_dir == "NONE"), outcome = NO_TRADE
    - If break UP: entry = orb_high, stop = orb_low, target = orb_high + (orb_high - orb_low)
    - If break DOWN: entry = orb_low, stop = orb_high, target = orb_low - (orb_high - orb_low)
    - Track MAE (Maximum Adverse Excursion) and MFE (Maximum Favorable Excursion)
    - WIN if target hit before stop
    - LOSS if stop hit before target
    """
    if orb_high is None or orb_low is None or orb_break_dir == "NONE":
        return {
            "outcome": "NO_TRADE",
            "r_multiple": None,
            "mae": None,
            "mfe": None,
        }

    orb_size = orb_high - orb_low

    if orb_break_dir == "UP":
        entry = orb_high
        stop = orb_low
        target = orb_high + orb_size

        # Track MAE (worst drawdown) and MFE (best profit)
        mae = 0.0  # adverse = price going down
        mfe = 0.0  # favorable = price going up
        outcome = "NO_TRADE"  # default if neither hit

        for bar in bars_5m_after:
            # Check if stop hit (low touches stop)
            if bar.l <= stop:
                outcome = "LOSS"
                break
            # Check if target hit (high touches target)
            if bar.h >= target:
                outcome = "WIN"
                break

            # Track excursions (in ticks, 1 tick = 0.1 for MGC)
            mae = min(mae, bar.l - entry)  # most negative = worst drawdown
            mfe = max(mfe, bar.h - entry)  # most positive = best gain

        # R-multiple: profit/risk
        if outcome == "WIN":
            r_multiple = 1.0  # hit 1R target
        elif outcome == "LOSS":
            r_multiple = -1.0  # hit stop
        else:
            r_multiple = None  # no exit

    elif orb_break_dir == "DOWN":
        entry = orb_low
        stop = orb_high
        target = orb_low - orb_size

        mae = 0.0  # adverse = price going up
        mfe = 0.0  # favorable = price going down
        outcome = "NO_TRADE"

        for bar in bars_5m_after:
            # Check if stop hit (high touches stop)
            if bar.h >= stop:
                outcome = "LOSS"
                break
            # Check if target hit (low touches target)
            if bar.l <= target:
                outcome = "WIN"
                break

            # Track excursions
            mae = max(mae, bar.h - entry)  # most positive = worst drawdown
            mfe = min(mfe, bar.l - entry)  # most negative = best gain

        if outcome == "WIN":
            r_multiple = 1.0
        elif outcome == "LOSS":
            r_multiple = -1.0
        else:
            r_multiple = None

    else:
        return {
            "outcome": "NO_TRADE",
            "r_multiple": None,
            "mae": None,
            "mfe": None,
        }

    return {
        "outcome": outcome,
        "r_multiple": r_multiple,
        "mae": float(mae) if mae != 0.0 else None,
        "mfe": float(mfe) if mfe != 0.0 else None,
    }


def compute_orb_generic(
    con: duckdb.DuckDBPyConnection,
    d_local: date,
    orb_start_time: time,
    orb_duration_minutes: int = 5,
    break_lookahead_hours: int = 2,
    compute_rsi: bool = False,
) -> Dict[str, Optional[object]]:
    """
    Generic ORB computation for any start time.
    Returns dict with keys: orb_high, orb_low, orb_size, orb_break_dir, (rsi_at_orb if compute_rsi=True)
    """
    # Calculate end time
    orb_start_dt = datetime.combine(d_local, orb_start_time, tzinfo=TZ_LOCAL)
    orb_end_dt = orb_start_dt + timedelta(minutes=orb_duration_minutes)
    break_end_dt = orb_end_dt + timedelta(hours=break_lookahead_hours)

    orb_start_utc = orb_start_dt.astimezone(timezone.utc)
    orb_end_utc = orb_end_dt.astimezone(timezone.utc)
    break_end_utc = break_end_dt.astimezone(timezone.utc)

    # ORB box from 1m data
    orb_1m = fetch_bars_1m(con, orb_start_utc, orb_end_utc)
    if not orb_1m:
        result = {
            "orb_high": None,
            "orb_low": None,
            "orb_size": None,
            "orb_break_dir": None,
            "outcome": None,
            "r_multiple": None,
            "mae": None,
            "mfe": None,
        }
        if compute_rsi:
            result["rsi_at_orb"] = None
        return result

    orb_hi, orb_lo = high_low_1m(orb_1m)
    if orb_hi is None or orb_lo is None:
        result = {
            "orb_high": None,
            "orb_low": None,
            "orb_size": None,
            "orb_break_dir": None,
            "outcome": None,
            "r_multiple": None,
            "mae": None,
            "mfe": None,
        }
        if compute_rsi:
            result["rsi_at_orb"] = None
        return result

    # Break direction: first 5m CLOSE outside box
    after_5m = fetch_bars_5m(con, orb_end_utc, break_end_utc)
    break_dir = orb_break_dir_from_5m_closes(float(orb_hi), float(orb_lo), after_5m)

    # Compute outcome (WIN/LOSS/NO_TRADE, R-multiple, MAE, MFE)
    outcome_data = compute_orb_outcome(float(orb_hi), float(orb_lo), break_dir, after_5m)

    result = {
        "orb_high": float(orb_hi),
        "orb_low": float(orb_lo),
        "orb_size": float(orb_hi - orb_lo),
        "orb_break_dir": break_dir,
        "outcome": outcome_data["outcome"],
        "r_multiple": outcome_data["r_multiple"],
        "mae": outcome_data["mae"],
        "mfe": outcome_data["mfe"],
    }

    # RSI at ORB (optional)
    if compute_rsi:
        rsi_lookback_start = orb_start_utc - timedelta(hours=24)
        bars_5m = fetch_bars_5m(con, rsi_lookback_start, orb_end_utc)
        rsi_val: Optional[float] = None
        if bars_5m:
            closes = [b.c for b in bars_5m]
            rsis = rsi_wilder(closes, RSI_LEN)
            # Find the 5m bucket that starts exactly at orb_start_utc
            idx = None
            for i, b in enumerate(bars_5m):
                if b.ts_utc == orb_start_utc:
                    idx = i
                    break
            if idx is not None:
                rsi_val = rsis[idx]
        result["rsi_at_orb"] = (float(rsi_val) if rsi_val is not None else None)

    return result


def compute_orb_0030(
    con: duckdb.DuckDBPyConnection,
    d_local: date,
) -> Dict[str, Optional[object]]:
    """Legacy wrapper - computes 00:30 ORB with RSI"""
    result = compute_orb_generic(con, d_local, time(0, 30), orb_duration_minutes=5, break_lookahead_hours=2, compute_rsi=True)
    # Rename keys for backward compatibility
    return {
        "orb_high": result["orb_high"],
        "orb_low": result["orb_low"],
        "orb_first5m": result["orb_size"],
        "orb_break_dir": result["orb_break_dir"],
        "rsi_at_orb": result.get("rsi_at_orb"),
    }


# ─────────────────────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────────────────────
def ensure_daily_features_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_features (
          date_local DATE,
          instrument TEXT,

          -- Session high/low
          asia_high DOUBLE,
          asia_low DOUBLE,
          asia_range DOUBLE,
          london_high DOUBLE,
          london_low DOUBLE,
          ny_high DOUBLE,
          ny_low DOUBLE,

          -- Pre-move travel
          pre_ny_travel DOUBLE,
          pre_orb_travel DOUBLE,

          -- ATR and session types
          atr_20 DOUBLE,
          asia_type TEXT,
          london_type TEXT,
          ny_type TEXT,

          -- ORB 09:00
          orb_0900_high DOUBLE,
          orb_0900_low DOUBLE,
          orb_0900_size DOUBLE,
          orb_0900_break_dir TEXT,
          orb_0900_outcome TEXT,
          orb_0900_r_multiple DOUBLE,
          orb_0900_mae DOUBLE,
          orb_0900_mfe DOUBLE,

          -- ORB 10:00
          orb_1000_high DOUBLE,
          orb_1000_low DOUBLE,
          orb_1000_size DOUBLE,
          orb_1000_break_dir TEXT,
          orb_1000_outcome TEXT,
          orb_1000_r_multiple DOUBLE,
          orb_1000_mae DOUBLE,
          orb_1000_mfe DOUBLE,

          -- ORB 11:00
          orb_1100_high DOUBLE,
          orb_1100_low DOUBLE,
          orb_1100_size DOUBLE,
          orb_1100_break_dir TEXT,
          orb_1100_outcome TEXT,
          orb_1100_r_multiple DOUBLE,
          orb_1100_mae DOUBLE,
          orb_1100_mfe DOUBLE,

          -- ORB 18:00
          orb_1800_high DOUBLE,
          orb_1800_low DOUBLE,
          orb_1800_size DOUBLE,
          orb_1800_break_dir TEXT,
          orb_1800_outcome TEXT,
          orb_1800_r_multiple DOUBLE,
          orb_1800_mae DOUBLE,
          orb_1800_mfe DOUBLE,

          -- ORB 23:00
          orb_2300_high DOUBLE,
          orb_2300_low DOUBLE,
          orb_2300_size DOUBLE,
          orb_2300_break_dir TEXT,
          orb_2300_outcome TEXT,
          orb_2300_r_multiple DOUBLE,
          orb_2300_mae DOUBLE,
          orb_2300_mfe DOUBLE,

          -- ORB 00:30 (with RSI)
          orb_0030_high DOUBLE,
          orb_0030_low DOUBLE,
          orb_0030_size DOUBLE,
          orb_0030_break_dir TEXT,
          orb_0030_outcome TEXT,
          orb_0030_r_multiple DOUBLE,
          orb_0030_mae DOUBLE,
          orb_0030_mfe DOUBLE,
          rsi_at_orb DOUBLE,

          PRIMARY KEY (date_local, instrument)
        )
        """
    )


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main(date_local_str: str) -> None:
    d = date.fromisoformat(date_local_str)

    con = duckdb.connect(str(DB_PATH))
    try:
        ensure_daily_features_table(con)

        # Session windows (UTC+10 local -> UTC)
        asia_start_utc, asia_end_utc = local_window_to_utc(d, ASIA_START, ASIA_END)
        london_start_utc, london_end_utc = local_window_to_utc(d, LONDON_START, LONDON_END)
        ny_start_utc, ny_end_utc = local_window_to_utc(d, NY_START, NY_END)

        pre_ny_start_utc, pre_ny_end_utc = local_window_to_utc(d, PRE_NY_START, PRE_NY_END)
        pre_orb_start_utc, pre_orb_end_utc = local_window_to_utc(d, PRE_ORB_START, PRE_ORB_END)

        # Fetch 1m for high/low + travel
        asia_1m = fetch_bars_1m(con, asia_start_utc, asia_end_utc)
        london_1m = fetch_bars_1m(con, london_start_utc, london_end_utc)
        ny_1m = fetch_bars_1m(con, ny_start_utc, ny_end_utc)

        asia_hi, asia_lo = high_low_1m(asia_1m)
        lon_hi, lon_lo = high_low_1m(london_1m)
        ny_hi, ny_lo = high_low_1m(ny_1m)

        asia_range = (float(asia_hi - asia_lo) if (asia_hi is not None and asia_lo is not None) else None)

        pre_ny_travel = travel_range_1m(fetch_bars_1m(con, pre_ny_start_utc, pre_ny_end_utc))
        pre_orb_travel = travel_range_1m(fetch_bars_1m(con, pre_orb_start_utc, pre_orb_end_utc))

        # Compute ATR_20 (using 5m bars from trading day start)
        # Fetch 24 hours of 5m bars before Asia start for ATR calculation
        atr_lookback_start = asia_start_utc - timedelta(hours=24)
        atr_bars_5m = fetch_bars_5m(con, atr_lookback_start, asia_start_utc)
        atr_20: Optional[float] = None
        if len(atr_bars_5m) >= ATR_LEN + 1:
            highs = [b.h for b in atr_bars_5m]
            lows = [b.l for b in atr_bars_5m]
            closes = [b.c for b in atr_bars_5m]
            atr_values = atr_wilder(highs, lows, closes, ATR_LEN)
            # Use the last ATR value (at Asia start)
            atr_20 = atr_values[-1]

        # Classify session types
        asia_type = classify_asia_type(asia_range, atr_20)
        london_type = classify_london_type(lon_hi, lon_lo, asia_hi, asia_lo)
        ny_type = classify_ny_type(ny_hi, ny_lo, lon_hi, lon_lo)

        # Compute all 6 ORBs
        orb_0900 = compute_orb_generic(con, d, time(9, 0))
        orb_1000 = compute_orb_generic(con, d, time(10, 0))
        orb_1100 = compute_orb_generic(con, d, time(11, 0))
        orb_1800 = compute_orb_generic(con, d, time(18, 0))
        orb_2300 = compute_orb_generic(con, d, time(23, 0))
        orb_0030 = compute_orb_generic(con, d, time(0, 30), compute_rsi=True)  # Keep RSI for 00:30

        if orb_0030["orb_high"] is None or orb_0030["orb_low"] is None:
            print(f"SKIP_ORB_0030: {d.isoformat()} missing 00:30 ORB 1m bars (writing NULL for 00:30 orb fields).")

        # Upsert
        con.execute(
            """
            INSERT INTO daily_features AS t
            (date_local, instrument,
             asia_high, asia_low, asia_range,
             london_high, london_low,
             ny_high, ny_low,
             pre_ny_travel, pre_orb_travel,
             atr_20, asia_type, london_type, ny_type,
             orb_0900_high, orb_0900_low, orb_0900_size, orb_0900_break_dir,
             orb_0900_outcome, orb_0900_r_multiple, orb_0900_mae, orb_0900_mfe,
             orb_1000_high, orb_1000_low, orb_1000_size, orb_1000_break_dir,
             orb_1000_outcome, orb_1000_r_multiple, orb_1000_mae, orb_1000_mfe,
             orb_1100_high, orb_1100_low, orb_1100_size, orb_1100_break_dir,
             orb_1100_outcome, orb_1100_r_multiple, orb_1100_mae, orb_1100_mfe,
             orb_1800_high, orb_1800_low, orb_1800_size, orb_1800_break_dir,
             orb_1800_outcome, orb_1800_r_multiple, orb_1800_mae, orb_1800_mfe,
             orb_2300_high, orb_2300_low, orb_2300_size, orb_2300_break_dir,
             orb_2300_outcome, orb_2300_r_multiple, orb_2300_mae, orb_2300_mfe,
             orb_0030_high, orb_0030_low, orb_0030_size, orb_0030_break_dir,
             orb_0030_outcome, orb_0030_r_multiple, orb_0030_mae, orb_0030_mfe,
             rsi_at_orb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (date_local, instrument) DO UPDATE SET
              asia_high=excluded.asia_high,
              asia_low=excluded.asia_low,
              asia_range=excluded.asia_range,
              london_high=excluded.london_high,
              london_low=excluded.london_low,
              ny_high=excluded.ny_high,
              ny_low=excluded.ny_low,
              pre_ny_travel=excluded.pre_ny_travel,
              pre_orb_travel=excluded.pre_orb_travel,
              atr_20=excluded.atr_20,
              asia_type=excluded.asia_type,
              london_type=excluded.london_type,
              ny_type=excluded.ny_type,
              orb_0900_high=excluded.orb_0900_high,
              orb_0900_low=excluded.orb_0900_low,
              orb_0900_size=excluded.orb_0900_size,
              orb_0900_break_dir=excluded.orb_0900_break_dir,
              orb_0900_outcome=excluded.orb_0900_outcome,
              orb_0900_r_multiple=excluded.orb_0900_r_multiple,
              orb_0900_mae=excluded.orb_0900_mae,
              orb_0900_mfe=excluded.orb_0900_mfe,
              orb_1000_high=excluded.orb_1000_high,
              orb_1000_low=excluded.orb_1000_low,
              orb_1000_size=excluded.orb_1000_size,
              orb_1000_break_dir=excluded.orb_1000_break_dir,
              orb_1000_outcome=excluded.orb_1000_outcome,
              orb_1000_r_multiple=excluded.orb_1000_r_multiple,
              orb_1000_mae=excluded.orb_1000_mae,
              orb_1000_mfe=excluded.orb_1000_mfe,
              orb_1100_high=excluded.orb_1100_high,
              orb_1100_low=excluded.orb_1100_low,
              orb_1100_size=excluded.orb_1100_size,
              orb_1100_break_dir=excluded.orb_1100_break_dir,
              orb_1100_outcome=excluded.orb_1100_outcome,
              orb_1100_r_multiple=excluded.orb_1100_r_multiple,
              orb_1100_mae=excluded.orb_1100_mae,
              orb_1100_mfe=excluded.orb_1100_mfe,
              orb_1800_high=excluded.orb_1800_high,
              orb_1800_low=excluded.orb_1800_low,
              orb_1800_size=excluded.orb_1800_size,
              orb_1800_break_dir=excluded.orb_1800_break_dir,
              orb_1800_outcome=excluded.orb_1800_outcome,
              orb_1800_r_multiple=excluded.orb_1800_r_multiple,
              orb_1800_mae=excluded.orb_1800_mae,
              orb_1800_mfe=excluded.orb_1800_mfe,
              orb_2300_high=excluded.orb_2300_high,
              orb_2300_low=excluded.orb_2300_low,
              orb_2300_size=excluded.orb_2300_size,
              orb_2300_break_dir=excluded.orb_2300_break_dir,
              orb_2300_outcome=excluded.orb_2300_outcome,
              orb_2300_r_multiple=excluded.orb_2300_r_multiple,
              orb_2300_mae=excluded.orb_2300_mae,
              orb_2300_mfe=excluded.orb_2300_mfe,
              orb_0030_high=excluded.orb_0030_high,
              orb_0030_low=excluded.orb_0030_low,
              orb_0030_size=excluded.orb_0030_size,
              orb_0030_break_dir=excluded.orb_0030_break_dir,
              orb_0030_outcome=excluded.orb_0030_outcome,
              orb_0030_r_multiple=excluded.orb_0030_r_multiple,
              orb_0030_mae=excluded.orb_0030_mae,
              orb_0030_mfe=excluded.orb_0030_mfe,
              rsi_at_orb=excluded.rsi_at_orb
            """,
            [
                d,
                INSTRUMENT,
                asia_hi, asia_lo, asia_range,
                lon_hi, lon_lo,
                ny_hi, ny_lo,
                pre_ny_travel, pre_orb_travel,
                atr_20, asia_type, london_type, ny_type,
                # ORB 0900
                orb_0900["orb_high"], orb_0900["orb_low"], orb_0900["orb_size"], orb_0900["orb_break_dir"],
                orb_0900["outcome"], orb_0900["r_multiple"], orb_0900["mae"], orb_0900["mfe"],
                # ORB 1000
                orb_1000["orb_high"], orb_1000["orb_low"], orb_1000["orb_size"], orb_1000["orb_break_dir"],
                orb_1000["outcome"], orb_1000["r_multiple"], orb_1000["mae"], orb_1000["mfe"],
                # ORB 1100
                orb_1100["orb_high"], orb_1100["orb_low"], orb_1100["orb_size"], orb_1100["orb_break_dir"],
                orb_1100["outcome"], orb_1100["r_multiple"], orb_1100["mae"], orb_1100["mfe"],
                # ORB 1800
                orb_1800["orb_high"], orb_1800["orb_low"], orb_1800["orb_size"], orb_1800["orb_break_dir"],
                orb_1800["outcome"], orb_1800["r_multiple"], orb_1800["mae"], orb_1800["mfe"],
                # ORB 2300
                orb_2300["orb_high"], orb_2300["orb_low"], orb_2300["orb_size"], orb_2300["orb_break_dir"],
                orb_2300["outcome"], orb_2300["r_multiple"], orb_2300["mae"], orb_2300["mfe"],
                # ORB 0030
                orb_0030["orb_high"], orb_0030["orb_low"], orb_0030["orb_size"], orb_0030["orb_break_dir"],
                orb_0030["outcome"], orb_0030["r_multiple"], orb_0030["mae"], orb_0030["mfe"],
                # RSI
                orb_0030.get("rsi_at_orb"),
            ],
        )

        print("OK: daily_features upserted for", d.isoformat(), INSTRUMENT)
        print("  ATR_20:", atr_20)
        print("  Asia H/L:", asia_hi, asia_lo, "range:", asia_range, f"type: {asia_type}")
        print("  London H/L:", lon_hi, lon_lo, f"type: {london_type}")
        print("  NY H/L:", ny_hi, ny_lo, f"type: {ny_type}")
        print("  Pre-NY travel:", pre_ny_travel, "Pre-ORB travel:", pre_orb_travel)
        print("  ORB 09:00:", f"H/L: {orb_0900['orb_high']}/{orb_0900['orb_low']}", f"size: {orb_0900['orb_size']}",
              f"dir: {orb_0900['orb_break_dir']}", f"outcome: {orb_0900['outcome']}", f"R: {orb_0900['r_multiple']}")
        print("  ORB 10:00:", f"H/L: {orb_1000['orb_high']}/{orb_1000['orb_low']}", f"size: {orb_1000['orb_size']}",
              f"dir: {orb_1000['orb_break_dir']}", f"outcome: {orb_1000['outcome']}", f"R: {orb_1000['r_multiple']}")
        print("  ORB 11:00:", f"H/L: {orb_1100['orb_high']}/{orb_1100['orb_low']}", f"size: {orb_1100['orb_size']}",
              f"dir: {orb_1100['orb_break_dir']}", f"outcome: {orb_1100['outcome']}", f"R: {orb_1100['r_multiple']}")
        print("  ORB 18:00:", f"H/L: {orb_1800['orb_high']}/{orb_1800['orb_low']}", f"size: {orb_1800['orb_size']}",
              f"dir: {orb_1800['orb_break_dir']}", f"outcome: {orb_1800['outcome']}", f"R: {orb_1800['r_multiple']}")
        print("  ORB 23:00:", f"H/L: {orb_2300['orb_high']}/{orb_2300['orb_low']}", f"size: {orb_2300['orb_size']}",
              f"dir: {orb_2300['orb_break_dir']}", f"outcome: {orb_2300['outcome']}", f"R: {orb_2300['r_multiple']}")
        print("  ORB 00:30:", f"H/L: {orb_0030['orb_high']}/{orb_0030['orb_low']}", f"size: {orb_0030['orb_size']}",
              f"dir: {orb_0030['orb_break_dir']}", f"outcome: {orb_0030['outcome']}", f"R: {orb_0030['r_multiple']}")
        print("  RSI@ORB(00:30):", orb_0030.get("rsi_at_orb"))

    finally:
        con.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python build_daily_features.py YYYY-MM-DD  (local Brisbane date, UTC+10)")
    main(sys.argv[1])
