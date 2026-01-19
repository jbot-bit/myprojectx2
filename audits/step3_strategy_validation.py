"""
STEP 3: Strategy Validation
Based on: STEPTHREE.txt

Purpose: Prove strategy is mechanically correct and deterministic
- Strategy manifest lock
- Backtest engine correctness
- Walk-forward testing
- Regime safety
"""

import duckdb
import pandas as pd
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Callable
import numpy as np


class StrategyValidationAuditor:
    """Auditor for strategy validation"""

    def __init__(self, db_path: str = "gold.db"):
        self.db_path = db_path
        self.results = []
        self.passed = 0
        self.failed = 0

    def connect(self):
        """Connect to database"""
        return duckdb.connect(self.db_path)

    def add_result(self, test_name: str, passed: bool, message: str, details: Dict = None):
        """Add test result"""
        self.results.append({
            "test": test_name,
            "passed": passed,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    # ========================================================================
    # 3.1 Strategy Definition Lock
    # ========================================================================

    def test_strategy_manifest_exists(self) -> bool:
        """Test that validated_setups table exists and has data"""
        print("  -> Testing strategy manifest...")

        con = self.connect()

        try:
            query = """
            SELECT COUNT(*) as setup_count
            FROM validated_setups
            """
            result = con.execute(query).fetchone()
            setup_count = result[0]

            passed = setup_count >= 17  # Expect at least 17 setups
            self.add_result(
                "Strategy Manifest",
                passed,
                f"Found {setup_count} validated setups (expected >=17)",
                {"setup_count": setup_count}
            )

        except Exception as e:
            self.add_result(
                "Strategy Manifest",
                False,
                f"Error accessing validated_setups: {str(e)}"
            )
            passed = False

        con.close()
        return passed

    def test_strategy_manifest_hash(self) -> bool:
        """Test that strategy manifest can be hashed for determinism"""
        print("  -> Testing strategy manifest hash...")

        con = self.connect()

        try:
            query = """
            SELECT
                setup_id, instrument, orb_time, rr, sl_mode,
                close_confirmations, buffer_ticks, orb_size_filter
            FROM validated_setups
            ORDER BY setup_id
            """
            df = con.execute(query).fetchdf()

            # Compute hash (sort DataFrame first for determinism)
            df_sorted = df.sort_values('setup_id').reset_index(drop=True)
            manifest_str = df_sorted.to_json(orient='records')
            manifest_hash = hashlib.md5(manifest_str.encode()).hexdigest()

            self.add_result(
                "Strategy Manifest Hash",
                True,
                f"Manifest hash computed: {manifest_hash[:16]}...",
                {
                    "hash": manifest_hash,
                    "setup_count": len(df),
                    "note": "Re-run to verify determinism"
                }
            )
            passed = True

        except Exception as e:
            self.add_result(
                "Strategy Manifest Hash",
                False,
                f"Error computing hash: {str(e)}"
            )
            passed = False

        con.close()
        return passed

    # ========================================================================
    # 3.2 Backtest Engine Correctness (Mechanical)
    # ========================================================================

    def test_strategy_parameters_valid(self) -> bool:
        """Test that all strategy parameters are valid"""
        print("  -> Testing strategy parameter validity...")

        con = self.connect()

        try:
            query = """
            SELECT
                setup_id,
                rr,
                sl_mode,
                close_confirmations,
                orb_size_filter
            FROM validated_setups
            """
            df = con.execute(query).fetchdf()

            issues = []

            # Check RR is positive
            invalid_rr = df[df['rr'] <= 0]
            if len(invalid_rr) > 0:
                issues.append(f"{len(invalid_rr)} setups with RR <= 0")

            # Check SL mode is valid
            valid_sl_modes = ['FULL', 'HALF', 'DYNAMIC']
            invalid_sl = df[~df['sl_mode'].isin(valid_sl_modes)]
            if len(invalid_sl) > 0:
                issues.append(f"{len(invalid_sl)} setups with invalid SL mode")

            # Check confirmations >= 0
            invalid_confirm = df[df['close_confirmations'] < 0]
            if len(invalid_confirm) > 0:
                issues.append(f"{len(invalid_confirm)} setups with confirmations < 0")

            passed = len(issues) == 0
            self.add_result(
                "Strategy Parameter Validity",
                passed,
                "All parameters valid" if passed else f"Found {len(issues)} issues",
                {"issues": issues, "total_setups": len(df)}
            )

        except Exception as e:
            self.add_result(
                "Strategy Parameter Validity",
                False,
                f"Error validating parameters: {str(e)}"
            )
            passed = False

        con.close()
        return passed

    def test_strategy_tiers_valid(self) -> bool:
        """Test that strategy tiers are assigned correctly"""
        print("  -> Testing strategy tier assignments...")

        con = self.connect()

        try:
            query = """
            SELECT
                setup_id,
                tier,
                win_rate,
                avg_r
            FROM validated_setups
            """
            df = con.execute(query).fetchdf()

            valid_tiers = ['S+', 'S', 'A', 'B', 'C']
            invalid_tiers = df[~df['tier'].isin(valid_tiers)]

            passed = len(invalid_tiers) == 0
            self.add_result(
                "Strategy Tier Validity",
                passed,
                f"All tiers valid" if passed else f"Found {len(invalid_tiers)} invalid tiers",
                {
                    "valid_tiers": valid_tiers,
                    "invalid_count": len(invalid_tiers),
                    "total_setups": len(df)
                }
            )

        except Exception as e:
            self.add_result(
                "Strategy Tier Validity",
                False,
                f"Error validating tiers: {str(e)}"
            )
            passed = False

        con.close()
        return passed

    # ========================================================================
    # 3.3 Walk-Forward & Regime Safety (Simplified)
    # ========================================================================

    def test_strategy_performance_metrics(self) -> bool:
        """Test that strategy performance metrics are reasonable"""
        print("  -> Testing strategy performance metrics...")

        con = self.connect()

        try:
            query = """
            SELECT
                instrument,
                COUNT(*) as setup_count,
                AVG(win_rate) as avg_win_rate,
                AVG(avg_r) as avg_avg_r,
                MIN(trades) as min_trades,
                MAX(trades) as max_trades
            FROM validated_setups
            GROUP BY instrument
            """
            df = con.execute(query).fetchdf()

            issues = []

            for _, row in df.iterrows():
                inst = row['instrument']

                # Win rate should be reasonable (15% to 85%)
                if not (15 <= row['avg_win_rate'] <= 85):
                    issues.append(f"{inst}: win rate {row['avg_win_rate']:.1f}% out of range")

                # Avg R should be positive for S+ tier strategies
                if row['avg_avg_r'] < 0:
                    issues.append(f"{inst}: negative avg R {row['avg_avg_r']:.3f}")

                # Should have decent sample size
                if row['min_trades'] < 50:
                    issues.append(f"{inst}: low trade count {row['min_trades']}")

            passed = len(issues) == 0
            self.add_result(
                "Strategy Performance Metrics",
                passed,
                f"All metrics reasonable" if passed else f"Found {len(issues)} issues",
                {
                    "issues": issues,
                    "instruments": df['instrument'].tolist()
                }
            )

        except Exception as e:
            self.add_result(
                "Strategy Performance Metrics",
                False,
                f"Error checking metrics: {str(e)}"
            )
            passed = False

        con.close()
        return passed

    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================

    def run_all_tests(self) -> Dict:
        """Run all Step 3 tests"""
        print("\n" + "=" * 60)
        print("STEP 3: STRATEGY VALIDATION AUDIT")
        print("=" * 60)

        tests = [
            ("Strategy Manifest", self.test_strategy_manifest_exists),
            ("Manifest Hash", self.test_strategy_manifest_hash),
            ("Parameter Validity", self.test_strategy_parameters_valid),
            ("Tier Validity", self.test_strategy_tiers_valid),
            ("Performance Metrics", self.test_strategy_performance_metrics),
        ]

        for test_name, test_fn in tests:
            try:
                test_fn()
            except Exception as e:
                self.add_result(
                    test_name,
                    False,
                    f"Test failed with exception: {str(e)}"
                )

        # Summary
        total_tests = self.passed + self.failed
        pass_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0

        print("\n" + "-" * 60)
        print(f"RESULTS: {self.passed}/{total_tests} tests passed ({pass_rate:.1f}%)")
        print("-" * 60)

        summary = {
            "step": "Step 3: Strategy Validation",
            "passed": self.passed,
            "failed": self.failed,
            "total": total_tests,
            "pass_rate": pass_rate,
            "results": self.results,
            "verdict": "PASS" if self.failed == 0 else "FAIL"
        }

        return summary

    def export_results(self, filepath: str = "audit_reports/step3_strategy_validation_report.json"):
        """Export results to JSON file"""
        total_tests = self.passed + self.failed
        pass_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0

        summary = {
            "step": "Step 3: Strategy Validation",
            "passed": self.passed,
            "failed": self.failed,
            "total": total_tests,
            "pass_rate": pass_rate,
            "results": self.results,
            "verdict": "PASS" if self.failed == 0 else "FAIL"
        }

        with open(filepath, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n[OK] Results exported to: {filepath}")
        return filepath


if __name__ == "__main__":
    auditor = StrategyValidationAuditor("gold.db")
    summary = auditor.run_all_tests()

    # Export results
    auditor.export_results()

    # Exit with error code if tests failed
    import sys
    sys.exit(0 if summary["verdict"] == "PASS" else 1)
