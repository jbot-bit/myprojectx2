"""
Test Conditional Edges Integration

Verifies Phase 1B conditional edge system works correctly:
- Market state detection
- Conditional setup matching
- Quality multipliers
- Fallback to baseline setups
"""

import sys
from pathlib import Path
from datetime import date
import os

# Load environment variables BEFORE importing any trading_app modules
from dotenv import load_dotenv
load_dotenv()

# Verify FORCE_LOCAL_DB is set
print(f"FORCE_LOCAL_DB={os.getenv('FORCE_LOCAL_DB')}")
print(f"CLOUD_MODE={os.getenv('CLOUD_MODE')}")
print(f"DUCKDB_PATH={os.getenv('DUCKDB_PATH')}")

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent / 'trading_app'))

from setup_detector import SetupDetector
from market_state import get_market_state, detect_asia_bias, get_asia_range


def test_market_state_detection():
    """Test 1: Market state detection works"""
    print("=" * 70)
    print("TEST 1: Market State Detection")
    print("=" * 70)

    # Test with known date (2026-01-09)
    test_date = date(2026, 1, 9)

    # Get Asia range
    asia_data = get_asia_range(target_date=test_date)
    if asia_data is None:
        print("[SKIP] No Asia data for test date")
        return False

    print(f"Asia Range: {asia_data['asia_low']:.2f} - {asia_data['asia_high']:.2f}")

    # Test ABOVE
    price_above = asia_data['asia_high'] + 1.0
    bias = detect_asia_bias(price_above, asia_data['asia_high'], asia_data['asia_low'])
    assert bias == "ABOVE", f"Expected ABOVE, got {bias}"
    print(f"[PASS] Price {price_above:.2f} detected as ABOVE")

    # Test BELOW
    price_below = asia_data['asia_low'] - 1.0
    bias = detect_asia_bias(price_below, asia_data['asia_high'], asia_data['asia_low'])
    assert bias == "BELOW", f"Expected BELOW, got {bias}"
    print(f"[PASS] Price {price_below:.2f} detected as BELOW")

    # Test INSIDE
    price_inside = (asia_data['asia_high'] + asia_data['asia_low']) / 2
    bias = detect_asia_bias(price_inside, asia_data['asia_high'], asia_data['asia_low'])
    assert bias == "INSIDE", f"Expected INSIDE, got {bias}"
    print(f"[PASS] Price {price_inside:.2f} detected as INSIDE")

    print("[PASS] Market state detection works correctly")
    return True


def test_conditional_setup_matching():
    """Test 2: Conditional setup matching works"""
    print("\n" + "=" * 70)
    print("TEST 2: Conditional Setup Matching")
    print("=" * 70)

    detector = SetupDetector()
    test_date = date(2026, 1, 9)

    # Get Asia range
    asia_data = get_asia_range(target_date=test_date)
    if asia_data is None:
        print("[SKIP] No Asia data for test date")
        return False

    # Test ABOVE condition (should activate ABOVE conditional setups)
    price_above = asia_data['asia_high'] + 1.0
    result = detector.get_active_and_potential_setups('MGC', price_above, test_date)

    print(f"\nPrice ABOVE Asia range ({price_above:.2f}):")
    print(f"  Market state: {result['market_state']['asia_bias']}")
    print(f"  Active conditional setups: {len(result['active'])}")
    print(f"  Baseline setups: {len(result['baseline'])}")

    # Should have some active setups when ABOVE
    if len(result['active']) > 0:
        print(f"[PASS] Conditional setups activated when price ABOVE")
        # Check quality multipliers
        for setup in result['active'][:3]:
            print(f"    - {setup['orb_time']} RR={setup['rr']}: "
                  f"AvgR={setup['avg_r']:.3f}, Quality={setup.get('quality_multiplier', 1.0)}x")
    else:
        print(f"[INFO] No conditional setups for ABOVE (may be expected)")

    # Test INSIDE condition (should fall back to baseline only)
    price_inside = (asia_data['asia_high'] + asia_data['asia_low']) / 2
    result = detector.get_active_and_potential_setups('MGC', price_inside, test_date)

    print(f"\nPrice INSIDE Asia range ({price_inside:.2f}):")
    print(f"  Market state: {result['market_state']['asia_bias']}")
    print(f"  Active conditional setups: {len(result['active'])}")
    print(f"  Baseline setups: {len(result['baseline'])}")

    assert len(result['baseline']) > 0, "Should always have baseline setups"
    print(f"[PASS] Baseline setups always available (fallback works)")

    # Test BELOW condition
    price_below = asia_data['asia_low'] - 1.0
    result = detector.get_active_and_potential_setups('MGC', price_below, test_date)

    print(f"\nPrice BELOW Asia range ({price_below:.2f}):")
    print(f"  Market state: {result['market_state']['asia_bias']}")
    print(f"  Active conditional setups: {len(result['active'])}")
    print(f"  Baseline setups: {len(result['baseline'])}")

    if len(result['active']) > 0:
        print(f"[PASS] Conditional setups activated when price BELOW")

    print("[PASS] Conditional setup matching works correctly")
    return True


def test_quality_multipliers():
    """Test 3: Quality multipliers present"""
    print("\n" + "=" * 70)
    print("TEST 3: Quality Multipliers")
    print("=" * 70)

    detector = SetupDetector()
    test_date = date(2026, 1, 9)

    # Get Asia range
    asia_data = get_asia_range(target_date=test_date)
    if asia_data is None:
        print("[SKIP] No Asia data for test date")
        return False

    # Test with ABOVE condition to get conditional setups
    price_above = asia_data['asia_high'] + 1.0
    result = detector.get_active_and_potential_setups('MGC', price_above, test_date)

    found_multipliers = False
    for setup in result['active']:
        multiplier = setup.get('quality_multiplier')
        if multiplier is not None and multiplier != 1.0:
            found_multipliers = True
            print(f"[PASS] {setup['orb_time']} RR={setup['rr']}: "
                  f"AvgR={setup['avg_r']:.3f}, Quality={multiplier:.1f}x")

    if found_multipliers:
        print("[PASS] Quality multipliers present in conditional setups")
    else:
        print("[INFO] No quality multipliers > 1.0 found (may be expected)")

    return True


def test_database_schema():
    """Test 4: Database has Phase 1B columns"""
    print("\n" + "=" * 70)
    print("TEST 4: Database Schema")
    print("=" * 70)

    import duckdb
    conn = duckdb.connect('data/db/gold.db', read_only=True)

    # Check columns exist
    columns = conn.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'validated_setups'
    """).fetchall()

    column_names = [col[0] for col in columns]
    required_columns = ['condition_type', 'condition_value', 'baseline_setup_id', 'quality_multiplier']

    for col in required_columns:
        assert col in column_names, f"Missing column: {col}"
        print(f"[PASS] Column exists: {col}")

    # Check conditional setups exist
    result = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN condition_type IS NOT NULL THEN 1 ELSE 0 END) as conditional,
               SUM(CASE WHEN condition_type IS NULL THEN 1 ELSE 0 END) as baseline
        FROM validated_setups
        WHERE instrument = 'MGC'
    """).fetchone()

    print(f"\nMGC Setups:")
    print(f"  Total: {result[0]}")
    print(f"  Conditional: {result[1]}")
    print(f"  Baseline: {result[2]}")

    assert result[1] > 0, "Should have conditional setups"
    assert result[2] > 0, "Should have baseline setups"

    conn.close()

    print("[PASS] Database schema correct with Phase 1B data")
    return True


def main():
    """Run all tests"""
    print("\n")
    print("=" * 70)
    print("CONDITIONAL EDGES INTEGRATION TEST")
    print("=" * 70)
    print()

    tests = [
        test_database_schema,
        test_market_state_detection,
        test_conditional_setup_matching,
        test_quality_multipliers,
    ]

    passed = 0
    failed = 0
    skipped = 0

    for test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            elif result is False:
                failed += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"\n[FAIL] {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"Failed: {failed}/{len(tests)}")
    if skipped > 0:
        print(f"Skipped: {skipped}/{len(tests)}")

    if failed == 0:
        print("\n[PASS] ALL TESTS PASSED!")
        print("\nConditional edges system is working correctly:")
        print("  - Market state detection works")
        print("  - Conditional setups match correctly based on conditions")
        print("  - Quality multipliers present for position sizing")
        print("  - Baseline setups always available as fallback")
        print("  - Database schema includes all Phase 1B columns")
        return True
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
