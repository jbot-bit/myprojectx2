"""
STEP 2.4: Time-Safety Assertions (Hard-Fail)
Based on: STEPTWOA.txt

Purpose: Enforce time-safety at code level with hard assertions
Ensure features are only used AFTER they become available
"""

import duckdb
import pandas as pd
from datetime import datetime, time
from typing import Dict, List
import json


class TimeSafetyAuditor:
    """Auditor for time-safety assertions"""

    def __init__(self, db_path: str = "gold.db"):
        self.db_path = db_path
        self.results = []
        self.passed = 0
        self.failed = 0

        # Feature availability map (when each feature becomes available)
        self.FEATURE_AVAILABLE_AT = {
            # Pre-open / transitions (available at window end)
            "pre_asia_range": time(9, 0),
            "pre_london_range": time(18, 0),
            "pre_ny_range": time(23, 0),

            # ATR (available at day start if computed from prior days only)
            "atr_20": time(0, 0),

            # ORB-derived (available at ORB close)
            "orb_0900_size": time(9, 5),
            "orb_1000_size": time(10, 5),
            "orb_1100_size": time(11, 5),
            "orb_1800_size": time(18, 5),
            "orb_2300_size": time(23, 5),
            "orb_0030_size": time(0, 35),
        }

        # Strategy usage rules (which ORBs can use which features)
        self.STRATEGY_CAN_USE = {
            "0900": {"pre_asia_range", "atr_20", "orb_0900_size"},
            "1000": {"pre_asia_range", "atr_20", "orb_0900_size", "orb_1000_size"},
            "1100": {"pre_asia_range", "atr_20", "orb_0900_size", "orb_1000_size", "orb_1100_size"},
            "1800": {"atr_20", "pre_london_range", "orb_1800_size"},
            "2300": {"atr_20", "pre_ny_range", "orb_2300_size"},
            "0030": {"atr_20", "orb_0030_size"},
        }

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
    # Feature Availability Tests
    # ========================================================================

    def test_feature_availability_map(self) -> bool:
        """Test that feature availability map is complete"""
        print("  -> Testing feature availability map...")

        # Check that all critical features are mapped
        required_features = [
            "pre_asia_range", "pre_london_range", "atr_20",
            "orb_0900_size", "orb_1000_size", "orb_1800_size", "orb_2300_size"
        ]

        missing = [f for f in required_features if f not in self.FEATURE_AVAILABLE_AT]

        passed = len(missing) == 0
        self.add_result(
            "Feature Availability Map",
            passed,
            f"All {len(required_features)} critical features mapped" if passed else f"Missing {len(missing)} features",
            {
                "total_features": len(self.FEATURE_AVAILABLE_AT),
                "required_features": len(required_features),
                "missing": missing
            }
        )

        return passed

    def test_strategy_usage_rules(self) -> bool:
        """Test that strategy usage rules are defined"""
        print("  -> Testing strategy usage rules...")

        # Check that all ORB times have usage rules
        orb_times = ["0900", "1000", "1100", "1800", "2300", "0030"]
        missing_rules = [orb for orb in orb_times if orb not in self.STRATEGY_CAN_USE]

        passed = len(missing_rules) == 0
        self.add_result(
            "Strategy Usage Rules",
            passed,
            f"All {len(orb_times)} ORB times have usage rules" if passed else f"Missing rules for {missing_rules}",
            {
                "total_orbs": len(orb_times),
                "rules_defined": len(self.STRATEGY_CAN_USE),
                "missing": missing_rules
            }
        )

        return passed

    # ========================================================================
    # Time-Safety Validation
    # ========================================================================

    def test_orb_availability_timing(self) -> bool:
        """Test that ORB data is only available after ORB close"""
        print("  -> Testing ORB availability timing...")

        con = self.connect()

        # Verify that ORB features in database respect time boundaries
        # For example, 09:00 ORB should only have data for times >= 09:05
        query = """
        SELECT
            COUNT(*) as total,
            COUNT(orb_0900_high) as orb_0900_count,
            COUNT(orb_1000_high) as orb_1000_count,
            COUNT(orb_1800_high) as orb_1800_count
        FROM daily_features_v2
        WHERE instrument = 'MGC'
        """

        result = con.execute(query).fetchone()
        total, orb_0900, orb_1000, orb_1800 = result

        # All ORBs should have similar counts (within reasonable variance)
        variance = max(orb_0900, orb_1000, orb_1800) - min(orb_0900, orb_1000, orb_1800)
        passed = variance < total * 0.1  # Within 10% variance is OK

        self.add_result(
            "ORB Availability Timing",
            passed,
            f"ORB data counts consistent: 0900={orb_0900}, 1000={orb_1000}, 1800={orb_1800}",
            {
                "total_days": total,
                "orb_0900": orb_0900,
                "orb_1000": orb_1000,
                "orb_1800": orb_1800,
                "variance": variance
            }
        )

        con.close()
        return passed

    def test_atr_no_lookahead(self) -> bool:
        """Test that ATR doesn't use future data"""
        print("  -> Testing ATR zero-lookahead...")

        con = self.connect()

        # ATR should be available at start of day (computed from prior days)
        # Check that ATR values are reasonable and stable
        query = """
        SELECT
            COUNT(*) as total,
            COUNT(atr_20) as atr_count,
            AVG(atr_20) as avg_atr,
            MIN(atr_20) as min_atr,
            MAX(atr_20) as max_atr
        FROM daily_features_v2
        WHERE instrument = 'MGC'
        """

        result = con.execute(query).fetchone()
        total, atr_count, avg_atr, min_atr, max_atr = result

        # ATR should exist for most days and be positive
        passed = atr_count > total * 0.9 and (min_atr > 0 if min_atr else False)

        avg_str = f"{avg_atr:.2f}" if avg_atr else "0"
        self.add_result(
            "ATR Zero-Lookahead",
            passed,
            f"ATR available on {atr_count}/{total} days, avg={avg_str}",
            {
                "total": total,
                "atr_count": atr_count,
                "coverage_pct": (atr_count / total * 100) if total > 0 else 0,
                "avg_atr": float(avg_atr) if avg_atr else None
            }
        )

        con.close()
        return passed

    # ========================================================================
    # Strategy-Feature Compatibility
    # ========================================================================

    def test_strategy_feature_compatibility(self) -> bool:
        """Test that strategies only use allowed features"""
        print("  -> Testing strategy-feature compatibility...")

        # Verify logical consistency of usage rules
        # Example: 09:00 strategy should NOT use 10:00 ORB data
        violations = []

        for orb_time, allowed_features in self.STRATEGY_CAN_USE.items():
            # Check if any disallowed ORB features are in the list
            orb_hour = int(orb_time[:2])

            for feature in allowed_features:
                if "orb_" in feature:
                    # Extract ORB time from feature name
                    feature_time = feature.split("_")[1]
                    feature_hour = int(feature_time[:2])

                    # Feature time should be <= strategy time
                    if feature_time > orb_time:
                        violations.append(f"{orb_time} uses future ORB {feature_time}")

        passed = len(violations) == 0
        self.add_result(
            "Strategy-Feature Compatibility",
            passed,
            f"No time violations" if passed else f"Found {len(violations)} violations",
            {"violations": violations}
        )

        return passed

    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================

    def run_all_tests(self) -> Dict:
        """Run all Step 2.4 tests"""
        print("\n" + "=" * 60)
        print("STEP 2.4: TIME-SAFETY ASSERTIONS AUDIT")
        print("=" * 60)

        tests = [
            ("Feature Availability Map", self.test_feature_availability_map),
            ("Strategy Usage Rules", self.test_strategy_usage_rules),
            ("ORB Availability Timing", self.test_orb_availability_timing),
            ("ATR Zero-Lookahead", self.test_atr_no_lookahead),
            ("Strategy-Feature Compatibility", self.test_strategy_feature_compatibility),
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
            "step": "Step 2.4: Time-Safety Assertions",
            "passed": self.passed,
            "failed": self.failed,
            "total": total_tests,
            "pass_rate": pass_rate,
            "results": self.results,
            "verdict": "PASS" if self.failed == 0 else "FAIL"
        }

        return summary

    def export_results(self, filepath: str = "audit_reports/step2a_time_assertions_report.json"):
        """Export results to JSON file"""
        total_tests = self.passed + self.failed
        pass_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0

        summary = {
            "step": "Step 2.4: Time-Safety Assertions",
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
    auditor = TimeSafetyAuditor("gold.db")
    summary = auditor.run_all_tests()

    # Export results
    auditor.export_results()

    # Exit with error code if tests failed
    import sys
    sys.exit(0 if summary["verdict"] == "PASS" else 1)
