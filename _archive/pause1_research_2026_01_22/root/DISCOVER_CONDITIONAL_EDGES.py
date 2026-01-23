"""
DISCOVER CONDITIONAL EDGES - FILTER-GATED UNICORNS
===================================================

Find zero-lookahead filters that create SUPER SETUPS.

For each ORB, test pre-session conditions:
1. Asia range (coiled/extended)
2. Directional alignment (prior ORBs)
3. ORB size relative to ATR
4. Gap conditions
5. Prior day momentum

Goal: Find "When X is true, setup Y has 2x better edge"

Example: "1800 ORB with small Asia range → 0.50 avg R (vs 0.27 baseline)"
"""

import duckdb
from datetime import date, timedelta, datetime, time
from dataclasses import dataclass
import pandas as pd

DB_PATH = "data/db/gold.db"
SYMBOL = "MGC"

@dataclass
class FilterResult:
    orb: str
    rr: float
    sl_mode: str
    filter_name: str
    filter_desc: str
    baseline_trades: int
    baseline_avg_r: float
    filtered_trades: int
    filtered_win_rate: float
    filtered_avg_r: float
    improvement: float
    freq_pct: float


def get_orb_from_bars(con, date_local, hour, minute, duration=5):
    """Get ORB from bars_1m"""
    start_ts = f"{date_local} {hour:02d}:{minute:02d}:00"
    end_dt = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=duration)
    end_ts = end_dt.strftime("%Y-%m-%d %H:%M:%S")

    query = f"""
    SELECT high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{start_ts}'::TIMESTAMPTZ
        AND ts_utc < '{end_ts}'::TIMESTAMPTZ
    """
    rows = con.execute(query).fetchall()
    if not rows:
        return None

    orb_high = max(float(r[0]) for r in rows)
    orb_low = min(float(r[1]) for r in rows)
    if orb_high <= orb_low:
        return None

    return {'high': orb_high, 'low': orb_low, 'size': orb_high - orb_low}


def detect_break(con, orb, date_local, hour, minute):
    """Detect first close outside ORB"""
    entry_start = datetime.combine(date_local, time(hour, minute)) + timedelta(minutes=5)
    entry_start_str = entry_start.strftime("%Y-%m-%d %H:%M:%S")
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

    query = f"""
    SELECT ts_utc, close
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc >= '{entry_start_str}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    rows = con.execute(query).fetchall()
    if not rows:
        return None, None

    for ts, close in rows:
        if float(close) > orb['high']:
            return 'UP', str(ts)
        elif float(close) < orb['low']:
            return 'DOWN', str(ts)
    return None, None


def simulate_trade(con, orb, break_dir, entry_ts, date_local, rr, sl_mode):
    """Simulate trade outcome"""
    orb_edge = orb['high'] if break_dir == 'UP' else orb['low']
    orb_mid = (orb['high'] + orb['low']) / 2.0

    if sl_mode == "FULL":
        stop = orb['low'] if break_dir == 'UP' else orb['high']
    elif sl_mode == "HALF":
        stop = orb_mid
    else:
        return None

    r_size = abs(orb_edge - stop)
    if r_size <= 0:
        return None

    target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)
    scan_end = f"{date_local + timedelta(days=1)} 09:00:00"

    query = f"""
    SELECT ts_utc, high, low
    FROM bars_1m
    WHERE symbol = '{SYMBOL}'
        AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
        AND ts_utc < '{scan_end}'::TIMESTAMPTZ
    ORDER BY ts_utc ASC
    """
    bars = con.execute(query).fetchall()
    if not bars:
        return None

    for ts_utc, h, l in bars:
        h, l = float(h), float(l)
        if break_dir == 'UP':
            if l <= stop and h >= target:
                return -1.0
            if h >= target:
                return float(rr)
            if l <= stop:
                return -1.0
        else:
            if h >= stop and l <= target:
                return -1.0
            if l <= target:
                return float(rr)
            if h >= stop:
                return -1.0
    return None


def get_features(con, date_local):
    """Get pre-session features from daily_features_v2"""
    query = f"""
    SELECT
        asia_high, asia_low, asia_range,
        orb_0900_break_dir, orb_0900_size,
        orb_1000_break_dir, orb_1000_size,
        orb_1100_break_dir, orb_1100_size,
        atr_20
    FROM daily_features_v2
    WHERE instrument = 'MGC' AND date_local = '{date_local}'
    """
    row = con.execute(query).fetchone()
    if not row:
        return None

    return {
        'asia_high': row[0],
        'asia_low': row[1],
        'asia_range': row[2],
        'orb_0900_break_dir': row[3],
        'orb_0900_size': row[4],
        'orb_1000_break_dir': row[5],
        'orb_1000_size': row[6],
        'orb_1100_break_dir': row[7],
        'orb_1100_size': row[8],
        'atr_20': row[9],
    }


def test_filter(con, dates, orb_name, hour, minute, rr, sl_mode, filter_func, filter_name, filter_desc):
    """Test setup with and without filter"""

    baseline_results = []
    filtered_results = []

    for d in dates:
        # Get features
        features = get_features(con, d)
        if not features or not features['atr_20']:
            continue

        # Get ORB
        orb = get_orb_from_bars(con, d, hour, minute)
        if not orb:
            continue

        # Detect break
        break_dir, entry_ts = detect_break(con, orb, d, hour, minute)
        if not break_dir:
            continue

        # Simulate trade
        r_mult = simulate_trade(con, orb, break_dir, entry_ts, d, rr, sl_mode)
        if r_mult is None:
            continue

        # Baseline (all trades)
        baseline_results.append(r_mult)

        # Filtered (only if filter passes)
        if filter_func(features, orb, break_dir):
            filtered_results.append(r_mult)

    # Calculate stats
    if len(baseline_results) < 100:
        return None

    baseline_trades = len(baseline_results)
    baseline_avg_r = sum(baseline_results) / baseline_trades

    if len(filtered_results) < 30:  # Need minimum 30 filtered trades
        return None

    filtered_trades = len(filtered_results)
    filtered_wins = sum(1 for r in filtered_results if r > 0)
    filtered_win_rate = filtered_wins / filtered_trades
    filtered_avg_r = sum(filtered_results) / filtered_trades

    # Must improve by at least 30%
    improvement = (filtered_avg_r - baseline_avg_r) / baseline_avg_r
    if improvement < 0.30:
        return None

    freq_pct = (filtered_trades / baseline_trades) * 100

    return FilterResult(
        orb=orb_name,
        rr=rr,
        sl_mode=sl_mode,
        filter_name=filter_name,
        filter_desc=filter_desc,
        baseline_trades=baseline_trades,
        baseline_avg_r=baseline_avg_r,
        filtered_trades=filtered_trades,
        filtered_win_rate=filtered_win_rate,
        filtered_avg_r=filtered_avg_r,
        improvement=improvement,
        freq_pct=freq_pct
    )


def main():
    print("\n" + "="*100)
    print("DISCOVERING CONDITIONAL EDGES - FILTER-GATED UNICORNS")
    print("="*100)
    print("\nSearching for zero-lookahead filters that create SUPER SETUPS")
    print("Criteria: Filter improves edge by 30%+, min 30 filtered trades\n")

    con = duckdb.connect(DB_PATH, read_only=True)

    # Get dates
    dates_query = """
    SELECT DISTINCT date(ts_utc) as date_local
    FROM bars_1m
    WHERE symbol = 'MGC'
        AND ts_utc >= '2024-01-02'::TIMESTAMPTZ
        AND ts_utc <= '2026-01-10'::TIMESTAMPTZ
    ORDER BY date_local
    """
    dates = [row[0] for row in con.execute(dates_query).fetchall()]
    print(f"Testing across {len(dates)} dates\n")

    # Define filters (zero lookahead)
    filters = [
        # Asia range filters (coiled = ready to expand)
        (lambda f, o, d: f['asia_range'] and f['asia_range'] < 0.20 * f['atr_20'],
         "ASIA_COILED_20", "Asia range < 20% ATR (coiled spring)"),

        (lambda f, o, d: f['asia_range'] and f['asia_range'] < 0.25 * f['atr_20'],
         "ASIA_COILED_25", "Asia range < 25% ATR"),

        (lambda f, o, d: f['asia_range'] and f['asia_range'] < 0.30 * f['atr_20'],
         "ASIA_COILED_30", "Asia range < 30% ATR"),

        # Directional alignment
        (lambda f, o, d: f['orb_0900_break_dir'] == d or f['orb_1000_break_dir'] == d,
         "ALIGN_ASIA", "1800 aligns with 0900/1000 direction"),

        (lambda f, o, d: f['orb_0900_break_dir'] == d and f['orb_1000_break_dir'] == d,
         "STRONG_ALIGN", "Both 0900 AND 1000 align (strong trend)"),

        # ORB size filters
        (lambda f, o, d: o['size'] < 0.10 * f['atr_20'],
         "SMALL_ORB_10", "ORB size < 10% ATR (tight range)"),

        (lambda f, o, d: o['size'] < 0.15 * f['atr_20'],
         "SMALL_ORB_15", "ORB size < 15% ATR"),

        (lambda f, o, d: o['size'] > 0.20 * f['atr_20'],
         "LARGE_ORB_20", "ORB size > 20% ATR (volatile)"),

        # Combined filters
        (lambda f, o, d: f['asia_range'] and f['asia_range'] < 0.25 * f['atr_20'] and
                         (f['orb_0900_break_dir'] == d or f['orb_1000_break_dir'] == d),
         "COILED_ALIGNED", "Coiled Asia + directional alignment"),

        (lambda f, o, d: f['asia_range'] and f['asia_range'] < 0.30 * f['atr_20'] and
                         o['size'] < 0.15 * f['atr_20'],
         "DOUBLE_COILED", "Coiled Asia + small ORB (double compression)"),
    ]

    # Test ORBs
    orb_configs = [
        ("1800", 18, 0, 1.5, "FULL"),  # Best London setup
        ("1800", 18, 0, 2.0, "FULL"),  # Higher RR
        ("2300", 23, 0, 1.5, "HALF"),  # Best night setup
        ("2300", 23, 0, 2.0, "HALF"),  # Higher RR
        ("0030", 0, 30, 3.0, "HALF"),  # Best NY setup
        ("1000", 10, 0, 8.0, "FULL"),  # Crown jewel
        ("1000", 10, 0, 6.0, "FULL"),  # Alternative
    ]

    discoveries = []

    print("Testing combinations (this will take 2-3 minutes)...\n")

    for orb_name, hour, minute, rr, sl_mode in orb_configs:
        print(f"Testing {orb_name} RR={rr} {sl_mode}...", flush=True)

        for filter_func, filter_name, filter_desc in filters:
            result = test_filter(con, dates, orb_name, hour, minute, rr, sl_mode,
                                filter_func, filter_name, filter_desc)
            if result:
                discoveries.append(result)
                print(f"  FOUND: {filter_name} -> {result.filtered_avg_r:+.3f} avg R "
                      f"(+{result.improvement*100:.0f}% vs baseline, {result.filtered_trades} trades)")

    con.close()

    print("\n" + "="*100)
    print("DISCOVERED CONDITIONAL EDGES")
    print("="*100 + "\n")

    if not discoveries:
        print("No conditional edges found meeting criteria (30%+ improvement, 30+ trades)\n")
        return

    # Sort by improvement
    discoveries.sort(key=lambda x: x.improvement, reverse=True)

    print(f"Found {len(discoveries)} conditional edges!\n")
    print(f"{'ORB':<6} {'RR':<5} {'SL':<5} {'Filter':<20} {'Trades':<8} {'WR%':<7} "
          f"{'Filt R':<9} {'Base R':<9} {'Improv':<8} {'Freq%':<7}")
    print("-"*100)

    for d in discoveries[:20]:  # Top 20
        print(f"{d.orb:<6} {d.rr:<5.1f} {d.sl_mode:<5} {d.filter_name:<20} {d.filtered_trades:<8} "
              f"{d.filtered_win_rate*100:<7.1f} {d.filtered_avg_r:<+9.3f} {d.baseline_avg_r:<+9.3f} "
              f"{d.improvement*100:<+8.0f}% {d.freq_pct:<7.1f}")

    print("\n" + "="*100)
    print("TOP 3 UNICORNS:")
    print("="*100)

    for i, d in enumerate(discoveries[:3], 1):
        annual_filtered = d.filtered_avg_r * d.filtered_trades / 2.0
        annual_baseline = d.baseline_avg_r * d.baseline_trades / 2.0

        print(f"\n{i}. {d.orb} ORB RR={d.rr} {d.sl_mode} + {d.filter_name}")
        print(f"   Filter: {d.filter_desc}")
        print(f"   Baseline: {d.baseline_trades} trades, {d.baseline_avg_r:+.3f} avg R (~{annual_baseline:+.0f}R/year)")
        print(f"   Filtered: {d.filtered_trades} trades, {d.filtered_avg_r:+.3f} avg R (~{annual_filtered:+.0f}R/year)")
        print(f"   Improvement: +{d.improvement*100:.0f}%")
        print(f"   Frequency: {d.freq_pct:.1f}% of baseline trades")
        print(f"   Action: When filter TRUE → SIZE UP {d.improvement:.1f}x")

    print("\n" + "="*100)
    print("NEXT STEPS:")
    print("="*100)
    print("1. Validate top discoveries with PROOF scripts")
    print("2. Add filters to validated_setups with conditional sizing rules")
    print("3. Apps can check filters and alert: 'UNICORN SETUP DETECTED - SIZE UP!'")
    print("="*100 + "\n")


if __name__ == "__main__":
    main()
