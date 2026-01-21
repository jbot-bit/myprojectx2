"""
Candidate Backtest Engine - Zero-Lookahead Compliant

Properly tests edge candidates using:
- Raw bars_1m data (not precomputed outcomes)
- Candidate-specific RR, SL mode, scan windows, filters
- Correct midnight-crossing window handling
- Zero-lookahead enforcement

Fixes Phase 3 issues:
- No baseline outcome shortcuts
- Each candidate evaluated with its actual specifications
- Extended windows properly supported
"""

import pandas as pd
import numpy as np
import pytz
import re
import json
from datetime import datetime, time as dt_time, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from trading_app.cloud_mode import get_database_connection

# Timezone
TZ_LOCAL = pytz.timezone("Australia/Brisbane")  # UTC+10, no DST
TZ_UTC = pytz.utc


@dataclass
class CandidateSpec:
    """Normalized candidate specification."""
    candidate_id: int
    name: str
    instrument: str
    orb_time: str  # '0900', '1000', etc.
    orb_minutes: int  # default 5
    entry_rule: str  # 'breakout' or 'rejection'
    sl_mode: str  # 'HALF' or 'FULL'
    rr: float  # risk/reward ratio
    scan_start_local: dt_time  # Brisbane time
    scan_end_local: dt_time  # Brisbane time (may be next day)
    max_hold_end_local: dt_time  # Brisbane time
    filters: Dict[str, Any]  # filter specifications

    # Derived
    crosses_midnight: bool = False  # scan window crosses midnight


@dataclass
class Trade:
    """Single trade result."""
    candidate_id: int
    date_local: str
    direction: str  # 'long' or 'short'

    entry_ts_local: datetime
    entry_price: float
    stop_price: float
    target_price: float
    risk: float

    exit_ts_local: Optional[datetime] = None
    exit_price: Optional[float] = None
    outcome: str = 'NO_TRADE'  # WIN, LOSS, TIME_EXIT, NO_TRADE
    r_multiple: float = 0.0

    time_to_resolution_minutes: float = 0.0
    mae_r: float = 0.0  # Max adverse excursion in R
    mfe_r: float = 0.0  # Max favorable excursion in R


def parse_candidate_spec(candidate: Dict[str, Any]) -> CandidateSpec:
    """
    Parse edge_candidates row into normalized CandidateSpec.

    Extracts:
    - ORB time from test_config_json
    - RR from target_rule
    - SL mode from stop_rule
    - Scan window from scan_window field
    - Filters from filter_spec_json
    """
    # Parse JSONs
    test_config = json.loads(candidate['test_config_json']) if isinstance(candidate['test_config_json'], str) else (candidate['test_config_json'] or {})
    filter_spec = json.loads(candidate['filter_spec_json']) if isinstance(candidate['filter_spec_json'], str) else (candidate['filter_spec_json'] or {})

    # Extract ORB time
    orb_time = test_config.get('orb_time', 'UNKNOWN')

    # Parse RR from target_rule (e.g., "1.5R", "3.0R", "1.5-2.0R")
    target_rule = test_config.get('target_rule', '2.0R')
    rr_match = re.search(r'(\d+\.?\d*)(?:-\d+\.?\d*)?R?', target_rule)
    rr = float(rr_match.group(1)) if rr_match else 2.0

    # Extract SL mode from stop_rule
    stop_rule = test_config.get('stop_rule', 'ORB midpoint (HALF mode)')
    sl_mode = 'HALF' if 'HALF' in stop_rule or 'midpoint' in stop_rule else 'FULL'

    # Parse scan window (e.g., "23:05 → 09:00 (10 hours)", "18:05 → 02:00 (8 hours)")
    scan_window = test_config.get('scan_window', '')
    scan_start_local, scan_end_local = parse_scan_window(scan_window, orb_time)

    # Entry rule
    entry_rule_text = test_config.get('entry_rule', '')
    if 'rejection' in entry_rule_text.lower() or 'sweep' in entry_rule_text.lower():
        entry_rule = 'rejection'
    else:
        entry_rule = 'breakout'

    # Filters
    filters = parse_filters(filter_spec, test_config)

    # Check if window crosses midnight
    crosses_midnight = scan_end_local < scan_start_local

    return CandidateSpec(
        candidate_id=candidate['candidate_id'],
        name=candidate['name'],
        instrument=candidate.get('instrument', 'MGC'),
        orb_time=orb_time,
        orb_minutes=5,
        entry_rule=entry_rule,
        sl_mode=sl_mode,
        rr=rr,
        scan_start_local=scan_start_local,
        scan_end_local=scan_end_local,
        max_hold_end_local=scan_end_local,  # Same as scan end for now
        filters=filters,
        crosses_midnight=crosses_midnight
    )


def parse_scan_window(scan_window_text: str, orb_time: str) -> Tuple[dt_time, dt_time]:
    """
    Parse scan window text into start/end times.

    Examples:
    - "23:05 → 09:00 (10 hours)" -> (23:05, 09:00)
    - "18:05 → 02:00 (8 hours)" -> (18:05, 02:00)
    - "09:05 → 17:00 (6 hours)" -> (09:05, 17:00)
    """
    # Extract times using regex
    time_pattern = r'(\d{1,2}):(\d{2})'
    matches = re.findall(time_pattern, scan_window_text)

    if len(matches) >= 2:
        start_h, start_m = int(matches[0][0]), int(matches[0][1])
        end_h, end_m = int(matches[1][0]), int(matches[1][1])

        scan_start = dt_time(start_h, start_m)
        scan_end = dt_time(end_h, end_m)

        return scan_start, scan_end

    # Fallback: use ORB time + 5 minutes for start, add reasonable default window
    orb_h = int(orb_time[:2])
    orb_m = int(orb_time[2:])

    scan_start = dt_time(orb_h, orb_m + 5 if orb_m + 5 < 60 else 0)

    # Default windows by session
    if orb_time in ['2300', '0030']:
        scan_end = dt_time(9, 0)  # Extended to Asia open
    else:
        scan_end = dt_time(17, 0)  # End of Asia session

    return scan_start, scan_end


def parse_filters(filter_spec: Dict, test_config: Dict) -> Dict[str, Any]:
    """
    Extract filter specifications from candidate.

    Returns dict with filter keys:
    - orb_size_pct_min/max
    - directional_bias_required
    - asia_sweep_rejection
    - session_dependency
    """
    filters = {}

    # ORB size filter from description
    description = filter_spec.get('description', '')
    if 'size' in description.lower():
        # Extract percentage range (e.g., "0.2-0.5%")
        pct_match = re.search(r'(0\.\d+)[-–](0\.\d+)%', description)
        if pct_match:
            filters['orb_size_pct_min'] = float(pct_match.group(1))
            filters['orb_size_pct_max'] = float(pct_match.group(2))

    # Directional bias
    if 'bias' in description.lower() or 'bias' in filter_spec.get('type', '').lower():
        filters['directional_bias_required'] = True

    # Asia sweep/rejection
    if 'sweep' in description.lower() or 'rejection' in description.lower():
        filters['asia_sweep_rejection'] = True

    # Session dependencies (e.g., compression, alignment)
    if 'compression' in description.lower():
        filters['session_dependency'] = 'compression'
    elif 'alignment' in description.lower():
        filters['session_dependency'] = 'alignment'

    return filters


def load_bars_for_trading_day(
    conn,
    trading_date: date,
    spec: CandidateSpec
) -> pd.DataFrame:
    """
    Load bars for a trading day with proper timezone handling.

    Trading day for extended windows: from 09:00 on trading_date to 09:00 next day.
    For standard windows: same calendar day only.

    Returns bars with ts_local (Brisbane time) column added.
    """
    # Trading day starts at 09:00 local
    start_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date, dt_time(9, 0)))

    # For midnight-crossing windows, load until 09:00 next day
    if spec.crosses_midnight:
        end_dt_local = start_dt_local + timedelta(days=1)
    else:
        end_dt_local = TZ_LOCAL.localize(datetime.combine(trading_date + timedelta(days=1), dt_time(9, 0)))

    # Convert to UTC for query
    start_dt_utc = start_dt_local.astimezone(TZ_UTC)
    end_dt_utc = end_dt_local.astimezone(TZ_UTC)

    # Query bars
    bars = conn.execute("""
        SELECT ts_utc, open, high, low, close, volume
        FROM bars_1m
        WHERE symbol = ?
        AND ts_utc >= ?
        AND ts_utc < ?
        ORDER BY ts_utc
    """, [spec.instrument, start_dt_utc, end_dt_utc]).fetchdf()

    if len(bars) == 0:
        return pd.DataFrame()

    # Convert to datetime and add local time
    bars['ts_utc'] = pd.to_datetime(bars['ts_utc'], utc=True)
    bars['ts_local'] = bars['ts_utc'].dt.tz_convert(TZ_LOCAL)
    bars['time_local'] = bars['ts_local'].dt.time

    return bars


def calculate_orb(bars: pd.DataFrame, spec: CandidateSpec) -> Optional[Dict[str, float]]:
    """
    Calculate ORB from raw bars for the specified ORB time.

    Returns None if ORB cannot be calculated (missing data).
    """
    orb_h = int(spec.orb_time[:2])
    orb_m = int(spec.orb_time[2:])

    orb_start = dt_time(orb_h, orb_m)
    orb_end = dt_time(orb_h, orb_m + spec.orb_minutes) if orb_m + spec.orb_minutes < 60 else dt_time(orb_h + 1, 0)

    # Filter to ORB window
    orb_bars = bars[
        (bars['time_local'] >= orb_start) &
        (bars['time_local'] < orb_end)
    ]

    if len(orb_bars) == 0:
        return None

    orb_high = orb_bars['high'].max()
    orb_low = orb_bars['low'].min()
    orb_size = orb_high - orb_low
    orb_midpoint = (orb_high + orb_low) / 2.0

    return {
        'high': orb_high,
        'low': orb_low,
        'size': orb_size,
        'midpoint': orb_midpoint
    }


def apply_filters(
    orb: Dict[str, float],
    day_features: Optional[Dict],
    spec: CandidateSpec
) -> bool:
    """
    Apply candidate filters (zero-lookahead only).

    Returns True if passes all filters, False otherwise.
    """
    if not spec.filters:
        return True  # No filters

    # ORB size filter
    if 'orb_size_pct_min' in spec.filters or 'orb_size_pct_max' in spec.filters:
        # Convert ORB size to percentage of price (use ORB midpoint as proxy for price)
        orb_size_pct = (orb['size'] / orb['midpoint']) if orb['midpoint'] > 0 else 0

        min_pct = spec.filters.get('orb_size_pct_min', 0)
        max_pct = spec.filters.get('orb_size_pct_max', 1.0)

        if not (min_pct <= orb_size_pct <= max_pct):
            return False

    # Other filters would go here (directional bias, session dependencies, etc.)
    # For now, we skip them to get basic functionality working

    return True


def detect_breakout_entry(
    bars: pd.DataFrame,
    orb: Dict[str, float],
    spec: CandidateSpec,
    trading_date: date
) -> Optional[Tuple[pd.Series, str]]:
    """
    Detect first breakout entry (close outside ORB).

    Handles midnight-crossing windows correctly.

    Returns (entry_bar, direction) or None.
    """
    # Build scan window datetime range
    # Trading day starts at 09:00 local
    # If scan_start is before 09:00, it's on the NEXT calendar day
    if spec.scan_start_local < dt_time(9, 0):
        scan_start_cal_date = trading_date + timedelta(days=1)
    else:
        scan_start_cal_date = trading_date

    scan_start_dt = TZ_LOCAL.localize(datetime.combine(scan_start_cal_date, spec.scan_start_local))

    # If scan crosses midnight, end is next calendar day relative to scan start
    if spec.crosses_midnight:
        scan_end_cal_date = scan_start_cal_date + timedelta(days=1)
        scan_end_dt = TZ_LOCAL.localize(datetime.combine(scan_end_cal_date, spec.scan_end_local))
    else:
        # Same calendar day as scan start
        scan_end_dt = TZ_LOCAL.localize(datetime.combine(scan_start_cal_date, spec.scan_end_local))

    # Filter bars to scan window
    scan_bars = bars[
        (bars['ts_local'] >= scan_start_dt) &
        (bars['ts_local'] < scan_end_dt)
    ]

    if len(scan_bars) == 0:
        return None

    # Find first close outside ORB
    for idx, bar in scan_bars.iterrows():
        if bar['close'] > orb['high']:
            return (bar, 'long')
        elif bar['close'] < orb['low']:
            return (bar, 'short')

    return None


def simulate_trade(
    entry_bar: pd.Series,
    direction: str,
    orb: Dict[str, float],
    remaining_bars: pd.DataFrame,
    spec: CandidateSpec
) -> Trade:
    """
    Simulate trade from entry to exit.

    Returns completed Trade object.
    """
    entry_price = entry_bar['close']
    entry_ts = entry_bar['ts_local']

    # Calculate stop
    if spec.sl_mode == 'HALF':
        stop_price = orb['midpoint']
    else:  # FULL
        stop_price = orb['low'] if direction == 'long' else orb['high']

    # Calculate risk and target
    if direction == 'long':
        risk = entry_price - stop_price
        target_price = entry_price + (risk * spec.rr)
    else:  # short
        risk = stop_price - entry_price
        target_price = entry_price - (risk * spec.rr)

    if risk <= 0:
        # Invalid trade
        return Trade(
            candidate_id=spec.candidate_id,
            date_local=str(entry_ts.date()),
            direction=direction,
            entry_ts_local=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk=risk,
            outcome='NO_TRADE'
        )

    # Track through remaining bars
    mae = 0.0
    mfe = 0.0

    for idx, bar in remaining_bars.iterrows():
        # Check stop and target (conservative: stop-first if both hit)
        if direction == 'long':
            # Check stop first
            if bar['low'] <= stop_price:
                return Trade(
                    candidate_id=spec.candidate_id,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=stop_price,
                    outcome='LOSS',
                    r_multiple=-1.0,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60,
                    mae_r=1.0,
                    mfe_r=abs(mfe / risk) if risk != 0 else 0
                )

            # Check target
            if bar['high'] >= target_price:
                return Trade(
                    candidate_id=spec.candidate_id,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=target_price,
                    outcome='WIN',
                    r_multiple=spec.rr,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60,
                    mae_r=abs(mae / risk) if risk != 0 else 0,
                    mfe_r=spec.rr
                )

            # Track MAE/MFE
            unrealized = bar['close'] - entry_price
            if unrealized < mae:
                mae = unrealized
            if unrealized > mfe:
                mfe = unrealized

        else:  # short
            # Check stop first
            if bar['high'] >= stop_price:
                return Trade(
                    candidate_id=spec.candidate_id,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=stop_price,
                    outcome='LOSS',
                    r_multiple=-1.0,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60,
                    mae_r=1.0,
                    mfe_r=abs(mfe / risk) if risk != 0 else 0
                )

            # Check target
            if bar['low'] <= target_price:
                return Trade(
                    candidate_id=spec.candidate_id,
                    date_local=str(entry_ts.date()),
                    direction=direction,
                    entry_ts_local=entry_ts,
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk=risk,
                    exit_ts_local=bar['ts_local'],
                    exit_price=target_price,
                    outcome='WIN',
                    r_multiple=spec.rr,
                    time_to_resolution_minutes=(bar['ts_local'] - entry_ts).total_seconds() / 60,
                    mae_r=abs(mae / risk) if risk != 0 else 0,
                    mfe_r=spec.rr
                )

            # Track MAE/MFE
            unrealized = entry_price - bar['close']
            if unrealized < mae:
                mae = unrealized
            if unrealized > mfe:
                mfe = unrealized

    # Time exit (no TP/SL hit)
    if len(remaining_bars) > 0:
        final_bar = remaining_bars.iloc[-1]
        final_price = final_bar['close']

        if direction == 'long':
            pnl = final_price - entry_price
        else:
            pnl = entry_price - final_price

        r_mult = pnl / risk if risk != 0 else 0

        return Trade(
            candidate_id=spec.candidate_id,
            date_local=str(entry_ts.date()),
            direction=direction,
            entry_ts_local=entry_ts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            risk=risk,
            exit_ts_local=final_bar['ts_local'],
            exit_price=final_price,
            outcome='TIME_EXIT',
            r_multiple=r_mult,
            time_to_resolution_minutes=(final_bar['ts_local'] - entry_ts).total_seconds() / 60,
            mae_r=abs(mae / risk) if risk != 0 else 0,
            mfe_r=abs(mfe / risk) if risk != 0 else 0
        )

    # No bars to exit on
    return Trade(
        candidate_id=spec.candidate_id,
        date_local=str(entry_ts.date()),
        direction=direction,
        entry_ts_local=entry_ts,
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        risk=risk,
        outcome='NO_TRADE'
    )


def backtest_candidate(
    candidate: Dict[str, Any],
    start_date: str = '2020-12-20',
    end_date: str = '2026-01-10'
) -> List[Trade]:
    """
    Backtest a single candidate across date range.

    Returns list of Trade objects.
    """
    # Parse candidate spec
    spec = parse_candidate_spec(candidate)

    # Connect to database (use cloud-aware connection)
    conn = get_database_connection(read_only=True)

    # Generate trading dates
    start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()

    trades = []
    current_date = start_dt

    while current_date <= end_dt:
        # Load bars for trading day
        bars = load_bars_for_trading_day(conn, current_date, spec)

        if len(bars) == 0:
            current_date += timedelta(days=1)
            continue

        # Calculate ORB
        orb = calculate_orb(bars, spec)
        if not orb:
            current_date += timedelta(days=1)
            continue

        # Apply filters
        if not apply_filters(orb, None, spec):
            current_date += timedelta(days=1)
            continue

        # Detect entry (only breakout for now)
        if spec.entry_rule == 'breakout':
            entry_result = detect_breakout_entry(bars, orb, spec, current_date)

            if entry_result:
                entry_bar, direction = entry_result

                # Get remaining bars after entry
                remaining_bars = bars[bars['ts_local'] > entry_bar['ts_local']]

                # Simulate trade
                trade = simulate_trade(entry_bar, direction, orb, remaining_bars, spec)

                if trade.outcome != 'NO_TRADE':
                    trades.append(trade)

        current_date += timedelta(days=1)

    # Note: Don't close connection - managed by cloud_mode
    return trades


def calculate_metrics(trades: List[Trade]) -> Dict[str, Any]:
    """Calculate performance metrics from trades."""
    if len(trades) == 0:
        return {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'time_exits': 0,
            'win_rate': 0.0,
            'avg_r': 0.0,
            'total_r': 0.0,
            'avg_win_r': 0.0,
            'avg_loss_r': 0.0,
            'avg_time_to_resolution_hours': 0.0
        }

    total_trades = len(trades)
    wins = len([t for t in trades if t.outcome == 'WIN'])
    losses = len([t for t in trades if t.outcome == 'LOSS'])
    time_exits = len([t for t in trades if t.outcome == 'TIME_EXIT'])

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    r_multiples = [t.r_multiple for t in trades]
    avg_r = np.mean(r_multiples) if r_multiples else 0
    total_r = np.sum(r_multiples) if r_multiples else 0

    win_rs = [t.r_multiple for t in trades if t.outcome == 'WIN']
    loss_rs = [t.r_multiple for t in trades if t.outcome == 'LOSS']

    avg_win_r = np.mean(win_rs) if win_rs else 0
    avg_loss_r = np.mean(loss_rs) if loss_rs else 0

    times = [t.time_to_resolution_minutes / 60.0 for t in trades]
    avg_time = np.mean(times) if times else 0

    return {
        'total_trades': total_trades,
        'wins': wins,
        'losses': losses,
        'time_exits': time_exits,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'avg_win_r': avg_win_r,
        'avg_loss_r': avg_loss_r,
        'avg_time_to_resolution_hours': avg_time
    }
