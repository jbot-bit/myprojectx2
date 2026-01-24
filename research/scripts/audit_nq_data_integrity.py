"""
Audit NQ Data Integrity
========================

Validates bars_1m_nq and bars_5m_nq data integrity:
- Date range coverage
- Gap detection (missing minutes)
- Timezone conversion sanity checks
- Duplicate detection
- Contract roll presence
- Sample data validation

Usage:
  python scripts/audit_nq_data_integrity.py

Output:
  outputs/NQ_DATA_AUDIT.md
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import duckdb

# Configuration
DB_PATH = "gold.db"
SYMBOL = "NQ"
TZ_LOCAL = ZoneInfo("Australia/Brisbane")
TZ_UTC = ZoneInfo("UTC")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "NQ_DATA_AUDIT.md"


def log(msg: str):
    """Print timestamped message"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def run_audit(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Run comprehensive data integrity audit

    Returns:
        Dict with audit results
    """
    results = {}

    # 1. Basic counts
    log("Checking basic counts...")
    count_1m = con.execute("SELECT COUNT(*) FROM bars_1m_nq WHERE symbol = ?", [SYMBOL]).fetchone()[0]
    count_5m = con.execute("SELECT COUNT(*) FROM bars_5m_nq WHERE symbol = ?", [SYMBOL]).fetchone()[0]

    results['count_1m'] = count_1m
    results['count_5m'] = count_5m
    results['expected_5m'] = count_1m // 5
    results['5m_ratio_ok'] = abs(count_5m - (count_1m // 5)) <= 5  # Allow small difference

    # 2. Date range
    log("Checking date range...")
    date_range_1m = con.execute("""
        SELECT MIN(ts_utc), MAX(ts_utc)
        FROM bars_1m_nq
        WHERE symbol = ?
    """, [SYMBOL]).fetchone()

    date_range_5m = con.execute("""
        SELECT MIN(ts_utc), MAX(ts_utc)
        FROM bars_5m_nq
        WHERE symbol = ?
    """, [SYMBOL]).fetchone()

    results['start_utc_1m'] = str(date_range_1m[0]) if date_range_1m[0] else None
    results['end_utc_1m'] = str(date_range_1m[1]) if date_range_1m[1] else None
    results['start_utc_5m'] = str(date_range_5m[0]) if date_range_5m[0] else None
    results['end_utc_5m'] = str(date_range_5m[1]) if date_range_5m[1] else None

    # Calculate expected vs actual days
    if date_range_1m[0] and date_range_1m[1]:
        start_dt = date_range_1m[0]
        end_dt = date_range_1m[1]
        total_days = (end_dt - start_dt).days + 1
        results['total_days'] = total_days

        # Expected minutes: ~1440 per day for 24/5 markets (less on weekends)
        # NQ trades ~23 hours/day, 6 days/week
        expected_minutes = total_days * 1380  # Conservative estimate
        results['expected_minutes'] = expected_minutes
        results['coverage_pct'] = (count_1m / expected_minutes) * 100 if expected_minutes > 0 else 0

    # 3. Contract rolls
    log("Checking contract rolls...")
    contracts = con.execute("""
        SELECT DISTINCT source_symbol
        FROM bars_1m_nq
        WHERE symbol = ? AND source_symbol IS NOT NULL
        ORDER BY source_symbol
    """, [SYMBOL]).fetchall()

    results['unique_contracts'] = len(contracts)
    results['contracts_list'] = [c[0] for c in contracts]

    # Get contract transition dates
    contract_transitions = con.execute("""
        SELECT
            DATE(ts_utc AT TIME ZONE 'Australia/Brisbane') as date_local,
            source_symbol,
            COUNT(*) as bars
        FROM bars_1m_nq
        WHERE symbol = ? AND source_symbol IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, [SYMBOL]).fetchall()

    results['contract_transitions'] = contract_transitions[:20]  # First 20 days

    # 4. Duplicates
    log("Checking for duplicates...")
    duplicates = con.execute("""
        SELECT ts_utc, symbol, COUNT(*) as cnt
        FROM bars_1m_nq
        WHERE symbol = ?
        GROUP BY ts_utc, symbol
        HAVING COUNT(*) > 1
    """, [SYMBOL]).fetchall()

    results['duplicates'] = len(duplicates)
    results['duplicate_samples'] = duplicates[:5]  # First 5 if any

    # 5. Gap analysis
    log("Checking for gaps...")
    gaps = con.execute("""
        WITH minute_series AS (
            SELECT
                ts_utc,
                LEAD(ts_utc) OVER (ORDER BY ts_utc) as next_ts
            FROM bars_1m_nq
            WHERE symbol = ?
        )
        SELECT
            ts_utc,
            next_ts,
            EXTRACT(EPOCH FROM (next_ts - ts_utc)) / 60.0 as gap_minutes
        FROM minute_series
        WHERE next_ts IS NOT NULL
          AND EXTRACT(EPOCH FROM (next_ts - ts_utc)) > 120  -- Gaps > 2 minutes
        ORDER BY gap_minutes DESC
        LIMIT 20
    """, [SYMBOL]).fetchall()

    results['large_gaps'] = len(gaps)
    results['gap_samples'] = gaps[:10]  # Top 10 largest gaps

    # 6. Timezone sanity check
    log("Checking timezone conversion...")
    sample_times = con.execute("""
        SELECT
            ts_utc,
            ts_utc AT TIME ZONE 'Australia/Brisbane' as ts_local,
            EXTRACT(HOUR FROM (ts_utc AT TIME ZONE 'Australia/Brisbane')) as hour_local
        FROM bars_1m_nq
        WHERE symbol = ?
        ORDER BY ts_utc
        LIMIT 10
    """, [SYMBOL]).fetchall()

    results['timezone_samples'] = sample_times

    # 7. Price sanity check
    log("Checking price ranges...")
    price_stats = con.execute("""
        SELECT
            MIN(low) as min_price,
            MAX(high) as max_price,
            AVG(close) as avg_price,
            STDDEV(close) as stddev_price
        FROM bars_1m_nq
        WHERE symbol = ?
    """, [SYMBOL]).fetchone()

    results['min_price'] = price_stats[0]
    results['max_price'] = price_stats[1]
    results['avg_price'] = price_stats[2]
    results['stddev_price'] = price_stats[3]

    # Detect any zero/negative prices (would be error)
    bad_prices = con.execute("""
        SELECT COUNT(*)
        FROM bars_1m_nq
        WHERE symbol = ? AND (open <= 0 OR high <= 0 OR low <= 0 OR close <= 0)
    """, [SYMBOL]).fetchone()[0]

    results['bad_prices'] = bad_prices

    # 8. Volume sanity
    log("Checking volume distribution...")
    volume_stats = con.execute("""
        SELECT
            MIN(volume) as min_vol,
            MAX(volume) as max_vol,
            AVG(volume) as avg_vol,
            COUNT(CASE WHEN volume = 0 THEN 1 END) as zero_vol_count
        FROM bars_1m_nq
        WHERE symbol = ?
    """, [SYMBOL]).fetchone()

    results['min_volume'] = volume_stats[0]
    results['max_volume'] = volume_stats[1]
    results['avg_volume'] = volume_stats[2]
    results['zero_volume_bars'] = volume_stats[3]

    # 9. Sample data for manual inspection
    log("Collecting sample data...")
    samples = con.execute("""
        SELECT *
        FROM bars_1m_nq
        WHERE symbol = ?
        ORDER BY ts_utc
        LIMIT 5
    """, [SYMBOL]).fetchall()

    results['sample_bars'] = samples

    return results


def generate_report(results: dict) -> str:
    """Generate markdown audit report"""

    report = []
    report.append("# NQ DATA INTEGRITY AUDIT")
    report.append("")
    report.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Database**: {DB_PATH}")
    report.append(f"**Symbol**: {SYMBOL}")
    report.append("")
    report.append("---")
    report.append("")

    # Summary
    report.append("## SUMMARY")
    report.append("")
    report.append(f"- bars_1m_nq: **{results['count_1m']:,}** rows")
    report.append(f"- bars_5m_nq: **{results['count_5m']:,}** rows")
    report.append(f"- Date range: **{results.get('start_utc_1m', 'N/A')}** to **{results.get('end_utc_1m', 'N/A')}**")
    report.append(f"- Total days: **{results.get('total_days', 'N/A')}**")
    report.append(f"- Unique contracts: **{results['unique_contracts']}**")
    report.append("")

    # Integrity checks
    report.append("## INTEGRITY CHECKS")
    report.append("")

    # 1. 5m aggregation
    report.append("### 1. 5-Minute Aggregation")
    report.append("")
    status = "[OK]" if results['5m_ratio_ok'] else "[WARN]"
    report.append(f"{status} Expected ~{results['expected_5m']:,} bars, found {results['count_5m']:,}")
    report.append("")

    # 2. Duplicates
    report.append("### 2. Duplicates")
    report.append("")
    status = "[OK]" if results['duplicates'] == 0 else "[ERROR]"
    report.append(f"{status} Found {results['duplicates']} duplicate timestamps")
    if results['duplicate_samples']:
        report.append("")
        report.append("Sample duplicates:")
        for dup in results['duplicate_samples']:
            report.append(f"  - {dup}")
    report.append("")

    # 3. Gaps
    report.append("### 3. Time Gaps")
    report.append("")
    report.append(f"Found {results['large_gaps']} gaps > 2 minutes")
    if results['gap_samples']:
        report.append("")
        report.append("Largest gaps (minutes):")
        for gap in results['gap_samples']:
            report.append(f"  - {gap[0]} -> {gap[1]}: {gap[2]:.0f} minutes")
    report.append("")

    # 4. Price sanity
    report.append("### 4. Price Sanity")
    report.append("")
    status = "[OK]" if results['bad_prices'] == 0 else "[ERROR]"
    report.append(f"{status} Bad prices (<=0): {results['bad_prices']}")
    report.append(f"  - Min: {results['min_price']:.2f}")
    report.append(f"  - Max: {results['max_price']:.2f}")
    report.append(f"  - Avg: {results['avg_price']:.2f}")
    report.append(f"  - StdDev: {results['stddev_price']:.2f}")
    report.append("")

    # 5. Volume sanity
    report.append("### 5. Volume Sanity")
    report.append("")
    zero_pct = (results['zero_volume_bars'] / results['count_1m']) * 100 if results['count_1m'] > 0 else 0
    status = "[WARN]" if zero_pct > 5 else "[OK]"
    report.append(f"{status} Zero volume bars: {results['zero_volume_bars']:,} ({zero_pct:.1f}%)")
    report.append(f"  - Min: {results['min_volume']:,}")
    report.append(f"  - Max: {results['max_volume']:,}")
    report.append(f"  - Avg: {results['avg_volume']:.0f}")
    report.append("")

    # 6. Coverage
    report.append("### 6. Data Coverage")
    report.append("")
    coverage = results.get('coverage_pct', 0)
    status = "[OK]" if coverage > 80 else "[WARN]" if coverage > 50 else "[ERROR]"
    report.append(f"{status} Coverage: {coverage:.1f}% of expected bars")
    report.append(f"  - Expected: ~{results.get('expected_minutes', 0):,} bars (conservative)")
    report.append(f"  - Actual: {results['count_1m']:,} bars")
    report.append("")

    # Contract rolls
    report.append("## CONTRACT ROLLS")
    report.append("")
    report.append(f"Unique contracts: {results['unique_contracts']}")
    report.append("")
    report.append("Contracts found:")
    for contract in results['contracts_list']:
        report.append(f"  - {contract}")
    report.append("")

    # Timezone samples
    report.append("## TIMEZONE VERIFICATION")
    report.append("")
    report.append("Sample timestamps (UTC -> Brisbane UTC+10):")
    report.append("")
    for sample in results['timezone_samples'][:5]:
        report.append(f"  - UTC: {sample[0]} -> Local: {sample[1]} (hour={sample[2]})")
    report.append("")

    # Sample data
    report.append("## SAMPLE DATA")
    report.append("")
    report.append("First 5 bars:")
    report.append("")
    for bar in results['sample_bars']:
        report.append(f"  - {bar[0]} | {bar[2]} | O={bar[3]:.2f} H={bar[4]:.2f} L={bar[5]:.2f} C={bar[6]:.2f} V={bar[7]:,}")
    report.append("")

    # Final verdict
    report.append("---")
    report.append("")
    report.append("## VERDICT")
    report.append("")

    critical_errors = []
    warnings = []

    if results['duplicates'] > 0:
        critical_errors.append(f"Duplicate timestamps: {results['duplicates']}")
    if results['bad_prices'] > 0:
        critical_errors.append(f"Bad prices (<=0): {results['bad_prices']}")
    if results.get('coverage_pct', 0) < 50:
        critical_errors.append(f"Low coverage: {results.get('coverage_pct', 0):.1f}%")

    if results['zero_volume_bars'] / results['count_1m'] > 0.05:
        warnings.append(f"High zero-volume bars: {(results['zero_volume_bars'] / results['count_1m']) * 100:.1f}%")
    if not results['5m_ratio_ok']:
        warnings.append("5m bar count mismatch")

    if critical_errors:
        report.append("[ERROR] CRITICAL ISSUES FOUND:")
        for err in critical_errors:
            report.append(f"  - {err}")
        report.append("")

    if warnings:
        report.append("[WARN] WARNINGS:")
        for warn in warnings:
            report.append(f"  - {warn}")
        report.append("")

    if not critical_errors and not warnings:
        report.append("[OK] DATA INTEGRITY VERIFIED")
        report.append("")
        report.append("All checks passed. Data is ready for feature engineering and backtesting.")
        report.append("")

    return "\n".join(report)


def main():
    log("NQ Data Integrity Audit Started")
    log(f"  Database: {DB_PATH}")
    log(f"  Symbol: {SYMBOL}")
    log("")

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Connect to database
    con = duckdb.connect(DB_PATH)

    try:
        # Run audit
        results = run_audit(con)

        # Generate report
        log("Generating report...")
        report = generate_report(results)

        # Write report
        OUTPUT_FILE.write_text(report, encoding='utf-8')
        log(f"Report written to: {OUTPUT_FILE}")
        log("")

        # Print report to console
        print(report)

        log("\n[OK] Audit complete!")

    except Exception as e:
        log(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        con.close()


if __name__ == "__main__":
    main()
