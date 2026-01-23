"""
TEST NIGHT ORB WITH EXTENDED SCAN WINDOWS
==========================================

Current problem: 23:00 and 00:30 ORBs stop scanning after only 85 minutes!
- 23:00: scans until 00:30 (85 min)
- 00:30: scans until 02:00 (85 min)

But user observes 300+ tick moves (30+ points) which take HOURS to develop.

This script extends the scan window to next Asia open (09:00) to capture the REAL moves.
"""

import duckdb
from datetime import date, timedelta, datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass
import pandas as pd

SYMBOL = "MGC"
TICK_SIZE = 0.1

ORB_TIMES = {
    "2300": (23, 0),
    "0030": (0, 30),
}

@dataclass
class TradeResult:
    outcome: str
    direction: Optional[str]
    entry_ts: Optional[str]
    entry_price: Optional[float]
    stop_price: Optional[float]
    target_price: Optional[float]
    stop_ticks: Optional[float]
    r_multiple: float
    mae_r: Optional[float]
    mfe_r: Optional[float]
    orb_size: Optional[float]
    exit_ts: Optional[str]  # NEW: when did it hit TP/SL?


def simulate_night_orb_extended(
    con: duckdb.DuckDBPyConnection,
    date_local: date,
    orb: str,
    rr: float = 1.0,
    sl_mode: str = "half",
) -> TradeResult:
    """
    Simulate night ORB with EXTENDED scan window until next Asia open (09:00).
    """

    # Get ORB from daily features
    orb_col_prefix = f"orb_{orb}"
    query = f"""
    SELECT
        {orb_col_prefix}_high as orb_high,
        {orb_col_prefix}_low as orb_low,
        {orb_col_prefix}_size as orb_size,
        {orb_col_prefix}_break_dir as break_dir
    FROM daily_features_v2
    WHERE instrument = '{SYMBOL}'
        AND date_local = '{date_local}'
    """

    row = con.execute(query).fetchone()
    if not row:
        return TradeResult("SKIPPED_NO_ORB", None, None, None, None, None, None, 0.0, None, None, None, None)

    orb_high, orb_low, orb_size, break_dir = row

    if not break_dir or break_dir == "NONE":
        return TradeResult("NO_TRADE", None, None, None, None, None, None, 0.0, None, None, orb_size, None)

    # Get ORB edge
    orb_edge = orb_high if break_dir == "UP" else orb_low
    orb_mid = (orb_high + orb_low) / 2.0

    # Calculate stop
    if sl_mode == "full":
        stop = orb_low if break_dir == "UP" else orb_high
    else:  # half
        stop = orb_mid

    # R = distance from edge to stop
    r_orb = abs(orb_edge - stop)
    if r_orb <= 0:
        return TradeResult("SKIPPED_ZERO_R", None, None, None, None, None, None, 0.0, None, None, orb_size, None)

    # Target from ORB edge
    target = orb_edge + rr * r_orb if break_dir == "UP" else orb_edge - rr * r_orb

    # Get entry bar (first close outside ORB after 23:05 or 00:35)
    h, m = ORB_TIMES[orb]
    if h == 0:  # 00:30 crosses midnight
        entry_start = f"{date_local + timedelta(days=1)} {h:02d}:{m:02d}:00"
    else:
        entry_start = f"{date_local} {h:02d}:{m:02d}:00"

    # EXTENDED scan window: until next Asia open (09:00)
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

    # Find entry
    if break_dir == "UP":
        entry_query = f"""
        SELECT ts_utc, close
        FROM bars_1m
        WHERE symbol = '{SYMBOL}'
            AND ts_utc > '{entry_start}'::TIMESTAMPTZ
            AND ts_utc < '{scan_end}'::TIMESTAMPTZ
            AND close > {orb_high}
        ORDER BY ts_utc ASC
        LIMIT 1
        """
    else:  # DOWN
        entry_query = f"""
        SELECT ts_utc, close
        FROM bars_1m
        WHERE symbol = '{SYMBOL}'
            AND ts_utc > '{entry_start}'::TIMESTAMPTZ
            AND ts_utc < '{scan_end}'::TIMESTAMPTZ
            AND close < {orb_low}
        ORDER BY ts_utc ASC
        LIMIT 1
        """

    entry_row = con.execute(entry_query).fetchone()
    if not entry_row:
        return TradeResult("NO_TRADE", break_dir, None, None, None, None, None, 0.0, None, None, orb_size, None)

    entry_ts, entry_price = entry_row

    # Get all bars after entry until scan end
    bars_query = f"""
    SELECT ts_utc, high, low, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """

    bars = con.execute(bars_query).fetchall()
    if not bars:
        return TradeResult("NO_TRADE", break_dir, str(entry_ts), float(entry_price), float(stop), float(target), r_orb/TICK_SIZE, 0.0, None, None, orb_size, None)

    # Track MAE/MFE from ORB edge
    mae_raw = 0.0
    mfe_raw = 0.0

    for ts_utc, h, l, c in bars:
        h = float(h)
        l = float(l)

        if break_dir == "UP":
            mae_raw = max(mae_raw, orb_edge - l)
            mfe_raw = max(mfe_raw, h - orb_edge)

            hit_stop = l <= stop
            hit_target = h >= target

            if hit_stop and hit_target:
                # Both hit same bar = LOSS (conservative)
                return TradeResult("LOSS", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, -1.0, mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))
            if hit_target:
                return TradeResult("WIN", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, float(rr), mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))
            if hit_stop:
                return TradeResult("LOSS", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, -1.0, mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))
        else:  # DOWN
            mae_raw = max(mae_raw, h - orb_edge)
            mfe_raw = max(mfe_raw, orb_edge - l)

            hit_stop = h >= stop
            hit_target = l <= target

            if hit_stop and hit_target:
                return TradeResult("LOSS", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, -1.0, mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))
            if hit_target:
                return TradeResult("WIN", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, float(rr), mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))
            if hit_stop:
                return TradeResult("LOSS", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                                 r_orb/TICK_SIZE, -1.0, mae_raw/r_orb, mfe_raw/r_orb, orb_size, str(ts_utc))

    # Reached end of scan without TP/SL
    return TradeResult("NO_TRADE", break_dir, str(entry_ts), float(entry_price), float(stop), float(target),
                      r_orb/TICK_SIZE, 0.0, mae_raw/r_orb, mfe_raw/r_orb, orb_size, None)


def test_rr_sensitivity(orb: str, sl_mode: str = "half"):
    """Test multiple RR values with extended scan window"""

    con = duckdb.connect("gold.db", read_only=True)

    # Get all trading days
    dates_query = """
    SELECT DISTINCT date_local
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    dates = [row[0] for row in con.execute(dates_query).fetchall()]

    print(f"\n{'='*80}")
    print(f"TESTING {orb} ORB WITH EXTENDED SCAN WINDOW (until 09:00 next day)")
    print(f"SL Mode: {sl_mode.upper()}")
    print(f"Trading days: {len(dates)}")
    print(f"{'='*80}\n")

    rr_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]

    results = []

    for rr in rr_values:
        print(f"Testing RR={rr}...", end=" ", flush=True)

        trades = 0
        wins = 0
        total_r = 0.0

        for d in dates:
            result = simulate_night_orb_extended(con, d, orb, rr, sl_mode)

            if result.outcome in ("WIN", "LOSS"):
                trades += 1
                total_r += result.r_multiple
                if result.outcome == "WIN":
                    wins += 1

        win_rate = wins / trades if trades > 0 else 0.0
        avg_r = total_r / trades if trades > 0 else 0.0

        results.append({
            "orb": orb,
            "rr": rr,
            "trades": trades,
            "wins": wins,
            "win_rate": win_rate,
            "avg_r": avg_r,
            "total_r": total_r
        })

        print(f"Trades: {trades}, WR: {win_rate:.1%}, Avg R: {avg_r:+.3f}, Total R: {total_r:+.0f}")

    con.close()

    # Print summary table
    print(f"\n{'='*80}")
    print(f"RESULTS SUMMARY - {orb} ORB ({sl_mode.upper()} SL)")
    print(f"{'='*80}")
    print(f"{'RR':<6} {'Trades':<8} {'Wins':<6} {'WR%':<8} {'Avg R':<10} {'Total R':<10}")
    print(f"{'-'*80}")

    for r in results:
        print(f"{r['rr']:<6.1f} {r['trades']:<8} {r['wins']:<6} {r['win_rate']*100:<8.1f} {r['avg_r']:<+10.3f} {r['total_r']:<+10.0f}")

    # Save to CSV
    df = pd.DataFrame(results)
    filename = f"NIGHT_ORB_{orb}_{sl_mode}_EXTENDED.csv"
    df.to_csv(filename, index=False)
    print(f"\nResults saved to: {filename}")

    return results


if __name__ == "__main__":
    print("\n" + "="*80)
    print("NIGHT ORB EXTENDED WINDOW TEST")
    print("="*80)
    print("\nPROBLEM: Current backtest stops scanning after 85 minutes.")
    print("FIX: Extend scan window until next Asia open (09:00).")
    print("\nThis will reveal the REAL potential of night ORBs!\n")

    # Test 23:00 ORB
    results_2300 = test_rr_sensitivity("2300", sl_mode="half")

    # Test 00:30 ORB
    results_0030 = test_rr_sensitivity("0030", sl_mode="half")

    print("\n" + "="*80)
    print("KEY FINDINGS:")
    print("="*80)

    # Compare OLD vs NEW for RR=2.0
    print("\n23:00 ORB - RR=2.0:")
    old_2300 = next((r for r in results_2300 if r['rr'] == 2.0), None)
    if old_2300:
        print(f"  EXTENDED: {old_2300['trades']} trades, {old_2300['win_rate']*100:.1f}% WR, {old_2300['avg_r']:+.3f}R avg")
        print(f"  OLD (85min): 522 trades, 5.75% WR, -0.828R avg")
        print(f"  IMPROVEMENT: {(old_2300['win_rate'] - 0.0575) * 100:+.1f} percentage points!")

    print("\n00:30 ORB - RR=2.0:")
    old_0030 = next((r for r in results_0030 if r['rr'] == 2.0), None)
    if old_0030:
        print(f"  EXTENDED: {old_0030['trades']} trades, {old_0030['win_rate']*100:.1f}% WR, {old_0030['avg_r']:+.3f}R avg")
        print(f"  OLD (85min): 523 trades, 7.27% WR, -0.782R avg")
        print(f"  IMPROVEMENT: {(old_0030['win_rate'] - 0.0727) * 100:+.1f} percentage points!")

    print("\n" + "="*80)
    print("DONE!")
    print("="*80)
