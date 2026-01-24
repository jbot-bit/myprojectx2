"""
Test ORB Active Window Detection

Verifies that ORBs display for 3 hours after formation, not just exact hour.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import sys
from pathlib import Path

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from strategy_engine import StrategyEngine
from data_loader import LiveDataLoader
from config import TZ_LOCAL

def test_orb_windows():
    """Test ORB window detection at various times."""

    print("=" * 70)
    print("TESTING ORB ACTIVE WINDOW DETECTION")
    print("=" * 70)
    print()

    # Create engine with mock loader (won't query actual data)
    class MockLoader:
        """Minimal mock loader for testing window logic."""
        def __init__(self):
            self.symbol = "MGC"

    try:
        loader = MockLoader()
        engine = StrategyEngine(loader)
        print(f"[OK] Engine created for testing (instrument: {engine.instrument})")
    except Exception as e:
        print(f"[ERROR] Could not create engine: {e}")
        print(f"[INFO] This is OK if database is locked - we can still test window logic")
        # Create minimal engine just for window testing
        engine = type('obj', (object,), {})()  # Empty object
        engine._get_active_orb_windows = lambda self, t: []  # Dummy method
        print(f"[INFO] Using minimal mock for testing")

    # Test cases: (hour, minute, expected_active_orbs)
    test_cases = [
        # Night ORB tests
        (23, 0, ["2300"], "2300 ORB start"),
        (23, 10, ["2300"], "2300 ORB at 23:10 (CRITICAL FIX)"),
        (23, 30, ["2300"], "2300 ORB at 23:30"),
        (0, 0, ["2300"], "2300 ORB at midnight (1h elapsed)"),
        (0, 30, ["2300", "0030"], "Both 2300 and 0030 ORBs (overlap)"),
        (0, 45, ["2300", "0030"], "Both ORBs at 00:45"),
        (1, 0, ["2300", "0030"], "Both ORBs at 01:00"),
        (2, 0, ["0030"], "Only 0030 (2300 expired at 02:00)"),
        (3, 0, ["0030"], "0030 ORB at 03:00 (expires at 03:30)"),
        (3, 30, [], "0030 ORB expired"),

        # Day ORB tests
        (9, 0, ["0900"], "0900 ORB start"),
        (9, 15, ["0900"], "0900 ORB at 09:15 (CRITICAL FIX)"),
        (9, 30, ["0900"], "0900 ORB at 09:30"),
        (10, 0, ["0900", "1000"], "0900 and 1000 ORBs (overlap)"),
        (10, 30, ["0900", "1000"], "Both day ORBs at 10:30"),
        (11, 0, ["0900", "1000", "1100"], "All 3 day ORBs (max overlap)"),
        (11, 30, ["0900", "1000", "1100"], "All 3 at 11:30"),
        (12, 0, ["1000", "1100"], "0900 expired, 1000/1100 active"),
        (13, 0, ["1100"], "Only 1100 (1000 expired)"),
        (14, 0, [], "All day ORBs expired"),
    ]

    print("Testing ORB window detection:")
    print("-" * 70)

    passed = 0
    failed = 0

    for hour, minute, expected, description in test_cases:
        # Create test time
        test_time = datetime.now(TZ_LOCAL).replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0
        )

        # Get active ORBs
        try:
            active = engine._get_active_orb_windows(test_time)
            active_set = set(active)
            expected_set = set(expected)

            if active_set == expected_set:
                status = "[PASS]"
                passed += 1
            else:
                status = "[FAIL]"
                failed += 1

            exp_str = str(expected) if expected else 'none'
            act_str = str(active) if active else 'none'
            print(f"{status} | {hour:02d}:{minute:02d} | Expected: {exp_str:25s} | Got: {act_str}")
            print(f"       | {description}")

            if active_set != expected_set:
                missing = expected_set - active_set
                extra = active_set - expected_set
                if missing:
                    print(f"       | Missing: {missing}")
                if extra:
                    print(f"       | Extra: {extra}")

        except Exception as e:
            print(f"[ERROR] | {hour:02d}:{minute:02d} | {e}")
            failed += 1

        print()

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("[SUCCESS] ALL TESTS PASSED!")
        print()
        print("The timing fix is working correctly:")
        print("- ORBs persist for 3 hours after formation")
        print("- Multiple ORBs can be active simultaneously")
        print("- Overnight transitions handled correctly")
        return True
    else:
        print(f"[FAIL] {failed} TESTS FAILED")
        print("Fix the issues before proceeding.")
        return False

if __name__ == "__main__":
    success = test_orb_windows()
    sys.exit(0 if success else 1)
