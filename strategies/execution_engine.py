"""
CANONICAL ORB EXECUTION ENGINE
===============================

This is the ONLY place in the codebase that defines:
- Entry price logic (first close outside ORB)
- Stop placement (FULL or HALF)
- Target calculation (RR-based)
- Same-bar TP/SL resolution (conservative: both hit = LOSS)
- MAE/MFE tracking

All backtest scripts MUST call this engine instead of reimplementing execution logic.

Usage:
    from execution_engine import simulate_orb_trade

    result = simulate_orb_trade(
        con=con,
        date_local=date(2025, 1, 10),
        orb="1000",
        mode="1m",          # '1m' or '5m'
        confirm_bars=1,     # consecutive closes required
        rr=2.0,
        sl_mode="full",     # 'full' or 'half'
        buffer_ticks=0,     # entry buffer (0 = no buffer)
        entry_delay_bars=0, # wait N bars after confirmation
        max_stop_ticks=100, # filter: skip if stop > this
        asia_tp_cap_ticks=150,  # Asia ORB target cap
    )

Result format:
{
    'outcome': 'WIN' | 'LOSS' | 'NO_TRADE',
    'direction': 'UP' | 'DOWN' | None,
    'entry_ts': timestamp or None,
    'entry_price': float or None,
    'stop_price': float or None,
    'target_price': float or None,
    'stop_ticks': float or None,
    'r_multiple': float (RR on WIN, -1.0 on LOSS, 0.0 on NO_TRADE),
    'entry_delay_bars': int,
    'mae_r': float or None (max adverse excursion in R),
    'mfe_r': float or None (max favorable excursion in R),
    'execution_mode': str (logging: what mode was used),
    'execution_params': dict (logging: all parameters used),
}
"""

import duckdb
from datetime import date, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import json

SYMBOL = "MGC"
TICK_SIZE = 0.1

# ORB open times (local Brisbane time)
ORB_TIMES = {
    "0900": (9, 0),
    "1000": (10, 0),
    "1100": (11, 0),
    "1800": (18, 0),
    "2300": (23, 0),
    "0030": (0, 30),
}

@dataclass
class TradeResult:
    """Result from simulating a single ORB trade"""
    outcome: str  # 'WIN', 'LOSS', 'NO_TRADE', 'SKIPPED_NO_ORB', 'SKIPPED_NO_BARS', 'SKIPPED_NO_ENTRY', 'SKIPPED_BIG_STOP'
    direction: Optional[str]  # 'UP', 'DOWN', or None
    entry_ts: Optional[str]  # timestamp or None
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    stop_ticks: Optional[float]
    r_multiple: float  # RR on WIN, -1.0 on LOSS, 0.0 otherwise
    entry_delay_bars: int
    mae_r: Optional[float]  # max adverse excursion in R
    mfe_r: Optional[float]  # max favorable excursion in R
    execution_mode: str  # logging: e.g., "1m_confirm1_rr2.0_full"
    execution_params: dict  # logging: all parameters

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _is_asia(orb: str) -> bool:
    """Check if ORB is in Asia session"""
    return orb in ("0900", "1000", "1100")


def _orb_scan_end_local(orb: str, d: date) -> str:
    """
    EXTENDED SCAN WINDOW (CORRECTED 2026-01-16):
    All ORBs scan until next Asia open (09:00) to capture full overnight moves.

    OLD BUG: Short scan windows (85min for night ORBs) missed 30+ point moves
    that took 3-8 hours to develop. This caused massive underestimation of
    optimal RR values (e.g., 10:00 ORB optimal RR=8.0, not 3.0!).

    NEW: All scans extended to 09:00 next trading day.
    """
    # All ORBs scan until next Asia open (09:00 next day)
    # This captures overnight moves that take 3-8 hours to develop
    if orb in ("0900", "1000", "1100"):
        # Morning ORBs: scan until 09:00 NEXT day (24 hours)
        return f"{d + timedelta(days=1)} 09:00:00"
    if orb == "1800":
        # London ORB: scan through NY session until 09:00 next day
        return f"{d + timedelta(days=1)} 09:00:00"
    if orb == "2300":
        # Night futures ORB: scan until 09:00 next day (was only 85min!)
        return f"{d + timedelta(days=1)} 09:00:00"
    if orb == "0030":
        # NY cash ORB: scan until 09:00 same day (was only 85min!)
        return f"{d + timedelta(days=1)} 09:00:00"
    return f"{d + timedelta(days=1)} 09:00:00"  # Default: next Asia open


def simulate_orb_trade(
    con: duckdb.DuckDBPyConnection,
    date_local: date,
    orb: str,
    mode: str = "1m",           # '1m' or '5m'
    confirm_bars: int = 1,       # consecutive closes required
    rr: float = 1.0,
    sl_mode: str = "full",       # 'full' or 'half'
    buffer_ticks: float = 0,     # entry buffer (0 = no buffer)
    entry_delay_bars: int = 0,   # wait N bars after confirmation (NOT IMPLEMENTED YET)
    max_stop_ticks: float = 999999,  # filter: skip if stop > this
    asia_tp_cap_ticks: float = 999999,  # Asia ORB target cap
    apply_size_filter: bool = False,  # filter: skip if ORB too large vs ATR
    size_filter_threshold: float = None,  # threshold for size filter (orb_size_norm)
) -> TradeResult:
    """
    Simulate a single ORB trade using realistic execution.

    ENTRY METHOD: First `confirm_bars` consecutive closes outside ORB (not ORB edge).
    STOP PLACEMENT: 'full' = opposite ORB edge, 'half' = ORB midpoint (clamped).
    TARGET CALCULATION: entry +/- RR * risk.
    SAME-BAR TP+SL: Conservative (both hit in same bar => LOSS).

    Returns TradeResult with outcome, prices, and execution metadata.
    """
    # Log execution parameters
    execution_params = {
        'date_local': str(date_local),
        'orb': orb,
        'mode': mode,
        'confirm_bars': confirm_bars,
        'rr': rr,
        'sl_mode': sl_mode,
        'buffer_ticks': buffer_ticks,
        'entry_delay_bars': entry_delay_bars,
        'max_stop_ticks': max_stop_ticks,
        'asia_tp_cap_ticks': asia_tp_cap_ticks,
    }
    execution_mode = f"{mode}_confirm{confirm_bars}_rr{rr}_{sl_mode}"

    # Validate inputs
    assert orb in ORB_TIMES, f"Invalid ORB: {orb}"
    assert mode in ("1m", "5m"), f"Invalid mode: {mode}"
    assert sl_mode in ("full", "half"), f"Invalid sl_mode: {sl_mode}"
    assert confirm_bars >= 1, f"confirm_bars must be >= 1"
    assert rr > 0, f"RR must be > 0"

    h, m = ORB_TIMES[orb]

    # Get ORB levels from daily_features_v2
    row = con.execute(f"""
        SELECT orb_{orb}_high, orb_{orb}_low
        FROM daily_features_v2
        WHERE date_local = ?
    """, [date_local]).fetchone()

    if not row or row[0] is None or row[1] is None:
        return TradeResult(
            outcome='SKIPPED_NO_ORB',
            direction=None,
            entry_ts=None,
            entry_price=None,
            stop_price=None,
            target_price=None,
            stop_ticks=None,
            r_multiple=0.0,
            entry_delay_bars=0,
            mae_r=None,
            mfe_r=None,
            execution_mode=execution_mode,
            execution_params=execution_params
        )

    orb_high, orb_low = row
    orb_range = orb_high - orb_low
    if orb_range <= 0:
        return TradeResult(
            outcome='SKIPPED_NO_ORB',
            direction=None,
            entry_ts=None,
            entry_price=None,
            stop_price=None,
            target_price=None,
            stop_ticks=None,
            r_multiple=0.0,
            entry_delay_bars=0,
            mae_r=None,
            mfe_r=None,
            execution_mode=execution_mode,
            execution_params=execution_params
        )

    # Apply ORB size filter (NO LOOKAHEAD - ORB computed at orb close, before entry)
    if apply_size_filter and size_filter_threshold is not None:
        # Get ATR for normalization
        atr_row = con.execute(f"""
            SELECT atr_20
            FROM daily_features_v2
            WHERE date_local = ?
        """, [date_local]).fetchone()

        if atr_row and atr_row[0] is not None and atr_row[0] > 0:
            atr = atr_row[0]
            orb_size_norm = orb_range / atr

            # Reject if ORB too large (exhaustion pattern)
            if orb_size_norm > size_filter_threshold:
                return TradeResult(
                    outcome='SKIPPED_LARGE_ORB',
                    direction=None,
                    entry_ts=None,
                    entry_price=None,
                    stop_price=None,
                    target_price=None,
                    stop_ticks=None,
                    r_multiple=0.0,
                    entry_delay_bars=0,
                    mae_r=None,
                    mfe_r=None,
                    execution_mode=execution_mode,
                    execution_params=execution_params
                )

    # Start scanning AFTER the 5-min ORB completes
    start_min = m + 5
    # Handle date rollover for 00:30 ORB (belongs to D+1 local)
    start_date = date_local + timedelta(days=1) if orb == "0030" else date_local
    start_ts_local = f"{start_date} {h:02d}:{start_min:02d}:00"

    # End time for scan (limits runtime)
    end_ts_local = _orb_scan_end_local(orb, date_local)

    # Choose bar timeframe
    bars_table = "bars_1m" if mode == "1m" else "bars_5m"

    bars = con.execute(f"""
        SELECT
          (ts_utc AT TIME ZONE 'Australia/Brisbane') AS ts_local,
          high, low, close
        FROM {bars_table}
        WHERE symbol = ?
          AND (ts_utc AT TIME ZONE 'Australia/Brisbane') > CAST(? AS TIMESTAMP)
          AND (ts_utc AT TIME ZONE 'Australia/Brisbane') <= CAST(? AS TIMESTAMP)
        ORDER BY ts_local
    """, [SYMBOL, start_ts_local, end_ts_local]).fetchall()

    if not bars:
        return TradeResult(
            outcome='SKIPPED_NO_BARS',
            direction=None,
            entry_ts=None,
            entry_price=None,
            stop_price=None,
            target_price=None,
            stop_ticks=None,
            r_multiple=0.0,
            entry_delay_bars=0,
            mae_r=None,
            mfe_r=None,
            execution_mode=execution_mode,
            execution_params=execution_params
        )

    # Entry logic: N consecutive closes outside ORB
    consec = 0
    direction = None
    entry_price = None
    entry_ts = None
    entry_idx = None

    for i, (ts_local, high, low, close) in enumerate(bars):
        close = float(close)

        if close > orb_high:
            if direction != "UP":
                direction = "UP"
                consec = 0
            consec += 1
        elif close < orb_low:
            if direction != "DOWN":
                direction = "DOWN"
                consec = 0
            consec += 1
        else:
            direction = None
            consec = 0

        if consec >= confirm_bars:
            # CRITICAL: Entry at CLOSE price, not ORB edge
            entry_price = close
            entry_ts = ts_local
            entry_idx = i
            break

    if entry_price is None:
        return TradeResult(
            outcome='SKIPPED_NO_ENTRY',
            direction=direction,
            entry_ts=None,
            entry_price=None,
            stop_price=None,
            target_price=None,
            stop_ticks=None,
            r_multiple=0.0,
            entry_delay_bars=0,
            mae_r=None,
            mfe_r=None,
            execution_mode=execution_mode,
            execution_params=execution_params
        )

    # VALIDATE: Entry must not be at ORB edge (GUARDRAIL)
    assert entry_price != orb_high, "FATAL: Entry at ORB high (should be at close)"
    assert entry_price != orb_low, "FATAL: Entry at ORB low (should be at close)"

    # Apply entry buffer (if specified)
    if buffer_ticks > 0:
        buffer_price = buffer_ticks * TICK_SIZE
        if direction == "UP":
            entry_price += buffer_price
        else:
            entry_price -= buffer_price

    # Stop placement
    if sl_mode == "half":
        orb_mid = (orb_high + orb_low) / 2.0
        if direction == "UP":
            stop_price = max(orb_low, orb_mid)  # clamped to ORB low
        else:
            stop_price = min(orb_high, orb_mid)  # clamped to ORB high
    else:  # full
        stop_price = orb_low if direction == "UP" else orb_high

    stop_ticks = abs(entry_price - stop_price) / TICK_SIZE

    # Filter: max stop
    if stop_ticks > max_stop_ticks:
        return TradeResult(
            outcome='SKIPPED_BIG_STOP',
            direction=direction,
            entry_ts=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=None,
            stop_ticks=stop_ticks,
            r_multiple=0.0,
            entry_delay_bars=entry_idx + 1,
            mae_r=None,
            mfe_r=None,
            execution_mode=execution_mode,
            execution_params=execution_params
        )

    # Target = entry +/- RR * risk
    risk = abs(entry_price - stop_price)
    target_price = entry_price + rr * risk if direction == "UP" else entry_price - rr * risk

    # Asia TP cap (if applicable)
    if _is_asia(orb) and asia_tp_cap_ticks < 999999:
        cap = asia_tp_cap_ticks * TICK_SIZE
        if direction == "UP":
            target_price = min(target_price, entry_price + cap)
        else:
            target_price = max(target_price, entry_price - cap)

    # Outcome scan (HIGH/LOW-based, conservative: if both hit same bar => LOSS)
    outcome = "NO_TRADE"
    r_mult = 0.0
    max_fav_ticks = 0.0
    max_adv_ticks = 0.0

    for _, high, low, close in bars[entry_idx + 1:]:
        high = float(high)
        low = float(low)

        if direction == "UP":
            max_fav_ticks = max(max_fav_ticks, (high - entry_price) / TICK_SIZE)
            max_adv_ticks = max(max_adv_ticks, (entry_price - low) / TICK_SIZE)

            hit_stop = low <= stop_price
            hit_target = high >= target_price

            # Conservative: both hit in same bar => LOSS
            if hit_stop and hit_target:
                outcome = "LOSS"
                r_mult = -1.0
                break
            if hit_target:
                outcome = "WIN"
                r_mult = float(rr)
                break
            if hit_stop:
                outcome = "LOSS"
                r_mult = -1.0
                break
        else:  # DOWN
            max_fav_ticks = max(max_fav_ticks, (entry_price - low) / TICK_SIZE)
            max_adv_ticks = max(max_adv_ticks, (high - entry_price) / TICK_SIZE)

            hit_stop = high >= stop_price
            hit_target = low <= target_price

            # Conservative: both hit in same bar => LOSS
            if hit_stop and hit_target:
                outcome = "LOSS"
                r_mult = -1.0
                break
            if hit_target:
                outcome = "WIN"
                r_mult = float(rr)
                break
            if hit_stop:
                outcome = "LOSS"
                r_mult = -1.0
                break

    entry_delay_bars_val = entry_idx + 1  # bars after ORB end until entry trigger
    mae_r = (max_adv_ticks / stop_ticks) if stop_ticks and stop_ticks > 0 else None
    mfe_r = (max_fav_ticks / stop_ticks) if stop_ticks and stop_ticks > 0 else None

    return TradeResult(
        outcome=outcome,
        direction=direction,
        entry_ts=str(entry_ts) if entry_ts else None,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        stop_ticks=stop_ticks,
        r_multiple=r_mult,
        entry_delay_bars=entry_delay_bars_val,
        mae_r=mae_r,
        mfe_r=mfe_r,
        execution_mode=execution_mode,
        execution_params=execution_params
    )


# Logging helper
def log_execution(result: TradeResult, verbose: bool = False):
    """Log execution result with mode and parameters"""
    if verbose:
        print(f"[{result.execution_mode}] {result.execution_params['date_local']} {result.execution_params['orb']}: "
              f"{result.outcome} | {result.direction} | R={result.r_multiple:+.2f}")
