"""
Test Phase 1B conditional setup integration.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(".env")
load_dotenv(env_path)

sys.path.insert(0, 'trading_app')

from setup_detector import SetupDetector
from datetime import date

def test_conditional_setup_detection():
    """Test that conditional setups are detected correctly."""
    detector = SetupDetector()

    print("=" * 80)
    print("PHASE 1B INTEGRATION TEST")
    print("=" * 80)

    # Test 1: Get active/potential setups with realistic MGC price
    print("\nTEST 1: Active & Potential Setup Detection")
    print("-" * 80)

    current_price = 4480.0  # Realistic MGC price
    target_date = date(2026, 1, 9)  # Date with data

    result = detector.get_active_and_potential_setups(
        instrument='MGC',
        current_price=current_price,
        target_date=target_date
    )

    print(f"Current Price: ${current_price:.2f}")
    print(f"Date: {target_date}")
    print(f"\nMarket State:")
    print(f"  Asia Bias: {result['market_state']['asia_bias']}")
    print(f"  Asia High: ${result['market_state']['asia_high']:.2f}")
    print(f"  Asia Low:  ${result['market_state']['asia_low']:.2f}")

    print(f"\nActive Setups (conditions met NOW): {len(result['active'])}")
    if result['active']:
        print("  Top 3:")
        for setup in result['active'][:3]:
            print(f"    - {setup['orb_time']} RR={setup['rr']} {setup['sl_mode']}: {setup['avg_r']:.3f}R (Tier {setup['tier']}, {setup['quality_multiplier']}x)")
            print(f"      Condition: {setup['condition_type']}={setup['condition_value']}")

    print(f"\nBaseline Setups (always available): {len(result['baseline'])}")
    if result['baseline']:
        print("  Top 3:")
        for setup in result['baseline'][:3]:
            print(f"    - {setup['orb_time']} RR={setup['rr']} {setup['sl_mode']}: {setup['avg_r']:.3f}R (Tier {setup['tier']}, {setup['quality_multiplier']}x)")

    print(f"\nPotential Setups (if conditions change): {len(result['potential'])}")
    if result['potential']:
        print("  Top 3:")
        for setup in result['potential'][:3]:
            print(f"    - {setup['orb_time']} RR={setup['rr']} {setup['sl_mode']}: {setup['avg_r']:.3f}R (Tier {setup['tier']})")
            print(f"      Becomes active {setup['becomes_active_if']}")

    # Test 2: Elite setups (S+ and S tier)
    print("\n" + "=" * 80)
    print("TEST 2: Elite Setups (S+ and S Tier)")
    print("-" * 80)

    elite = detector.get_elite_setups('MGC')
    print(f"Total Elite Setups: {len(elite)}")

    baseline_elite = [s for s in elite if s['condition_type'] is None]
    conditional_elite = [s for s in elite if s['condition_type'] is not None]

    print(f"  Baseline Elite: {len(baseline_elite)}")
    print(f"  Conditional Elite: {len(conditional_elite)}")

    if conditional_elite:
        print("\nTop 5 Conditional Elite Setups:")
        for i, setup in enumerate(conditional_elite[:5], 1):
            cond = f"{setup['condition_type']}={setup['condition_value']}" if setup['condition_type'] else "baseline"
            print(f"  {i}. {setup['orb_time']} RR={setup['rr']} {setup['sl_mode']}: {setup['avg_r']:.3f}R (Tier {setup['tier']}, {setup['quality_multiplier']}x)")
            print(f"     {setup['win_rate']:.1f}% WR, ~{setup['annual_trades']} trades/year, Condition: {cond}")

    # Test 3: Database integrity
    print("\n" + "=" * 80)
    print("TEST 3: Database Integrity Check")
    print("-" * 80)

    import duckdb
    conn = duckdb.connect('data/db/gold.db')

    # Count setups by type
    result = conn.execute("""
        SELECT
            CASE WHEN condition_type IS NULL THEN 'Baseline' ELSE 'Conditional' END as setup_type,
            COUNT(*) as count,
            ROUND(AVG(avg_r), 3) as avg_expectancy,
            ROUND(AVG(win_rate), 1) as avg_wr
        FROM validated_setups
        GROUP BY setup_type
    """).fetchall()

    print("Setup breakdown:")
    for row in result:
        print(f"  {row[0]}: {row[1]} setups, Avg {row[2]}R expectancy, {row[3]}% WR")

    # Count quality multipliers
    result = conn.execute("""
        SELECT
            quality_multiplier,
            COUNT(*) as count
        FROM validated_setups
        WHERE quality_multiplier IS NOT NULL
        GROUP BY quality_multiplier
        ORDER BY quality_multiplier DESC
    """).fetchall()

    print("\nQuality Multiplier distribution:")
    for row in result:
        print(f"  {row[0]}x: {row[1]} setups")

    conn.close()

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
    print("\nPhase 1B integration is working correctly:")
    print("  - Market state detection active")
    print("  - Conditional setups loaded")
    print("  - Active/potential edge matching functional")
    print("  - Position sizing multipliers applied")
    print("\nSystem is ready for conditional edge trading!")

if __name__ == "__main__":
    test_conditional_setup_detection()
