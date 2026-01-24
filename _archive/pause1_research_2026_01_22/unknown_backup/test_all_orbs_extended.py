"""
TEST ALL ORBS WITH EXTENDED SCAN WINDOWS
=========================================

Test EVERY ORB (0900, 1000, 1100, 1800, 2300, 0030) with scan windows
extended until next Asia open (09:00) to find TRUE optimal RR values.

Current windows might be cutting off before targets hit!
"""

import duckdb
from datetime import date, timedelta
from typing import Dict, Optional, Any
from dataclasses import dataclass
import pandas as pd

SYMBOL = "MGC"
TICK_SIZE = 0.1

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
    exit_ts: Optional[str]


def simulate_orb_extended(
    con: duckdb.DuckDBPyConnection,
    date_local: date,
    orb: str,
    rr: float = 1.0,
    sl_mode: str = "full",
) -> TradeResult:
    """
    Simulate ORB with EXTENDED scan window until next Asia open (09:00).
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

    # Get entry bar (first close outside ORB)
    h, m = ORB_TIMES[orb]
    if orb in ("0030",):  # 00:30 crosses midnight
        entry_start = f"{date_local + timedelta(days=1)} {h:02d}:{m:02d}:00"
    else:
        entry_start = f"{date_local} {h:02d}:{m:02d}:00"

    # EXTENDED scan window: until next Asia open (09:00)
    # For morning ORBs (0900, 1000, 1100), scan until 09:00 NEXT day
    # For afternoon/night ORBs (1800, 2300, 0030), scan until 09:00 same/next day
    if orb in ("0900", "1000", "1100"):
        scan_end = f"{date_local + timedelta(days=1)} 09:00:00"
    elif orb == "1800":
        scan_end = f"{date_local + timedelta(days=1)} 09:00:00"
    elif orb == "2300":
        scan_end = f"{date_local + timedelta(days=1)} 09:00:00"
    elif orb == "0030":
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


def test_orb_rr_sensitivity(orb: str, sl_mode: str = "full"):
    """Test multiple RR values with extended scan window for a single ORB"""

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
    print(f"TESTING {orb} ORB WITH EXTENDED SCAN WINDOW")
    print(f"SL Mode: {sl_mode.upper()}")
    print(f"Trading days: {len(dates)}")
    print(f"{'='*80}\n")

    rr_values = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]

    results = []

    for rr in rr_values:
        print(f"  RR={rr}...", end=" ", flush=True)

        trades = 0
        wins = 0
        total_r = 0.0

        for d in dates:
            result = simulate_orb_extended(con, d, orb, rr, sl_mode)

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
            "sl_mode": sl_mode,
            "trades": trades,
            "wins": wins,
            "win_rate": win_rate,
            "avg_r": avg_r,
            "total_r": total_r
        })

        print(f"Trades: {trades}, WR: {win_rate*100:.1f}%, Avg R: {avg_r:+.3f}, Total R: {total_r:+.0f}")

    con.close()

    return results


def main():
    print("\n" + "="*80)
    print("ALL ORBS EXTENDED WINDOW TEST")
    print("="*80)
    print("\nScanning until next Asia open (09:00) for ALL ORBs.")
    print("This reveals the TRUE optimal RR for each session!\n")

    all_results = []

    # Test each ORB with its recommended SL mode
    orb_configs = [
        ("0900", "full"),
        ("1000", "full"),
        ("1100", "full"),
        ("1800", "full"),
        ("2300", "half"),
        ("0030", "half"),
    ]

    for orb, sl_mode in orb_configs:
        results = test_orb_rr_sensitivity(orb, sl_mode)
        all_results.extend(results)

    # Save comprehensive results
    df = pd.DataFrame(all_results)
    filename = "ALL_ORBS_EXTENDED_WINDOWS.csv"
    df.to_csv(filename, index=False)

    print("\n" + "="*80)
    print("OPTIMAL RR VALUES (by best Avg R):")
    print("="*80)

    for orb, sl_mode in orb_configs:
        orb_results = [r for r in all_results if r['orb'] == orb]
        best = max(orb_results, key=lambda x: x['avg_r'])

        print(f"\n{orb} ORB ({sl_mode.upper()} SL):")
        print(f"  Optimal RR: {best['rr']}")
        print(f"  Win Rate: {best['win_rate']*100:.1f}%")
        print(f"  Avg R: {best['avg_r']:+.3f}")
        print(f"  Total R: {best['total_r']:+.0f}")
        print(f"  Annual R (est): ~{best['total_r']/2:+.0f}R/year")

    print(f"\n{'='*80}")
    print(f"Results saved to: {filename}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
