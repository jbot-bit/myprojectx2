"""
MASTER AUDIT RUNNER
Complete validation suite for trading system

Usage:
    python audit_master.py                    # Run all tests
    python audit_master.py --step 1           # Run Step 1 only
    python audit_master.py --step 2           # Run Step 2 only
    python audit_master.py --quick            # Quick subset of critical tests
    python audit_master.py --export results.csv  # Export results
"""

import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Add audits to path (we're already in audits/)
sys.path.insert(0, str(Path(__file__).parent))

from step1_data_integrity import DataIntegrityAuditor
from step1a_gaps_transitions import GapTransitionAuditor
from step2_feature_verification import FeatureVerificationAuditor
from step2a_time_assertions import TimeSafetyAuditor
from step3_strategy_validation import StrategyValidationAuditor


class MasterAuditor:
    """Master audit coordinator"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Auto-detect from audits folder
            db_path = str(Path(__file__).parent.parent / "data/db/gold.db")
        self.db_path = db_path
        self.results = {}
        self.start_time = None
        self.end_time = None

    def print_header(self):
        """Print audit header"""
        print("\n" + "=" * 70)
        print("MASTER AUDIT SYSTEM".center(70))
        print("Trading System Validation Framework".center(70))
        print("=" * 70)
        print(f"\nDatabase: {self.db_path}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

    def print_summary(self):
        """Print final summary"""
        print("\n" + "=" * 70)
        print("MASTER AUDIT SUMMARY".center(70))
        print("=" * 70)

        total_passed = 0
        total_failed = 0
        total_tests = 0

        for step_name, result in self.results.items():
            if result:
                passed = result.get("passed", 0)
                failed = result.get("failed", 0)
                total = result.get("total", 0)
                verdict = result.get("verdict", "UNKNOWN")

                total_passed += passed
                total_failed += failed
                total_tests += total

                status = "[OK]" if verdict == "PASS" else "[FAIL]"
                print(f"\n{status} {step_name}")
                print(f"   Passed: {passed}/{total} ({result.get('pass_rate', 0):.1f}%)")

        print("\n" + "-" * 70)
        overall_pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        print(f"OVERALL: {total_passed}/{total_tests} tests passed ({overall_pass_rate:.1f}%)")

        # Overall verdict
        if total_failed == 0:
            print("\n[PASS] VERDICT: SYSTEM READY FOR DEPLOYMENT")
        elif total_failed <= 3:
            print("\n[WARN] VERDICT: MINOR ISSUES - REVIEW REQUIRED")
        else:
            print("\n[FAIL] VERDICT: CRITICAL FAILURES - DO NOT DEPLOY")

        print("=" * 70)

        # Timing
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"\nCompleted in {duration:.1f} seconds")

    def run_step1(self):
        """Run Step 1: Data Integrity"""
        print("\n" + ">" * 70)
        print("RUNNING STEP 1: DATA INTEGRITY")
        print(">" * 70)

        auditor = DataIntegrityAuditor(self.db_path)
        result = auditor.run_all_tests()
        self.results["Step 1: Data Integrity"] = result

        # Export
        auditor.export_results()

        return result

    def run_step2(self):
        """Run Step 2: Feature Verification"""
        print("\n" + ">" * 70)
        print("RUNNING STEP 2: FEATURE VERIFICATION")
        print(">" * 70)

        auditor = FeatureVerificationAuditor(self.db_path)
        result = auditor.run_all_tests()
        self.results["Step 2: Feature Verification"] = result

        # Export
        auditor.export_results()

        return result

    def run_step1a(self):
        """Run Step 1.5: Gap & Transition Behavior"""
        print("\n" + ">" * 70)
        print("RUNNING STEP 1.5: GAP & TRANSITION BEHAVIOR")
        print(">" * 70)

        auditor = GapTransitionAuditor(self.db_path)
        result = auditor.run_all_tests()
        self.results["Step 1.5: Gap & Transition Behavior"] = result

        # Export
        auditor.export_results()

        return result

    def run_step2a(self):
        """Run Step 2.4: Time-Safety Assertions"""
        print("\n" + ">" * 70)
        print("RUNNING STEP 2.4: TIME-SAFETY ASSERTIONS")
        print(">" * 70)

        auditor = TimeSafetyAuditor(self.db_path)
        result = auditor.run_all_tests()
        self.results["Step 2.4: Time-Safety Assertions"] = result

        # Export
        auditor.export_results()

        return result

    def run_step3(self):
        """Run Step 3: Strategy Validation"""
        print("\n" + ">" * 70)
        print("RUNNING STEP 3: STRATEGY VALIDATION")
        print(">" * 70)

        auditor = StrategyValidationAuditor(self.db_path)
        result = auditor.run_all_tests()
        self.results["Step 3: Strategy Validation"] = result

        # Export
        auditor.export_results()

        return result

    def run_all(self):
        """Run all audit steps"""
        self.start_time = datetime.now()
        self.print_header()

        # Run each step
        self.run_step1()
        self.run_step1a()  # Gap & Transitions
        self.run_step2()
        self.run_step2a()  # Time-Safety
        self.run_step3()   # Strategy Validation

        self.end_time = datetime.now()
        self.print_summary()

        # Export master report
        self.export_master_report()

        # Return exit code
        total_failed = sum(r.get("failed", 0) for r in self.results.values())
        return 0 if total_failed == 0 else 1

    def run_quick(self):
        """Run quick subset of critical tests"""
        print("\n** QUICK AUDIT MODE (Critical Tests Only) **\n")
        self.start_time = datetime.now()

        # Run just critical tests
        self.run_step1()

        self.end_time = datetime.now()
        self.print_summary()

        total_failed = sum(r.get("failed", 0) for r in self.results.values())
        return 0 if total_failed == 0 else 1

    def export_master_report(self):
        """Export master report"""
        report = {
            "audit_type": "master_audit",
            "database": self.db_path,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
            "results": self.results,
            "summary": {
                "total_passed": sum(r.get("passed", 0) for r in self.results.values()),
                "total_failed": sum(r.get("failed", 0) for r in self.results.values()),
                "total_tests": sum(r.get("total", 0) for r in self.results.values())
            }
        }

        filepath = "audit_reports/master_audit_report.json"
        os.makedirs("audit_reports", exist_ok=True)

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n[REPORT] Master report exported to: {filepath}")

        # Also create a simple CSV summary
        self.export_csv_summary()

    def export_csv_summary(self):
        """Export simple CSV summary"""
        import csv

        filepath = "audit_reports/audit_summary.csv"

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Step", "Passed", "Failed", "Total", "Pass Rate %", "Verdict"])

            for step_name, result in self.results.items():
                if result:
                    writer.writerow([
                        step_name,
                        result.get("passed", 0),
                        result.get("failed", 0),
                        result.get("total", 0),
                        f"{result.get('pass_rate', 0):.1f}",
                        result.get("verdict", "UNKNOWN")
                    ])

        print(f"[REPORT] CSV summary exported to: {filepath}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Master Audit System - Complete Validation Suite")
    parser.add_argument("--step", type=str, help="Run specific step (1, 1.5, 2, 2.4, 3)")
    parser.add_argument("--quick", action="store_true", help="Run quick audit (critical tests only)")
    parser.add_argument("--db", type=str, default=None, help="Path to database (auto-detected if not provided)")
    parser.add_argument("--export", type=str, help="Export results to file")

    args = parser.parse_args()

    # Auto-detect DB path if not provided
    if args.db is None:
        args.db = str(Path(__file__).parent.parent / "data/db/gold.db")

    # Create auditor
    auditor = MasterAuditor(db_path=args.db)

    # Check if database exists
    if not os.path.exists(args.db):
        print(f"[ERROR] Error: Database not found: {args.db}")
        print("\nMake sure you're running from the project directory with data/db/gold.db")
        return 1

    # Create reports directory
    os.makedirs("audit_reports", exist_ok=True)

    # Run appropriate audit
    if args.quick:
        exit_code = auditor.run_quick()
    elif args.step:
        auditor.print_header()

        if args.step == "1":
            auditor.run_step1()
            key = "Step 1: Data Integrity"
        elif args.step == "1.5":
            auditor.run_step1a()
            key = "Step 1.5: Gap & Transition Behavior"
        elif args.step == "2":
            auditor.run_step2()
            key = "Step 2: Feature Verification"
        elif args.step == "2.4":
            auditor.run_step2a()
            key = "Step 2.4: Time-Safety Assertions"
        elif args.step == "3":
            auditor.run_step3()
            key = "Step 3: Strategy Validation"
        else:
            print(f"[ERROR] Invalid step: {args.step}")
            print("Valid steps: 1, 1.5, 2, 2.4, 3")
            return 1

        auditor.print_summary()
        exit_code = 0 if auditor.results[key]["verdict"] == "PASS" else 1
    else:
        # Run all
        exit_code = auditor.run_all()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
