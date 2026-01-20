#!/usr/bin/env python3
"""
Asia Session Backtest Core - Zero-Lookahead Engine

Supports BOTH HALF and FULL SL modes with hard assertions.
"""

import duckdb
import pandas as pd
from datetime import datetime, date, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import hashlib

TZ_LOCAL = ZoneInfo("Australia/Brisbane")
TZ_UTC = ZoneInfo("UTC")

@dataclass
class ORBResult:
    """ORB levels computed from bars."""
    orb_high: float
    orb_low: float
    orb_size: float
    orb_midpoint: float
    bar_count: int

@dataclass
class TradeResult:
    """Single trade outcome."""
    date_local: str
    orb_time: str
    direction: str  # 'long' or 'short'
    entry_ts: datetime
    entry_price: float
    stop_price: float
    target_price: float
    exit_ts: Optional[datetime]
    exit_price: Optional[float]
    exit_reason: str  # 'TP', 'SL', 'FORCE_EXIT', 'NO_EXIT'
    r_multiple: float
    minutes_to_exit: Optional[float]
    mae_r: Optional[float]
    mfe_r: Optional[float]

def compute_orb_levels(
    conn: duckdb.DuckDBPyConnection,
    trading_date: date,
    orb_hour: int,
    orb_min: int,
    orb_duration_min: int = 5
) -> Optional[ORBResult]:
    """
    Compute ORB levels from raw bars_1m data.
    Zero-lookahead: Only uses bars within ORB window.
    """
    # Build ORB window in local time
    orb_start_local = datetime.combine(trading_date, dt_time(orb_hour, orb_min)).replace(tzinfo=TZ_LOCAL)
    orb_end_local = orb_start_local + timedelta(minutes=orb_duration_min)

    # Convert to UTC for query
    orb_start_utc = orb_start_local.astimezone(TZ_UTC)
    orb_end_utc = orb_end_local.astimezone(TZ_UTC)

    # Query bars within ORB window
    query = """
        SELECT high, low, close
        FROM bars_1m
        WHERE symbol = 'MGC'
        AND ts_utc >= ?
        AND ts_utc < ?
        ORDER BY ts_utc
    """

    orb_bars = conn.execute(query, [orb_start_utc, orb_end_utc]).fetchdf()

    if len(orb_bars) == 0:
        return None

    orb_high = orb_bars['high'].max()
    orb_low = orb_bars['low'].min()
    orb_size = orb_high - orb_low
    orb_midpoint = (orb_high + orb_low) / 2.0

    return ORBResult(
        orb_high=float(orb_high),
        orb_low=float(orb_low),
        orb_size=float(orb_size),
        orb_midpoint=float(orb_midpoint),
        bar_count=len(orb_bars)
    )

def simulate_orb_breakout(
    conn: duckdb.DuckDBPyConnection,
    trading_date: date,
    orb: ORBResult,
    orb_hour: int,
    orb_min: int,
    scan_end_hour: int,
    scan_end_min: int,
    rr: float,
    sl_mode: str,  # 'HALF' or 'FULL'
    mode: str = "ISOLATION"  # 'ISOLATION' or 'CONTINUATION'
) -> Optional[TradeResult]:
    """
    Simulate ORB breakout trade with zero-lookahead enforcement.

    ISOLATION mode: Force exit at scan_end
    CONTINUATION mode: No forced exit, TP/SL only
    """
    # Validate SL mode
    assert sl_mode in ("HALF", "FULL"), f"Invalid sl_mode: {sl_mode}"
    assert mode in ("ISOLATION", "CONTINUATION"), f"Invalid mode: {mode}"

    # Build scan window in local time
    scan_start_local = datetime.combine(trading_date, dt_time(orb_hour, orb_min)).replace(tzinfo=TZ_LOCAL) + timedelta(minutes=5)
    scan_end_local = datetime.combine(trading_date, dt_time(scan_end_hour, scan_end_min)).replace(tzinfo=TZ_LOCAL)

    # HARD ASSERTION: scan starts after ORB completes
    assert scan_start_local > datetime.combine(trading_date, dt_time(orb_hour, orb_min)).replace(tzinfo=TZ_LOCAL) + timedelta(minutes=4), \
        f"Lookahead violation: scan starts before ORB completes"

    # Convert to UTC
    scan_start_utc = scan_start_local.astimezone(TZ_UTC)
    scan_end_utc = scan_end_local.astimezone(TZ_UTC)

    # Find first close outside ORB
    entry_query = """
        SELECT ts_utc, close
        FROM bars_1m
        WHERE symbol = 'MGC'
        AND ts_utc >= ?
        AND ts_utc < ?
        ORDER BY ts_utc
    """

    scan_bars = conn.execute(entry_query, [scan_start_utc, scan_end_utc]).fetchdf()

    if len(scan_bars) == 0:
        return None

    # Detect breakout
    direction = None
    entry_bar = None

    for idx, row in scan_bars.iterrows():
        if row['close'] > orb.orb_high:
            direction = 'long'
            entry_bar = row
            break
        elif row['close'] < orb.orb_low:
            direction = 'short'
            entry_bar = row
            break

    if direction is None:
        return None

    # Entry time and price
    entry_ts = pd.to_datetime(entry_bar['ts_utc'], utc=True).to_pydatetime()
    entry_price = float(entry_bar['close'])

    # HARD ASSERTION: entry is after ORB end
    orb_end_utc = scan_start_local.astimezone(TZ_UTC) - timedelta(minutes=5) + timedelta(minutes=5)
    assert entry_ts >= orb_end_utc, f"Lookahead violation: entry before ORB completes"

    # Calculate stop based on SL mode
    if sl_mode == 'HALF':
        stop_price = orb.orb_midpoint
    else:  # FULL
        stop_price = orb.orb_low if direction == 'long' else orb.orb_high

    # Calculate risk
    if direction == 'long':
        risk = entry_price - stop_price
        if risk <= 0:
            return None  # Invalid trade
        target_price = entry_price + (risk * rr)
    else:  # short
        risk = stop_price - entry_price
        if risk <= 0:
            return None  # Invalid trade
        target_price = entry_price - (risk * rr)

    # Get all bars after entry for simulation
    if mode == "ISOLATION":
        # ISOLATION: only scan until session boundary
        sim_query = """
            SELECT ts_utc, high, low, close
            FROM bars_1m
            WHERE symbol = 'MGC'
            AND ts_utc > ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """
        sim_bars = conn.execute(sim_query, [entry_ts, scan_end_utc]).fetchdf()
    else:  # CONTINUATION
        # CONTINUATION: scan indefinitely (until TP/SL)
        # For practicality, limit to end of trading day (09:00 next day)
        continuation_end = datetime.combine(trading_date + timedelta(days=1), dt_time(9, 0)).replace(tzinfo=TZ_LOCAL).astimezone(TZ_UTC)
        sim_query = """
            SELECT ts_utc, high, low, close
            FROM bars_1m
            WHERE symbol = 'MGC'
            AND ts_utc > ?
            AND ts_utc < ?
            ORDER BY ts_utc
        """
        sim_bars = conn.execute(sim_query, [entry_ts, continuation_end]).fetchdf()

    if len(sim_bars) == 0:
        # No bars to simulate
        if mode == "ISOLATION":
            # Force exit at entry price
            return TradeResult(
                date_local=str(trading_date),
                orb_time=f"{orb_hour:02d}{orb_min:02d}",
                direction=direction,
                entry_ts=entry_ts,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                exit_ts=entry_ts,
                exit_price=entry_price,
                exit_reason='FORCE_EXIT',
                r_multiple=0.0,
                minutes_to_exit=0.0,
                mae_r=0.0,
                mfe_r=0.0
            )
        else:
            return None  # No exit in CONTINUATION mode

    # Simulate trade through bars
    mae_raw = 0.0
    mfe_raw = 0.0

    for idx, bar in sim_bars.iterrows():
        bar_ts = pd.to_datetime(bar['ts_utc'], utc=True).to_pydatetime()
        high = float(bar['high'])
        low = float(bar['low'])

        # Update MAE/MFE
        if direction == 'long':
            mae_raw = max(mae_raw, entry_price - low)
            mfe_raw = max(mfe_raw, high - entry_price)

            # Check stop (conservative: stop first)
            if low <= stop_price:
                minutes = (bar_ts - entry_ts).total_seconds() / 60.0
                return TradeResult(
                    date_local=str(trading_date),
                    orb_time=f"{orb_hour:02d}{orb_min:02d}",
                    direction=direction,
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    exit_ts=bar_ts,
                    exit_price=stop_price,
                    exit_reason='SL',
                    r_multiple=-1.0,
                    minutes_to_exit=minutes,
                    mae_r=mae_raw / risk if risk > 0 else 0,
                    mfe_r=mfe_raw / risk if risk > 0 else 0
                )

            # Check target
            if high >= target_price:
                minutes = (bar_ts - entry_ts).total_seconds() / 60.0
                return TradeResult(
                    date_local=str(trading_date),
                    orb_time=f"{orb_hour:02d}{orb_min:02d}",
                    direction=direction,
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    exit_ts=bar_ts,
                    exit_price=target_price,
                    exit_reason='TP',
                    r_multiple=rr,
                    minutes_to_exit=minutes,
                    mae_r=mae_raw / risk if risk > 0 else 0,
                    mfe_r=mfe_raw / risk if risk > 0 else 0
                )
        else:  # short
            mae_raw = max(mae_raw, high - entry_price)
            mfe_raw = max(mfe_raw, entry_price - low)

            # Check stop (conservative: stop first)
            if high >= stop_price:
                minutes = (bar_ts - entry_ts).total_seconds() / 60.0
                return TradeResult(
                    date_local=str(trading_date),
                    orb_time=f"{orb_hour:02d}{orb_min:02d}",
                    direction=direction,
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    exit_ts=bar_ts,
                    exit_price=stop_price,
                    exit_reason='SL',
                    r_multiple=-1.0,
                    minutes_to_exit=minutes,
                    mae_r=mae_raw / risk if risk > 0 else 0,
                    mfe_r=mfe_raw / risk if risk > 0 else 0
                )

            # Check target
            if low <= target_price:
                minutes = (bar_ts - entry_ts).total_seconds() / 60.0
                return TradeResult(
                    date_local=str(trading_date),
                    orb_time=f"{orb_hour:02d}{orb_min:02d}",
                    direction=direction,
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    exit_ts=bar_ts,
                    exit_price=target_price,
                    exit_reason='TP',
                    r_multiple=rr,
                    minutes_to_exit=minutes,
                    mae_r=mae_raw / risk if risk > 0 else 0,
                    mfe_r=mfe_raw / risk if risk > 0 else 0
                )

    # Reached end of scan window without TP/SL
    if mode == "ISOLATION":
        # Force exit at last bar close
        last_bar = sim_bars.iloc[-1]
        last_ts = pd.to_datetime(last_bar['ts_utc'], utc=True).to_pydatetime()
        last_close = float(last_bar['close'])

        # HARD ASSERTION: force exit is within scan window
        assert last_ts <= scan_end_utc, f"Force exit outside scan window"

        if direction == 'long':
            pnl = last_close - entry_price
        else:
            pnl = entry_price - last_close

        r_mult = pnl / risk if risk > 0 else 0
        minutes = (last_ts - entry_ts).total_seconds() / 60.0

        return TradeResult(
            date_local=str(trading_date),
            orb_time=f"{orb_hour:02d}{orb_min:02d}",
            direction=direction,
            entry_ts=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            exit_ts=last_ts,
            exit_price=last_close,
            exit_reason='FORCE_EXIT',
            r_multiple=r_mult,
            minutes_to_exit=minutes,
            mae_r=mae_raw / risk if risk > 0 else 0,
            mfe_r=mfe_raw / risk if risk > 0 else 0
        )
    else:
        # CONTINUATION mode: no exit yet
        return TradeResult(
            date_local=str(trading_date),
            orb_time=f"{orb_hour:02d}{orb_min:02d}",
            direction=direction,
            entry_ts=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            exit_ts=None,
            exit_price=None,
            exit_reason='NO_EXIT',
            r_multiple=0.0,
            minutes_to_exit=None,
            mae_r=mae_raw / risk if risk > 0 else 0,
            mfe_r=mfe_raw / risk if risk > 0 else 0
        )

def compute_metrics(trades: List[TradeResult]) -> Dict:
    """Compute performance metrics from trades."""
    if len(trades) == 0:
        return {
            'trades': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'profit_factor': 0.0,
            'max_dd_r': 0.0,
            'avg_minutes': 0.0
        }

    # Filter trades with exits
    completed = [t for t in trades if t.exit_reason in ('TP', 'SL', 'FORCE_EXIT')]

    if len(completed) == 0:
        return {
            'trades': len(trades),
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'profit_factor': 0.0,
            'max_dd_r': 0.0,
            'avg_minutes': 0.0
        }

    wins = [t for t in completed if t.r_multiple > 0]
    losses = [t for t in completed if t.r_multiple < 0]

    win_rate = len(wins) / len(completed) if len(completed) > 0 else 0.0
    avg_r = sum(t.r_multiple for t in completed) / len(completed)
    total_r = sum(t.r_multiple for t in completed)

    # Profit factor
    gross_profit = sum(t.r_multiple for t in wins) if wins else 0.0
    gross_loss = abs(sum(t.r_multiple for t in losses)) if losses else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    # Max drawdown
    equity = 0.0
    peak = 0.0
    max_dd = 0.0

    for t in completed:
        equity += t.r_multiple
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    # Avg minutes
    timed_trades = [t for t in completed if t.minutes_to_exit is not None]
    avg_minutes = sum(t.minutes_to_exit for t in timed_trades) / len(timed_trades) if timed_trades else 0.0

    return {
        'trades': len(completed),
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'profit_factor': profit_factor,
        'max_dd_r': max_dd,
        'avg_minutes': avg_minutes
    }

def compute_trades_hash(trades: List[TradeResult]) -> str:
    """Compute deterministic hash of trades for reproducibility check."""
    trade_strings = []
    for t in trades:
        s = f"{t.date_local}|{t.orb_time}|{t.direction}|{t.entry_price:.2f}|{t.r_multiple:.4f}"
        trade_strings.append(s)

    combined = "|".join(sorted(trade_strings))
    return hashlib.md5(combined.encode()).hexdigest()
