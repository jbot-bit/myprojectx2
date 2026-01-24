#!/usr/bin/env python3
"""
Test the complete setup ranking system works end-to-end.
Confirms existing architecture functions correctly.
"""

import sys
from pathlib import Path

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from setup_detector import SetupDetector
from setup_scoring import explain_setup_score, compare_setups, rank_all_setups


def test_setup_detector():
    """Test SetupDetector reads from database correctly."""
    print("="*80)
    print("TEST 1: SetupDetector")
    print("="*80)

    detector = SetupDetector()

    # Get all MGC setups
    setups = detector.get_all_validated_setups('MGC')

    print(f"Found {len(setups)} MGC setups in database")

    if len(setups) == 0:
        print("ERROR: No setups found!")
        return False

    print("\nSetups:")
    for setup in setups:
        print(f"  {setup['orb_time']} ORB: {setup['tier']} tier, +{setup['avg_r']:.3f}R, {setup['win_rate']:.1f}% WR")

    print("\n[PASS] SetupDetector works")
    return True


def test_setup_ranking():
    """Test setups rank correctly by tier + avg_r."""
    print("\n" + "="*80)
    print("TEST 2: Setup Ranking Logic")
    print("="*80)

    detector = SetupDetector()
    setups = detector.get_all_validated_setups('MGC')

    # Check ranking order
    print("\nSetups ranked by existing logic (tier first, then avg_r):")

    prev_tier_order = -1
    prev_avg_r = float('inf')
    tier_order_map = {'S+': 0, 'S': 1, 'A': 2, 'B': 3, 'C': 4}

    for i, setup in enumerate(setups, 1):
        tier = setup['tier']
        avg_r = setup['avg_r']
        tier_order = tier_order_map.get(tier, 99)

        print(f"{i}. {setup['orb_time']} ORB: {tier} tier, +{avg_r:.3f}R")

        # Verify ranking is correct
        if tier_order < prev_tier_order:
            print(f"  ERROR: Tier order broken! {tier} should not come after previous tier")
            return False

        if tier_order == prev_tier_order and avg_r > prev_avg_r:
            print(f"  ERROR: Within same tier, avg_r should be descending!")
            return False

        prev_tier_order = tier_order
        prev_avg_r = avg_r

    print("\n[PASS] Ranking logic correct")
    return True


def test_scoring_transparency():
    """Test scoring breakdown shows why setups rank."""
    print("\n" + "="*80)
    print("TEST 3: Scoring Transparency")
    print("="*80)

    detector = SetupDetector()
    setups = detector.get_all_validated_setups('MGC')

    if len(setups) < 3:
        print("Need at least 3 setups to test comparison")
        return False

    # Get top 3 setups
    top_3 = setups[:3]

    print("\nTop 3 setups with score breakdown:")

    for i, setup in enumerate(top_3, 1):
        score = explain_setup_score(setup)
        print(f"\n#{i}: {setup['orb_time']} ORB [{setup['tier']} tier]")
        print(f"  Score: {score['total_score']:.2f}/100")
        print(f"  Why: {score['rank_factors']['primary']} -> {score['rank_factors']['secondary']}")

    # Compare top 2
    if len(top_3) >= 2:
        print("\n" + "-"*80)
        print("Why #1 beats #2:")
        print("-"*80)

        comparison = compare_setups(top_3[0], top_3[1])
        print(comparison[:500] + "...")  # First 500 chars

    print("\n[PASS] Scoring transparency works")
    return True


def test_elite_detection():
    """Test elite setup detection (S+ and S tier)."""
    print("\n" + "="*80)
    print("TEST 4: Elite Setup Detection")
    print("="*80)

    detector = SetupDetector()
    elite = detector.get_elite_setups('MGC')

    print(f"\nFound {len(elite)} elite MGC setups (S+ and S tier):")

    for setup in elite:
        print(f"  {setup['orb_time']} ORB: {setup['tier']} tier, +{setup['avg_r']:.3f}R")

    if len(elite) == 0:
        print("WARNING: No elite setups found (expected some S+/S)")
        return False

    print("\n[PASS] Elite detection works")
    return True


def main():
    """Run all tests."""
    print("\n")
    print("="*80)
    print("SETUP SYSTEM VERIFICATION")
    print("="*80)
    print("\nTesting the existing 'best trade now' architecture...")
    print()

    tests = [
        ("SetupDetector", test_setup_detector),
        ("Setup Ranking", test_setup_ranking),
        ("Scoring Transparency", test_scoring_transparency),
        ("Elite Detection", test_elite_detection),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n[FAIL] {name} crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("\n" + "="*80)

    if all_passed:
        print("SUCCESS: All tests passed!")
        print("\nYour setup ranking system is WORKING and READY.")
        print("\nTo add new setups:")
        print("  1. Insert row to validated_setups database")
        print("  2. System automatically picks it up")
        print("  3. Use setup_scoring.py to see why it ranks where it does")
        print("\nSee SETUP_SYSTEM_GUIDE.md for details.")
    else:
        print("FAILURE: Some tests failed")
        print("Check errors above")

    print("="*80)
    print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
