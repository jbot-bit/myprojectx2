import sys; sys.exit("DEPRECATED: This script is a redundant execution engine. Use build_daily_features_v2.py instead. This file is kept for historical reference only.")
# backtest_orb_exec_5mhalfsl.py
# 5m CONFIRMED entry + FULL/HALF ORB SL (+ optional buffer ticks)
# Includes --reset to drop/recreate table if your schema changed.

import duckdb
import argparse
from datetime import date, timedelta

DB_PATH = "gold.db"
SYMBOL = "MGC"

TICK_SIZE = 0.1

# Defaults
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
    if orb in ("0900", "1000", "1100"):
        return f"{d} 17:00:00"
    if orb == "1800":
        return f"{d} 23:00:00"
    if orb == "2300":
        return f"{d + timedelta(days=1)} 00:30:00"
    if orb == "0030":
        return f"{d + timedelta(days=1)} 02:00:00"
    return f"{d} 23:59:00"


def ensure_schema(con: duckdb.DuckDBPyConnection):
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS orb_trades_5m_exec (
            date_local DATE NOT NULL,
            orb VARCHAR NOT NULL,
            close_confirmations INTEGER NOT NULL,
            rr DOUBLE NOT NULL,
            sl_mode VARCHAR NOT NULL,
            buffer_ticks DOUBLE NOT NULL,

            direction VARCHAR,
            entry_ts TIMESTAMP,
            entry_price DOUBLE,
            stop_price DOUBLE,
            target_price DOUBLE,
            stop_ticks DOUBLE,

            outcome VARCHAR,
            r_multiple DOUBLE,
            entry_delay_bars INTEGER,
            mae_r DOUBLE,
            mfe_r DOUBLE,

            PRIMARY KEY (date_local, orb, close_confirmations, rr, sl_mode, buffer_ticks)
        )
        """
    )


def run_backtest(
    close_confirmations: int = 1,
    rr: float = RR_DEFAULT,
    sl_mode: str = "full",
    buffer_ticks: float = 0.0,
    commit_every_days: int = 10,
    reset: bool = False,
):
    con = duckdb.connect(DB_PATH)

    # create table (or reset if requested)
    if reset:
        con.execute("DROP TABLE IF EXISTS orb_trades_5m_exec")
    ensure_schema(con)

    days = con.execute(
        """
        SELECT date_local
        FROM daily_features_v2
        ORDER BY date_local
        """
    ).fetchall()

    total_days = len(days)
    inserted = 0
    skipped_no_orb = 0
    skipped_no_bars = 0
    skipped_no_entry = 0
    skipped_big_stop = 0
    scanned_orbs = 0

    print(
        f"\nRUN 5m: confirm={close_confirmations} | SL={sl_mode} | buffer_ticks={buffer_ticks} "
        f"| max_stop={MAX_STOP_TICKS} | RR={rr} | asia_tp_cap={ASIA_TP_CAP_TICKS}"
    )
    print(f"Days: {total_days} | Orbs/day: {len(ORB_TIMES)} | Total scans: {total_days * len(ORB_TIMES)}\n")

    for idx, (d,) in enumerate(days, start=1):
        day_inserts = 0

        for orb, (h, m) in ORB_TIMES.items():
            scanned_orbs += 1

            # ORB levels from daily_features_v2
            row = con.execute(
                f"""
                SELECT orb_{orb}_high, orb_{orb}_low
                FROM daily_features_v2
                WHERE date_local = ?
                """,
                [d],
            ).fetchone()

            if not row or row[0] is None or row[1] is None:
                skipped_no_orb += 1
                continue

            orb_high = float(row[0])
            orb_low = float(row[1])
            orb_range = orb_high - orb_low
            if orb_range <= 0:
                skipped_no_orb += 1
                continue

            # Start scanning AFTER the 5-min ORB completes
            start_min = m + 5
            start_date = d + timedelta(days=1) if orb == "0030" else d
            start_ts_local = f"{start_date} {h:02d}:{start_min:02d}:00"

            end_ts_local = orb_scan_end_local(orb, d)

            bars = con.execute(
                """
                SELECT
                  (ts_utc AT TIME ZONE 'Australia/Brisbane') AS ts_local,
                  high, low, close
                FROM bars_5m
                WHERE symbol = ?
                  AND (ts_utc AT TIME ZONE 'Australia/Brisbane') > CAST(? AS TIMESTAMP)
                  AND (ts_utc AT TIME ZONE 'Australia/Brisbane') <= CAST(? AS TIMESTAMP)
                ORDER BY ts_local
                """,
                [SYMBOL, start_ts_local, end_ts_local],
            ).fetchall()

            if not bars:
                skipped_no_bars += 1
                continue

            # Entry: N consecutive 5m CLOSES outside ORB
            consec = 0
            direction = None
            entry_price = None
            entry_ts = None
            entry_idx = None

            for i, (ts_local, _hi, _lo, close) in enumerate(bars):
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

                if consec >= close_confirmations:
                    entry_price = close
                    entry_ts = ts_local
                    entry_idx = i
                    break

            if entry_price is None:
                skipped_no_entry += 1
                continue

            # Stop-loss modes
            mid = (orb_high + orb_low) / 2.0
            buf = float(buffer_ticks) * TICK_SIZE

            if sl_mode == "full":
                stop_price = orb_low if direction == "UP" else orb_high
            elif sl_mode == "half":
                if direction == "UP":
                    stop_price = max(orb_low, mid - buf)
                else:
                    stop_price = min(orb_high, mid + buf)
            else:
                raise ValueError("sl_mode must be 'full' or 'half'")

            stop_ticks = abs(entry_price - stop_price) / TICK_SIZE
            if stop_ticks <= 0:
                skipped_big_stop += 1
                continue
            if stop_ticks > MAX_STOP_TICKS:
                skipped_big_stop += 1
                continue

            # Target = RR * risk
            risk = abs(entry_price - stop_price)
            target_price = entry_price + rr * risk if direction == "UP" else entry_price - rr * risk

            # Asia TP cap
            if is_asia(orb):
                cap = ASIA_TP_CAP_TICKS * TICK_SIZE
                if direction == "UP":
                    target_price = min(target_price, entry_price + cap)
                else:
                    target_price = max(target_price, entry_price - cap)

            # Outcome scan (HIGH/LOW-based, conservative: TP+SL same bar => LOSS)
            outcome = "NO_TRADE"
            r_mult = 0.0
            max_fav_ticks = 0.0
            max_adv_ticks = 0.0

            for _, hi, lo, _cl in bars[entry_idx + 1 :]:
                hi = float(hi)
                lo = float(lo)

                if direction == "UP":
                    max_fav_ticks = max(max_fav_ticks, (hi - entry_price) / TICK_SIZE)
                    max_adv_ticks = max(max_adv_ticks, (entry_price - lo) / TICK_SIZE)

                    hit_stop = lo <= stop_price
                    hit_target = hi >= target_price
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
                    max_fav_ticks = max(max_fav_ticks, (entry_price - lo) / TICK_SIZE)
                    max_adv_ticks = max(max_adv_ticks, (hi - entry_price) / TICK_SIZE)

                    hit_stop = hi >= stop_price
                    hit_target = lo <= target_price
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

            entry_delay_bars = entry_idx + 1
            mae_r = (max_adv_ticks / stop_ticks) if stop_ticks > 0 else None
            mfe_r = (max_fav_ticks / stop_ticks) if stop_ticks > 0 else None

            # 17 cols => 17 placeholders
            con.execute(
                """
                INSERT OR REPLACE INTO orb_trades_5m_exec
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    d,
                    orb,
                    int(close_confirmations),
                    float(rr),
                    sl_mode,
                    float(buffer_ticks),
                    direction,
                    entry_ts,
                    float(entry_price),
                    float(stop_price),
                    float(target_price),
                    float(stop_ticks),
                    outcome,
                    float(r_mult),
                    int(entry_delay_bars),
                    float(mae_r) if mae_r is not None else None,
                    float(mfe_r) if mfe_r is not None else None,
                ],
            )

            inserted += 1
            day_inserts += 1

        if idx % commit_every_days == 0:
            con.commit()
            print(
                f"[{idx:>4}/{total_days}] date={d} | day_inserts={day_inserts} | total_inserted={inserted} | "
                f"no_orb={skipped_no_orb} no_bars={skipped_no_bars} no_entry={skipped_no_entry} big_stop={skipped_big_stop}"
            )

    con.commit()
    con.close()

    print("\nDONE")
    print(f"inserted={inserted} scanned_orbs={scanned_orbs}")
    print(
        f"skipped: no_orb={skipped_no_orb} no_bars={skipped_no_bars} "
        f"no_entry={skipped_no_entry} big_stop={skipped_big_stop}\n"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirm", type=int, default=1, help="N consecutive 5m closes outside ORB")
    p.add_argument("--rr", type=float, default=RR_DEFAULT)
    p.add_argument("--rr-grid", type=str, default="", help="comma list e.g. 1,1.5,2")
    p.add_argument("--sl", type=str, default="full", choices=["full", "half"])
    p.add_argument("--buffer-ticks", type=float, default=0.0, help="e.g. 2 = 2 ticks (0.2)")
    p.add_argument("--commit-every", type=int, default=10)
    p.add_argument("--reset", action="store_true", help="DROP and recreate orb_trades_5m_exec (schema change fix)")
    args = p.parse_args()

    if args.rr_grid.strip():
        grid = [float(x.strip()) for x in args.rr_grid.split(",") if x.strip()]
        for rr in grid:
            run_backtest(
                close_confirmations=args.confirm,
                rr=rr,
                sl_mode=args.sl,
                buffer_ticks=args.buffer_ticks,
                commit_every_days=args.commit_every,
                reset=args.reset,
            )
            # only reset once (first run in grid)
            args.reset = False
    else:
        run_backtest(
            close_confirmations=args.confirm,
            rr=args.rr,
            sl_mode=args.sl,
            buffer_ticks=args.buffer_ticks,
            commit_every_days=args.commit_every,
            reset=args.reset,
        )


if __name__ == "__main__":
    main()
