"""
COMPLETE NON-DESTRUCTIVE AUDIT - 2026-01-15
Automated audit of all strategies, data integrity, and system configuration
READ-ONLY - No modifications made
"""

import duckdb
from datetime import datetime
import os
from pathlib import Path

def banner(text):
    """Print section banner"""
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80 + "\n")

def run_audit():
    """Run complete non-destructive audit"""

    print("\n" + "=" * 80)
    print("COMPLETE NON-DESTRUCTIVE AUDIT")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Status: READ-ONLY (no modifications)")
    print("=" * 80 + "\n")

    results = {
        'timestamp': datetime.now(),
        'checks': [],
        'warnings': [],
        'errors': []
    }

    # Connect to database (read-only)
    try:
        con = duckdb.connect("gold.db", read_only=True)
        results['checks'].append("[OK] Database connection successful (read-only mode)")
    except Exception as e:
        results['errors'].append(f"[ERROR] Database connection failed: {str(e)}")
        return results

    # ========================================================================
    # AUDIT 1: DATABASE INTEGRITY
    # ========================================================================
    banner("AUDIT 1: DATABASE INTEGRITY")

    try:
        # Check tables exist
        tables = con.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        print(f"Tables found: {len(table_names)}")
        for table in sorted(table_names):
            print(f"  - {table}")

        required_tables = ['bars_1m', 'bars_5m', 'daily_features_v2']
        for table in required_tables:
            if table in table_names:
                results['checks'].append(f"[OK] Table exists: {table}")
            else:
                results['errors'].append(f"[ERROR] Missing required table: {table}")

        # Check MGC data volume
        print("\n[DATA] MGC Data Volume:")
        mgc_1m = con.execute("SELECT COUNT(*) FROM bars_1m WHERE symbol='MGC'").fetchone()[0]
        mgc_5m = con.execute("SELECT COUNT(*) FROM bars_5m WHERE symbol='MGC'").fetchone()[0]
        mgc_daily = con.execute("SELECT COUNT(*) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()[0]

        print(f"  - bars_1m: {mgc_1m:,} rows")
        print(f"  - bars_5m: {mgc_5m:,} rows")
        print(f"  - daily_features_v2: {mgc_daily:,} days")

        results['checks'].append(f"[OK] MGC 1m bars: {mgc_1m:,}")
        results['checks'].append(f"[OK] MGC 5m bars: {mgc_5m:,}")
        results['checks'].append(f"[OK] MGC daily features: {mgc_daily:,}")

        # Check date ranges
        print("\n[DATE] Date Ranges:")
        min_date_mgc = con.execute("SELECT MIN(date_local) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()[0]
        max_date_mgc = con.execute("SELECT MAX(date_local) FROM daily_features_v2 WHERE instrument='MGC'").fetchone()[0]
        print(f"  - MGC: {min_date_mgc} to {max_date_mgc}")
        results['checks'].append(f"[OK] MGC date range: {min_date_mgc} to {max_date_mgc}")

        # Check NQ data
        if 'daily_features_v2_nq' in table_names:
            nq_daily = con.execute("SELECT COUNT(*) FROM daily_features_v2_nq").fetchone()[0]
            min_date_nq = con.execute("SELECT MIN(date_local) FROM daily_features_v2_nq").fetchone()[0]
            max_date_nq = con.execute("SELECT MAX(date_local) FROM daily_features_v2_nq").fetchone()[0]
            print(f"  - NQ: {min_date_nq} to {max_date_nq} ({nq_daily} days)")
            results['checks'].append(f"[OK] NQ data available: {nq_daily} days")

    except Exception as e:
        results['errors'].append(f"[ERROR] Database integrity check failed: {str(e)}")

    # ========================================================================
    # AUDIT 2: STRATEGY VALIDATION
    # ========================================================================
    banner("AUDIT 2: STRATEGY VALIDATION (MGC)")

    try:
        print("Validating MGC ORB strategies from database...\n")

        orb_times = ['0900', '1000', '1100', '1800', '2300', '0030']

        for orb in orb_times:
            query = f"""
            SELECT
                COUNT(*) as trades,
                SUM(CASE WHEN orb_{orb}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN orb_{orb}_outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(orb_{orb}_r_multiple) as avg_r
            FROM daily_features_v2
            WHERE instrument = 'MGC'
              AND orb_{orb}_break_dir IS NOT NULL
              AND orb_{orb}_break_dir != 'NONE'
            """

            result = con.execute(query).fetchone()
            if result and result[0] > 0:
                trades, wins, losses, avg_r = result
                win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

                print(f"{orb[:2]}:{orb[2:]} ORB:")
                print(f"  - Trades: {trades}")
                print(f"  - Win Rate: {win_rate*100:.1f}%")
                print(f"  - Avg R: {avg_r:+.3f}R")
                print(f"  - Total R: {avg_r * trades:+.1f}R")

                if avg_r > 0:
                    results['checks'].append(f"[OK] {orb} ORB: {avg_r:+.3f}R ({trades} trades)")
                else:
                    results['warnings'].append(f"[WARN] {orb} ORB: Negative expectancy {avg_r:+.3f}R")
                print()

    except Exception as e:
        results['errors'].append(f"[ERROR] Strategy validation failed: {str(e)}")

    # ========================================================================
    # AUDIT 3: FILE SYSTEM INTEGRITY
    # ========================================================================
    banner("AUDIT 3: FILE SYSTEM INTEGRITY")

    try:
        # Check critical files exist
        critical_files = [
            'validated_strategies.py',
            'app_trading_hub.py',
            'build_daily_features_v2.py',
            'backtest_orb_exec_1m.py',
            'query_engine.py'
        ]

        print("Checking critical files:\n")
        for file in critical_files:
            if os.path.exists(file):
                size = os.path.getsize(file)
                print(f"  [OK] {file} ({size:,} bytes)")
                results['checks'].append(f"[OK] File exists: {file}")
            else:
                print(f"  [ERROR] {file} - MISSING")
                results['errors'].append(f"[ERROR] Missing critical file: {file}")

        # Check validated_strategies.py content
        print("\n[CHECK] Checking validated_strategies.py...")
        if os.path.exists('validated_strategies.py'):
            with open('validated_strategies.py', 'r') as f:
                content = f.read()

            # Check for all ORBs
            for orb in ['0900', '1000', '1100', '1800', '2300', '0030']:
                if f"'{orb}'" in content:
                    results['checks'].append(f"[OK] Strategy defined: {orb} ORB")
                else:
                    results['warnings'].append(f"[WARN] Strategy missing: {orb} ORB")

            # Check for cascades
            if 'Multi-Liquidity Cascades' in content:
                results['checks'].append("[OK] Cascade strategy defined")
            else:
                results['warnings'].append("[WARN] Cascade strategy missing")

            # Check for correlations
            if 'CORRELATION_STRATEGIES' in content:
                results['checks'].append("[OK] Correlation strategies defined")
            else:
                results['warnings'].append("[WARN] Correlation strategies missing")

    except Exception as e:
        results['errors'].append(f"[ERROR] File system check failed: {str(e)}")

    # ========================================================================
    # AUDIT 4: ARCHIVED STRATEGIES
    # ========================================================================
    banner("AUDIT 4: ARCHIVED STRATEGIES CHECK")

    try:
        archive_path = Path("_INVALID_SCRIPTS_ARCHIVE")
        if archive_path.exists():
            archived_files = list(archive_path.glob("*.py"))
            print(f"Found {len(archived_files)} archived scripts:\n")
            for file in archived_files:
                print(f"  - {file.name}")
            results['checks'].append(f"[OK] {len(archived_files)} scripts properly archived")
        else:
            results['warnings'].append("[WARN] Archive directory not found")

    except Exception as e:
        results['errors'].append(f"[ERROR] Archive check failed: {str(e)}")

    # ========================================================================
    # AUDIT 5: CONFIGURATION VALIDATION
    # ========================================================================
    banner("AUDIT 5: CONFIGURATION VALIDATION")

    try:
        # Check .env exists
        if os.path.exists('.env'):
            results['checks'].append("[OK] .env file exists")
            print("[OK] .env file exists")
        else:
            results['warnings'].append("[WARN] .env file missing")
            print("[WARN] .env file missing")

        # Check gold.db
        if os.path.exists('gold.db'):
            db_size = os.path.getsize('gold.db')
            print(f"[OK] gold.db exists ({db_size / 1024 / 1024:.1f} MB)")
            results['checks'].append(f"[OK] Database size: {db_size / 1024 / 1024:.1f} MB")
        else:
            results['errors'].append("[ERROR] gold.db missing")

    except Exception as e:
        results['errors'].append(f"[ERROR] Configuration check failed: {str(e)}")

    # ========================================================================
    # AUDIT SUMMARY
    # ========================================================================
    banner("AUDIT SUMMARY")

    print(f"Total Checks Passed: {len(results['checks'])}")
    print(f"Total Warnings: {len(results['warnings'])}")
    print(f"Total Errors: {len(results['errors'])}")
    print()

    if results['errors']:
        print("[ERROR] ERRORS FOUND:")
        for error in results['errors']:
            print(f"  {error}")
        print()

    if results['warnings']:
        print("[WARN] WARNINGS:")
        for warning in results['warnings']:
            print(f"  {warning}")
        print()

    if not results['errors']:
        print("[OK] AUDIT PASSED - All critical checks successful")
    else:
        print("[ERROR] AUDIT FAILED - Critical errors found")

    # Close database
    con.close()

    return results

if __name__ == "__main__":
    results = run_audit()

    # Write audit log
    log_file = f"AUDIT_LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(log_file, 'w') as f:
        f.write(f"COMPLETE NON-DESTRUCTIVE AUDIT\n")
        f.write(f"Timestamp: {results['timestamp']}\n")
        f.write(f"\n{'='*80}\n")
        f.write(f"SUMMARY\n")
        f.write(f"{'='*80}\n\n")
        f.write(f"Checks Passed: {len(results['checks'])}\n")
        f.write(f"Warnings: {len(results['warnings'])}\n")
        f.write(f"Errors: {len(results['errors'])}\n\n")

        if results['checks']:
            f.write(f"\n{'='*80}\n")
            f.write("PASSED CHECKS\n")
            f.write(f"{'='*80}\n\n")
            for check in results['checks']:
                f.write(f"{check}\n")

        if results['warnings']:
            f.write(f"\n{'='*80}\n")
            f.write("WARNINGS\n")
            f.write(f"{'='*80}\n\n")
            for warning in results['warnings']:
                f.write(f"{warning}\n")

        if results['errors']:
            f.write(f"\n{'='*80}\n")
            f.write("ERRORS\n")
            f.write(f"{'='*80}\n\n")
            for error in results['errors']:
                f.write(f"{error}\n")

    print(f"\n[LOG] Audit log written to: {log_file}")
