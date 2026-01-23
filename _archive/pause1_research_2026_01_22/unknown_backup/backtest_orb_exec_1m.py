import sys; sys.exit("DEPRECATED: This script is a redundant execution engine. Use build_daily_features_v2.py instead. This file is kept for historical reference only.")
import duckdb
import argparse
from datetime import datetime, date, timedelta

DB_PATH = "gold.db"
SYMBOL = "MGC"

TICK_SIZE = 0.1

# RULES (locked)
MAX_STOP_TICKS = 100
RR_DEFAULT = 2.0
ASIA_TP_CAP_TICKS = 150

# ORB open times (local Brisbane time)
ORB_TIMES = {
    "0900": (9, 0),
    "1000": (10, 0),
    "1100": (11, 0),
    "1800": (18, 0),
    "2300": (23, 0),
    "0030": (0, 30),
}

def is_asia(orb: str) -> bool:
    return orb in ("0900", "1000", "1100")

def orb_scan_end_local(orb: str, d: date) -> str:
    """
    Hard stop for scanning (keeps it fast + prevents 'infinite day' scans).
    We only need enough future to decide TP/SL within the relevant block.
    """
    if orb in ("0900", "1000", "1100"):
        return f"{d} 17:00:00"      # end Asia session
    if orb == "1800":
        return f"{d} 23:00:00"      # end London session
    if orb == "2300":
        # NY Futures block ends at 00:30 next day (local)
        return f"{d + timedelta(days=1)} 00:30:00"
    if orb == "0030":
        return f"{d + timedelta(days=1)} 02:00:00"      # end NY cash block
    return f"{d} 23:59:00"

def ensure_schema(con: duckdb.DuckDBPyConnection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS orb_trades_1m_exec (
            date_local DATE NOT NULL,
            orb VARCHAR NOT NULL,
            close_confirmations INTEGER NOT NULL,
            rr DOUBLE NOT NULL,

            direction VARCHAR,
            entry_ts TIMESTAMP,
            entry_price DOUBLE,
            stop_price DOUBLE,
            target_price DOUBLE,
            stop_ticks DOUBLE,

            outcome VARCHAR,
            r_multiple DOUBLE,
            entry_delay_min INTEGER,
            mae_r DOUBLE,
            mfe_r DOUBLE,

            PRIMARY KEY (date_local, orb, close_confirmations, rr)
        )
    """)
    # Backward-compatible column adds (non-destructive)
    con.execute("ALTER TABLE orb_trades_1m_exec ADD COLUMN IF NOT EXISTS rr DOUBLE;")
    con.execute("ALTER TABLE orb_trades_1m_exec ADD COLUMN IF NOT EXISTS mae_r DOUBLE;")
    con.execute("ALTER TABLE orb_trades_1m_exec ADD COLUMN IF NOT EXISTS mfe_r DOUBLE;")

def run_backtest(close_confirmations: int = 1, rr: float = RR_DEFAULT, commit_every_days: int = 10):
    con = duckdb.connect(DB_PATH)

    ensure_schema(con)

    # Pull trading dates from the already-built daily_features_v2 table
    days = con.execute("""
        SELECT date_local
        FROM daily_features_v2
        ORDER BY date_local
    """).fetchall()

    total_days = len(days)
    inserted = 0
    skipped_no_orb = 0
    skipped_no_bars = 0
    skipped_no_entry = 0
    skipped_big_stop = 0
    scanned_orbs = 0

    print(f"\nRUN: close_confirmations={close_confirmations} | max_stop={MAX_STOP_TICKS} | RR={rr} | asia_tp_cap={ASIA_TP_CAP_TICKS}")
    print(f"Days: {total_days} | Orbs per day: {len(ORB_TIMES)} | Total orb scans: {total_days * len(ORB_TIMES)}\n")

    for idx, (d,) in enumerate(days, start=1):
        day_inserts = 0

        for orb, (h, m) in ORB_TIMES.items():
            scanned_orbs += 1

            # Get ORB levels from daily_features_v2
            row = con.execute(f"""
                SELECT orb_{orb}_high, orb_{orb}_low
                FROM daily_features_v2
                WHERE date_local = ?
            """, [d]).fetchone()

            if not row or row[0] is None or row[1] is None:
                skipped_no_orb += 1
                continue

            orb_high, orb_low = row
            orb_range = orb_high - orb_low
            if orb_range <= 0:
                skipped_no_orb += 1
                continue

            # Start scanning AFTER the 5-min ORB completes
            start_min = m + 5
            # handle date rollover for 00:30 ORB (belongs to D+1 local)
            start_date = d + timedelta(days=1) if orb == "0030" else d
            start_ts_local = f"{start_date} {h:02d}:{start_min:02d}:00"

            # End time for scan (limits runtime)
            end_ts_local = orb_scan_end_local(orb, d)

            bars = con.execute("""
                SELECT
                  (ts_utc AT TIME ZONE 'Australia/Brisbane') AS ts_local,
                  high, low, close
                FROM bars_1m
                WHERE symbol = ?
                  AND (ts_utc AT TIME ZONE 'Australia/Brisbane') > CAST(? AS TIMESTAMP)
                  AND (ts_utc AT TIME ZONE 'Australia/Brisbane') <= CAST(? AS TIMESTAMP)
                ORDER BY ts_local
            """, [SYMBOL, start_ts_local, end_ts_local]).fetchall()

            if not bars:
                skipped_no_bars += 1
                continue

            # Entry logic: N consecutive closes outside ORB
            consec = 0
            direction = None
            entry_price = None
            entry_ts = None
            entry_idx = None

            for i, (ts_local, high, low, close) in enumerate(bars):
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

                if consec >= close_confirmations:
                    entry_price = close
                    entry_ts = ts_local
                    entry_idx = i
                    break

            if entry_price is None:
                skipped_no_entry += 1
                continue

            # Stop opposite ORB
            stop_price = orb_low if direction == "UP" else orb_high
            stop_ticks = abs(entry_price - stop_price) / TICK_SIZE

            if stop_ticks > MAX_STOP_TICKS:
                skipped_big_stop += 1
                continue

            # Target = RR * risk
            risk = abs(entry_price - stop_price)
            target_price = entry_price + rr * risk if direction == "UP" else entry_price - rr * risk

            # Asia TP cap in ticks
            if is_asia(orb):
                cap = ASIA_TP_CAP_TICKS * TICK_SIZE
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
                else:
                    max_fav_ticks = max(max_fav_ticks, (entry_price - low) / TICK_SIZE)
                    max_adv_ticks = max(max_adv_ticks, (high - entry_price) / TICK_SIZE)

                    hit_stop = high >= stop_price
                    hit_target = low <= target_price
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

            entry_delay_min = entry_idx + 1  # minutes after ORB end until entry trigger
            mae_r = (max_adv_ticks / stop_ticks) if stop_ticks and stop_ticks > 0 else None
            mfe_r = (max_fav_ticks / stop_ticks) if stop_ticks and stop_ticks > 0 else None

            # Idempotent write: PRIMARY KEY + INSERT OR REPLACE prevents duplicates
            con.execute("""
                INSERT OR REPLACE INTO orb_trades_1m_exec
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                d, orb, close_confirmations,
                rr,
                direction, entry_ts,
                entry_price, stop_price, target_price,
                stop_ticks,
                outcome, r_mult, entry_delay_min,
                mae_r, mfe_r
            ])

            inserted += 1
            day_inserts += 1

        # progress + periodic commit
        if idx % commit_every_days == 0:
            con.commit()
            print(f"[{idx:>4}/{total_days}] date={d} | day_inserts={day_inserts} | total_inserted={inserted} | "
                  f"no_orb={skipped_no_orb} no_bars={skipped_no_bars} no_entry={skipped_no_entry} big_stop={skipped_big_stop}")

    con.commit()
    con.close()

    print("\nDONE")
    print(f"inserted={inserted} scanned_orbs={scanned_orbs}")
    print(f"skipped: no_orb={skipped_no_orb} no_bars={skipped_no_bars} no_entry={skipped_no_entry} big_stop={skipped_big_stop}\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", type=int, default=1)
    p.add_argument("--rr", type=float, default=RR_DEFAULT)
    p.add_argument("--rr-grid", type=str, default="")
    p.add_argument("--commit-every", type=int, default=10)
    args = p.parse_args()

    if args.rr_grid.strip():
        grid = [float(x.strip()) for x in args.rr_grid.split(",") if x.strip()]
        for rr in grid:
            run_backtest(close_confirmations=args.confirm, rr=rr, commit_every_days=args.commit_every)
    else:
        run_backtest(close_confirmations=args.confirm, rr=args.rr, commit_every_days=args.commit_every)
