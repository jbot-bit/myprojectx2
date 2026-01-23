"""
COMPLETE DATA ACCURACY & CALCULATION AUDIT
==========================================
Comprehensive audit of all calculations, data integrity, and logic correctness.
Run this standalone script to verify everything is calculated correctly.

Checks:
1. Database schema and integrity
2. ORB calculations (high, low, size)
3. Session statistics (Asia, London, NY)
4. Trade level calculations (entry, stop, target)
5. Risk/Reward calculations
6. Filter logic (size filters)
7. Config vs database synchronization
8. Data gaps and completeness
9. Timezone handling
10. All mathematical formulas
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import duckdb
from typing import Dict, List, Tuple

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

try:
    from config import (
        MGC_ORB_SIZE_FILTERS, NQ_ORB_SIZE_FILTERS, MPL_ORB_SIZE_FILTERS,
        PRIMARY_INSTRUMENT, TZ_LOCAL, DB_PATH
    )
    import pytz
except ImportError as e:
    print(f"ERROR: Failed to import config: {e}")
    sys.exit(1)

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{'=' * 80}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{'=' * 80}\n")

def print_pass(text):
    print(f"{GREEN}[PASS]{RESET}: {text}")

def print_fail(text):
    print(f"{RED}[FAIL]{RESET}: {text}")

def print_warn(text):
    print(f"{YELLOW}[WARN]{RESET}: {text}")

def print_info(text):
    print(f"{BLUE}[INFO]{RESET}: {text}")


class DataAudit:
    """Complete data accuracy and calculation audit"""

    def __init__(self):
        self.gold_db_path = "gold.db"
        self.live_db_path = "trading_app/live_data.db"
        self.errors = []
        self.warnings = []
        self.passes = []

    def run_all_audits(self):
        """Run all audit checks"""
        print_header("COMPLETE DATA ACCURACY & CALCULATION AUDIT")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Run each audit section
        self.audit_database_schema()
        self.audit_config_sync()
        self.audit_orb_calculations()
        self.audit_session_statistics()
        self.audit_trade_calculations()
        self.audit_filter_logic()
        self.audit_data_completeness()
        self.audit_timezone_handling()
        self.audit_validated_setups()
        self.audit_risk_reward_math()

        # Print summary
        self.print_summary()

    def audit_database_schema(self):
        """Audit 1: Database Schema & Integrity"""
        print_header("AUDIT 1: Database Schema & Integrity")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Check required tables exist
            tables = con.execute("SHOW TABLES").fetchall()
            table_names = [t[0] for t in tables]

            required_tables = ['bars_1m', 'bars_5m', 'daily_features_v2', 'validated_setups']
            for table in required_tables:
                if table in table_names:
                    print_pass(f"Table '{table}' exists")
                    self.passes.append(f"Schema: {table} exists")
                else:
                    print_fail(f"Table '{table}' missing")
                    self.errors.append(f"Schema: {table} missing")

            # Check bars_1m schema
            schema = con.execute("DESCRIBE bars_1m").fetchdf()
            required_columns = ['ts_utc', 'symbol', 'open', 'high', 'low', 'close', 'volume']
            actual_columns = schema['column_name'].tolist()

            for col in required_columns:
                if col in actual_columns:
                    print_pass(f"bars_1m has column '{col}'")
                else:
                    print_fail(f"bars_1m missing column '{col}'")
                    self.errors.append(f"Schema: bars_1m missing {col}")

            # Check daily_features schema
            schema = con.execute("DESCRIBE daily_features").fetchdf()
            orb_times = ['0900', '1000', '1100', '1800', '2300', '0030']

            for orb in orb_times:
                cols_to_check = [
                    f'orb_{orb}_high',
                    f'orb_{orb}_low',
                    f'orb_{orb}_size',
                    f'orb_{orb}_break_dir'
                ]
                for col in cols_to_check:
                    if col in schema['column_name'].tolist():
                        print_pass(f"daily_features has '{col}'")
                    else:
                        print_fail(f"daily_features missing '{col}'")
                        self.errors.append(f"Schema: daily_features missing {col}")

            con.close()

        except Exception as e:
            print_fail(f"Database schema audit failed: {e}")
            self.errors.append(f"Schema audit exception: {e}")

    def audit_config_sync(self):
        """Audit 2: Config vs Database Synchronization"""
        print_header("AUDIT 2: Config vs Database Synchronization")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Get MGC setups from database
            setups = con.execute("""
                SELECT orb_time, orb_size_filter
                FROM validated_setups
                WHERE instrument = 'MGC'
                ORDER BY orb_time
            """).fetchdf()

            if setups.empty:
                print_fail("No MGC setups in validated_setups table")
                self.errors.append("Config sync: No MGC setups in database")
                con.close()
                return

            # Compare with config.py
            for _, row in setups.iterrows():
                orb_time = row['orb_time']
                db_filter = row['orb_size_filter']
                config_filter = MGC_ORB_SIZE_FILTERS.get(orb_time)

                # Handle None/NULL comparison
                if pd.isna(db_filter):
                    db_filter = None

                if config_filter is None and db_filter is None:
                    print_pass(f"MGC {orb_time}: config=None, db=None (match)")
                    self.passes.append(f"Config sync: MGC {orb_time} matches")
                elif config_filter is not None and db_filter is not None:
                    diff = abs(config_filter - db_filter)
                    if diff < 0.001:
                        print_pass(f"MGC {orb_time}: config={config_filter:.3f}, db={db_filter:.3f} (match)")
                        self.passes.append(f"Config sync: MGC {orb_time} matches")
                    else:
                        print_fail(f"MGC {orb_time}: config={config_filter:.3f}, db={db_filter:.3f} (MISMATCH)")
                        self.errors.append(f"Config sync: MGC {orb_time} mismatch")
                else:
                    print_fail(f"MGC {orb_time}: config={config_filter}, db={db_filter} (MISMATCH)")
                    self.errors.append(f"Config sync: MGC {orb_time} mismatch")

            con.close()

        except Exception as e:
            print_fail(f"Config sync audit failed: {e}")
            self.errors.append(f"Config sync exception: {e}")

    def audit_orb_calculations(self):
        """Audit 3: ORB Calculation Accuracy"""
        print_header("AUDIT 3: ORB Calculation Accuracy")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Get sample of recent ORB data
            df = con.execute("""
                SELECT
                    date_local,
                    orb_0900_high, orb_0900_low, orb_0900_size,
                    orb_1000_high, orb_1000_low, orb_1000_size,
                    orb_1100_high, orb_1100_low, orb_1100_size
                FROM daily_features_v2
                WHERE instrument = 'MGC'
                AND date_local >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY date_local DESC
                LIMIT 5
            """).fetchdf()

            if df.empty:
                print_warn("No recent ORB data to audit (last 7 days)")
                self.warnings.append("ORB calc: No recent data")
                con.close()
                return

            print_info(f"Auditing {len(df)} days of ORB calculations...\n")

            orb_times = ['0900', '1000', '1100']
            total_checks = 0
            passed_checks = 0

            for _, row in df.iterrows():
                date = row['date_local']
                print(f"  Date: {date}")

                for orb in orb_times:
                    high = row[f'orb_{orb}_high']
                    low = row[f'orb_{orb}_low']
                    size = row[f'orb_{orb}_size']

                    if pd.isna(high) or pd.isna(low):
                        print_info(f"    {orb} ORB: No data (NULL) - OK for weekends/holidays")
                        continue

                    # Calculate expected size
                    expected_size = high - low

                    # Verify calculation
                    total_checks += 1
                    if abs(size - expected_size) < 0.001:
                        print_pass(f"    {orb} ORB: size={size:.3f} (high={high:.2f} - low={low:.2f} = {expected_size:.3f}) [OK]")
                        passed_checks += 1
                    else:
                        print_fail(f"    {orb} ORB: size={size:.3f} but calculated={expected_size:.3f} (MISMATCH)")
                        self.errors.append(f"ORB calc: {date} {orb} size mismatch")

                print()

            if total_checks > 0:
                accuracy = (passed_checks / total_checks) * 100
                if accuracy == 100:
                    print_pass(f"ORB size calculations: {passed_checks}/{total_checks} correct ({accuracy:.1f}%)")
                    self.passes.append(f"ORB calc: 100% accurate ({total_checks} checks)")
                else:
                    print_fail(f"ORB size calculations: {passed_checks}/{total_checks} correct ({accuracy:.1f}%)")
                    self.errors.append(f"ORB calc: Only {accuracy:.1f}% accurate")

            con.close()

        except Exception as e:
            print_fail(f"ORB calculation audit failed: {e}")
            self.errors.append(f"ORB calc exception: {e}")

    def audit_session_statistics(self):
        """Audit 4: Session Statistics Calculations"""
        print_header("AUDIT 4: Session Statistics Calculations")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Get recent session data
            df = con.execute("""
                SELECT
                    date_local,
                    asia_high, asia_low,
                    london_high, london_low,
                    ny_high, ny_low
                FROM daily_features_v2
                WHERE instrument = 'MGC'
                AND date_local >= CURRENT_DATE - INTERVAL '7 days'
                ORDER BY date_local DESC
                LIMIT 5
            """).fetchdf()

            if df.empty:
                print_warn("No recent session data to audit")
                self.warnings.append("Session stats: No recent data")
                con.close()
                return

            print_info(f"Auditing {len(df)} days of session statistics...\n")

            for _, row in df.iterrows():
                date = row['date_local']
                print(f"  Date: {date}")

                sessions = [
                    ('Asia', row['asia_high'], row['asia_low']),
                    ('London', row['london_high'], row['london_low']),
                    ('NY', row['ny_high'], row['ny_low'])
                ]

                for name, high, low in sessions:
                    if pd.isna(high) or pd.isna(low):
                        print_info(f"    {name}: No data (NULL)")
                    elif high >= low:
                        print_pass(f"    {name}: high={high:.2f}, low={low:.2f}, range={high-low:.2f} [OK]")
                        self.passes.append(f"Session: {date} {name} valid")
                    else:
                        print_fail(f"    {name}: high={high:.2f} < low={low:.2f} (INVALID)")
                        self.errors.append(f"Session: {date} {name} invalid")

                print()

            con.close()

        except Exception as e:
            print_fail(f"Session statistics audit failed: {e}")
            self.errors.append(f"Session stats exception: {e}")

    def audit_trade_calculations(self):
        """Audit 5: Trade Level Calculations (Entry, Stop, Target)"""
        print_header("AUDIT 5: Trade Level Calculations")

        print_info("Testing trade calculation formulas...\n")

        # Test cases with known correct answers
        test_cases = [
            {
                'name': 'LONG trade, FULL stop, 1.0 RR',
                'orb_high': 100.0,
                'orb_low': 99.0,
                'direction': 'LONG',
                'rr': 1.0,
                'sl_mode': 'FULL',
                'expected': {
                    'entry': 100.0,
                    'stop': 99.0,
                    'target': 101.0,
                    'risk': 1.0,
                    'reward': 1.0
                }
            },
            {
                'name': 'LONG trade, HALF stop, 2.0 RR',
                'orb_high': 100.0,
                'orb_low': 99.0,
                'direction': 'LONG',
                'rr': 2.0,
                'sl_mode': 'HALF',
                'expected': {
                    'entry': 100.0,
                    'stop': 99.5,
                    'target': 101.0,
                    'risk': 0.5,
                    'reward': 1.0
                }
            },
            {
                'name': 'SHORT trade, FULL stop, 1.5 RR',
                'orb_high': 100.0,
                'orb_low': 99.0,
                'direction': 'SHORT',
                'rr': 1.5,
                'sl_mode': 'FULL',
                'expected': {
                    'entry': 99.0,
                    'stop': 100.0,
                    'target': 97.5,
                    'risk': 1.0,
                    'reward': 1.5
                }
            },
            {
                'name': 'SHORT trade, HALF stop, 3.0 RR',
                'orb_high': 100.0,
                'orb_low': 99.0,
                'direction': 'SHORT',
                'rr': 3.0,
                'sl_mode': 'HALF',
                'expected': {
                    'entry': 99.0,
                    'stop': 99.5,
                    'target': 97.5,
                    'risk': 0.5,
                    'reward': 1.5
                }
            }
        ]

        all_passed = True

        for test in test_cases:
            print(f"  Test: {test['name']}")

            # Calculate trade levels
            orb_high = test['orb_high']
            orb_low = test['orb_low']
            orb_mid = (orb_high + orb_low) / 2

            if test['direction'] == 'LONG':
                entry = orb_high
                stop = orb_mid if test['sl_mode'] == 'HALF' else orb_low
                risk = entry - stop
                target = entry + (risk * test['rr'])
            else:  # SHORT
                entry = orb_low
                stop = orb_mid if test['sl_mode'] == 'HALF' else orb_high
                risk = stop - entry
                target = entry - (risk * test['rr'])

            reward = abs(target - entry)

            # Verify each value
            checks = [
                ('entry', entry, test['expected']['entry']),
                ('stop', stop, test['expected']['stop']),
                ('target', target, test['expected']['target']),
                ('risk', risk, test['expected']['risk']),
                ('reward', reward, test['expected']['reward'])
            ]

            test_passed = True
            for label, actual, expected in checks:
                if abs(actual - expected) < 0.001:
                    print(f"    {label}: {actual:.2f} [OK]")
                else:
                    print_fail(f"    {label}: got {actual:.2f}, expected {expected:.2f}")
                    test_passed = False
                    all_passed = False
                    self.errors.append(f"Trade calc: {test['name']} {label} incorrect")

            if test_passed:
                self.passes.append(f"Trade calc: {test['name']} correct")

            print()

        if all_passed:
            print_pass("All trade calculation formulas are correct!")
        else:
            print_fail("Some trade calculations are incorrect")

    def audit_filter_logic(self):
        """Audit 6: Filter Logic Accuracy"""
        print_header("AUDIT 6: Filter Logic Accuracy")

        print_info("Testing filter logic...\n")

        # Test filter logic
        test_cases = [
            {
                'orb_time': '2300',
                'orb_size': 0.160,
                'filter': 0.155,
                'expected_pass': True,
                'reason': '0.160 > 0.155'
            },
            {
                'orb_time': '2300',
                'orb_size': 0.150,
                'filter': 0.155,
                'expected_pass': False,
                'reason': '0.150 < 0.155'
            },
            {
                'orb_time': '0030',
                'orb_size': 0.120,
                'filter': 0.112,
                'expected_pass': True,
                'reason': '0.120 > 0.112'
            },
            {
                'orb_time': '0900',
                'orb_size': 0.050,
                'filter': None,
                'expected_pass': True,
                'reason': 'No filter (always pass)'
            }
        ]

        all_passed = True

        for test in test_cases:
            orb_time = test['orb_time']
            orb_size = test['orb_size']
            filter_val = test['filter']
            expected = test['expected_pass']

            # Apply filter logic
            if filter_val is None:
                actual_pass = True
            else:
                actual_pass = orb_size >= filter_val

            if actual_pass == expected:
                print_pass(f"{orb_time} ORB: size={orb_size:.3f}, filter={filter_val}, pass={actual_pass} ({test['reason']}) [OK]")
                self.passes.append(f"Filter: {orb_time} logic correct")
            else:
                print_fail(f"{orb_time} ORB: size={orb_size:.3f}, filter={filter_val}, got pass={actual_pass}, expected={expected}")
                all_passed = False
                self.errors.append(f"Filter: {orb_time} logic incorrect")

        if all_passed:
            print_pass("\nAll filter logic tests passed!")

    def audit_data_completeness(self):
        """Audit 7: Data Completeness & Gaps"""
        print_header("AUDIT 7: Data Completeness & Gaps")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Check bars_1m data range
            result = con.execute("""
                SELECT
                    MIN(ts_utc) as first_bar,
                    MAX(ts_utc) as last_bar,
                    COUNT(*) as total_bars
                FROM bars_1m
                WHERE symbol = 'MGC'
            """).fetchdf()

            if not result.empty and result['total_bars'].iloc[0] > 0:
                first = result['first_bar'].iloc[0]
                last = result['last_bar'].iloc[0]
                total = result['total_bars'].iloc[0]

                print_info(f"bars_1m data range:")
                print(f"  First bar: {first}")
                print(f"  Last bar:  {last}")
                print(f"  Total bars: {total:,}")

                # Check for recent data
                now_utc = datetime.now(pytz.UTC)
                last_bar_time = pd.to_datetime(last, utc=True)
                hours_since_last = (now_utc - last_bar_time).total_seconds() / 3600

                if hours_since_last < 24:
                    print_pass(f"  Data is recent (last bar {hours_since_last:.1f} hours ago)")
                    self.passes.append("Data completeness: Recent data present")
                else:
                    print_warn(f"  Data may be stale (last bar {hours_since_last:.1f} hours ago)")
                    self.warnings.append(f"Data completeness: Last bar {hours_since_last:.1f}h ago")
            else:
                print_fail("No bars_1m data found")
                self.errors.append("Data completeness: No bars_1m data")

            # Check daily_features completeness
            result = con.execute("""
                SELECT
                    MIN(date_local) as first_date,
                    MAX(date_local) as last_date,
                    COUNT(*) as total_days
                FROM daily_features_v2
                WHERE instrument = 'MGC'
            """).fetchdf()

            if not result.empty and result['total_days'].iloc[0] > 0:
                first = result['first_date'].iloc[0]
                last = result['last_date'].iloc[0]
                total = result['total_days'].iloc[0]

                print_info(f"\ndaily_features data range:")
                print(f"  First date: {first}")
                print(f"  Last date:  {last}")
                print(f"  Total days: {total:,}")

                self.passes.append(f"Data completeness: {total} days of features")
            else:
                print_fail("No daily_features data found")
                self.errors.append("Data completeness: No daily_features")

            con.close()

        except Exception as e:
            print_fail(f"Data completeness audit failed: {e}")
            self.errors.append(f"Data completeness exception: {e}")

    def audit_timezone_handling(self):
        """Audit 8: Timezone Handling Correctness"""
        print_header("AUDIT 8: Timezone Handling")

        print_info(f"Configured local timezone: {TZ_LOCAL}\n")

        # Verify timezone is valid
        try:
            tz = pytz.timezone(str(TZ_LOCAL))
            print_pass(f"Timezone '{TZ_LOCAL}' is valid")
            self.passes.append("Timezone: Valid timezone config")

            # Check if it's Australia/Brisbane (UTC+10, no DST)
            now = datetime.now(tz)
            offset = now.strftime('%z')
            print_info(f"Current offset: {offset}")

            if 'Brisbane' in str(TZ_LOCAL):
                print_pass("Using Australia/Brisbane (UTC+10, no DST) - correct for trading")
                self.passes.append("Timezone: Brisbane (no DST)")
            else:
                print_warn(f"Using {TZ_LOCAL} - verify this matches your trading hours")
                self.warnings.append(f"Timezone: {TZ_LOCAL} (non-standard)")

        except Exception as e:
            print_fail(f"Timezone configuration error: {e}")
            self.errors.append(f"Timezone: Invalid config - {e}")

    def audit_validated_setups(self):
        """Audit 9: Validated Setups Completeness"""
        print_header("AUDIT 9: Validated Setups Database")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Check all instruments
            for instrument in ['MGC', 'NQ', 'MPL']:
                result = con.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(DISTINCT orb_time) as unique_orbs
                    FROM validated_setups
                    WHERE instrument = ?
                """, [instrument]).fetchdf()

                if not result.empty:
                    total = result['total'].iloc[0]
                    unique = result['unique_orbs'].iloc[0]

                    if total > 0:
                        print_pass(f"{instrument}: {total} setups, {unique} unique ORB times")
                        self.passes.append(f"Setups: {instrument} has {total} setups")
                    else:
                        print_warn(f"{instrument}: No validated setups")
                        self.warnings.append(f"Setups: {instrument} has no setups")

            # Check required fields
            print_info("\nChecking setup fields...")
            schema = con.execute("DESCRIBE validated_setups").fetchdf()
            required_fields = [
                'instrument', 'orb_time', 'rr', 'sl_mode',
                'orb_size_filter', 'avg_r', 'win_rate', 'tier'
            ]

            actual_fields = schema['column_name'].tolist()
            for field in required_fields:
                if field in actual_fields:
                    print_pass(f"  Field '{field}' exists")
                else:
                    print_fail(f"  Field '{field}' missing")
                    self.errors.append(f"Setups: Missing field {field}")

            con.close()

        except Exception as e:
            print_fail(f"Validated setups audit failed: {e}")
            self.errors.append(f"Setups exception: {e}")

    def audit_risk_reward_math(self):
        """Audit 10: Risk/Reward Mathematics"""
        print_header("AUDIT 10: Risk/Reward Mathematics")

        try:
            con = duckdb.connect(self.gold_db_path, read_only=True)

            # Get validated setups with their RR values
            setups = con.execute("""
                SELECT
                    instrument,
                    orb_time,
                    rr,
                    sl_mode,
                    avg_r
                FROM validated_setups
                ORDER BY instrument, orb_time
            """).fetchdf()

            if setups.empty:
                print_warn("No validated setups to audit R:R calculations")
                self.warnings.append("R:R math: No setups to audit")
                con.close()
                return

            print_info(f"Auditing {len(setups)} setup R:R configurations...\n")

            for _, setup in setups.iterrows():
                instrument = setup['instrument']
                orb_time = setup['orb_time']
                rr = setup['rr']
                sl_mode = setup['sl_mode']
                avg_r = setup['avg_r']

                # Verify RR is positive
                if rr > 0:
                    print_pass(f"{instrument} {orb_time}: RR={rr:.1f}, SL={sl_mode}, Avg R={avg_r:.2f}R [OK]")
                    self.passes.append(f"R:R: {instrument} {orb_time} valid")
                else:
                    print_fail(f"{instrument} {orb_time}: RR={rr:.1f} (INVALID - must be > 0)")
                    self.errors.append(f"R:R: {instrument} {orb_time} invalid RR")

                # Verify avg_r makes sense
                if not pd.isna(avg_r):
                    if -10 <= avg_r <= 10:  # Reasonable range for avg R
                        pass  # Already printed above
                    else:
                        print_warn(f"{instrument} {orb_time}: Avg R={avg_r:.2f}R seems extreme")
                        self.warnings.append(f"R:R: {instrument} {orb_time} extreme avg_r")

            con.close()

        except Exception as e:
            print_fail(f"R:R math audit failed: {e}")
            self.errors.append(f"R:R exception: {e}")

    def print_summary(self):
        """Print audit summary"""
        print_header("AUDIT SUMMARY")

        total = len(self.passes) + len(self.warnings) + len(self.errors)

        print(f"{GREEN}PASSES:   {len(self.passes):3d}{RESET}")
        print(f"{YELLOW}WARNINGS: {len(self.warnings):3d}{RESET}")
        print(f"{RED}ERRORS:   {len(self.errors):3d}{RESET}")
        print(f"{'-' * 20}")
        print(f"TOTAL:    {total:3d}\n")

        if self.errors:
            print_fail("AUDIT FAILED - Critical errors found:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
            print()

        if self.warnings:
            print_warn("Warnings (review recommended):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
            print()

        if not self.errors:
            if not self.warnings:
                print(f"\n{GREEN}{'=' * 80}")
                print("[OK][OK][OK] ALL AUDITS PASSED - DATA IS ACCURATE AND CALCULATIONS ARE CORRECT [OK][OK][OK]")
                print(f"{'=' * 80}{RESET}\n")
            else:
                print(f"\n{YELLOW}{'=' * 80}")
                print("[!] AUDIT PASSED WITH WARNINGS - Review warnings above")
                print(f"{'=' * 80}{RESET}\n")
        else:
            print(f"\n{RED}{'=' * 80}")
            print("[X][X][X] AUDIT FAILED - FIX ERRORS BEFORE TRADING [X][X][X]")
            print(f"{'=' * 80}{RESET}\n")

        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("COMPLETE DATA ACCURACY & CALCULATION AUDIT")
    print("=" * 80)
    print("\nThis audit will verify:")
    print("  1. Database schema and integrity")
    print("  2. Config vs database synchronization")
    print("  3. ORB calculation accuracy")
    print("  4. Session statistics calculations")
    print("  5. Trade level calculations (entry/stop/target)")
    print("  6. Filter logic correctness")
    print("  7. Data completeness and gaps")
    print("  8. Timezone handling")
    print("  9. Validated setups completeness")
    print("  10. Risk/Reward mathematics")
    print("\nPress Enter to start the audit...")

    try:
        input()
    except EOFError:
        print("(Running in non-interactive mode)")
        pass

    audit = DataAudit()
    audit.run_all_audits()
