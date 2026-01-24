"""
EXAMPLE: How to Use Attack Harness with Your Trading Strategy

This demonstrates how to integrate the attack testing framework
with your actual trading strategy backtest.
"""

import pandas as pd
import numpy as np
from audits.attack_harness import run_all_attacks, AttackResult, check_stop_conditions


# ============================================================================
# STEP 1: Define Your Backtest Function
# ============================================================================

def example_orb_backtest(data: pd.DataFrame) -> pd.DataFrame:
    """
    Example backtest function for ORB strategy

    Args:
        data: DataFrame with OHLC and ORB data

    Returns:
        DataFrame with trades containing:
        - entry_price
        - stop_price
        - target_price
        - outcome ('WIN' or 'LOSS')
        - r_multiple (actual R achieved)

    NOTE: Replace this with your actual backtest logic
    """
    trades = []

    # Example: Simple ORB breakout logic
    for idx, row in data.iterrows():
        # Skip if no ORB data
        if pd.isna(row.get('orb_high')) or pd.isna(row.get('orb_low')):
            continue

        orb_high = row['orb_high']
        orb_low = row['orb_low']
        orb_size = orb_high - orb_low

        # Entry: Breakout above ORB high
        entry_price = orb_high + 0.1  # Entry just above ORB high

        # Stop: Below ORB low
        stop_price = orb_low - 0.1

        # Target: 2R
        risk = entry_price - stop_price
        target_price = entry_price + (2.0 * risk)

        # Simulate outcome (replace with actual price action)
        # In real backtest, check if price hits stop or target first
        hit_target = row.get('high', 0) >= target_price
        hit_stop = row.get('low', 0) <= stop_price

        if hit_target and hit_stop:
            # Ambiguous case - mark it for attack testing
            outcome = "WIN"  # Optimistic assumption
            r_multiple = 2.0
            hit_both = True
        elif hit_target:
            outcome = "WIN"
            r_multiple = 2.0
            hit_both = False
        elif hit_stop:
            outcome = "LOSS"
            r_multiple = -1.0
            hit_both = False
        else:
            continue  # No trade

        trades.append({
            'date': row.get('date'),
            'entry_price': entry_price,
            'stop_price': stop_price,
            'target_price': target_price,
            'outcome': outcome,
            'r_multiple': r_multiple,
            'hit_stop_and_target': hit_both
        })

    return pd.DataFrame(trades)


# ============================================================================
# STEP 2: Load Your Data
# ============================================================================

def load_example_data() -> pd.DataFrame:
    """
    Load your trading data

    Returns:
        DataFrame with OHLC and ORB features

    NOTE: Replace this with actual data loading from gold.db
    """
    import duckdb

    con = duckdb.connect("gold.db")

    query = """
    SELECT
        date_local as date,
        orb_1000_high as orb_high,
        orb_1000_low as orb_low,
        orb_1000_size,
        atr_20
    FROM daily_features_v2
    WHERE instrument = 'MGC'
      AND orb_1000_high IS NOT NULL
    ORDER BY date_local
    """

    data = con.execute(query).fetchdf()
    con.close()

    # Add simulated price data (replace with actual bars_1m query)
    data['high'] = data['orb_high'] + np.random.uniform(1, 5, len(data))
    data['low'] = data['orb_low'] - np.random.uniform(1, 5, len(data))

    return data


# ============================================================================
# STEP 3: Run Baseline (Clean) Backtest
# ============================================================================

def run_baseline_test():
    """Run clean backtest without attacks"""
    print("=" * 60)
    print("STEP 3: BASELINE BACKTEST (No Attacks)")
    print("=" * 60)

    # Load data
    data = load_example_data()
    print(f"Loaded {len(data)} days of data")

    # Run backtest
    trades = example_orb_backtest(data)
    print(f"Generated {len(trades)} trades")

    if len(trades) == 0:
        print("❌ No trades generated - check backtest logic")
        return None

    # Calculate metrics
    avg_r = trades['r_multiple'].mean()
    winrate = (trades['outcome'] == 'WIN').mean() * 100
    total_r = trades['r_multiple'].sum()

    print("\nBaseline Results:")
    print(f"  Trades: {len(trades)}")
    print(f"  Avg R: {avg_r:.3f}")
    print(f"  Win Rate: {winrate:.1f}%")
    print(f"  Total R: {total_r:.2f}")

    # Create baseline result
    baseline = AttackResult(
        name="Baseline",
        avg_r=avg_r,
        winrate=winrate,
        trades=len(trades)
    )

    print(f"  Verdict: {baseline.verdict}")

    return baseline, data


# ============================================================================
# STEP 4: Run Attack Tests
# ============================================================================

def run_attack_tests():
    """Run full attack suite"""
    print("\n" + "=" * 60)
    print("STEP 4: ATTACK TESTING")
    print("=" * 60)

    # Get baseline and data
    result = run_baseline_test()
    if result is None:
        print("❌ Cannot run attacks without baseline")
        return

    baseline, data = result

    # Run all attacks
    print("\nRunning attack suite...")
    attack_results = run_all_attacks(
        backtest_fn=example_orb_backtest,
        data=data,
        baseline_result=baseline
    )

    # Display results
    print("\n" + "=" * 60)
    print("ATTACK TEST RESULTS")
    print("=" * 60)
    print(attack_results[['name', 'avg_r', 'winrate', 'trades', 'verdict']].to_string(index=False))

    # Check stop conditions
    print("\n" + "=" * 60)
    print("STOP CONDITION CHECK")
    print("=" * 60)

    stop_check = check_stop_conditions(attack_results)

    if stop_check['deployable']:
        print("✅ PASS: Strategy is deployable")
        print(f"   Warnings: {stop_check['warnings']}")
        print(f"   Critical Failures: {stop_check['critical_failures']}")
    else:
        print("❌ FAIL: Strategy is NOT deployable")
        print(f"   Critical Failures: {stop_check['critical_failures']}")
        print("\nFailures:")
        for failure in stop_check['failures']:
            print(f"  - {failure['condition']}: {failure.get('attacks', 'N/A')}")

    # Export results
    attack_results.to_csv("audit_reports/attack_test_results.csv", index=False)
    print("\n✅ Results exported to: audit_reports/attack_test_results.csv")

    return attack_results, stop_check


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ATTACK TESTING EXAMPLE")
    print("Demonstrates how to test strategy robustness")
    print("=" * 60)

    try:
        attack_results, stop_check = run_attack_tests()

        # Final verdict
        print("\n" + "=" * 60)
        print("FINAL VERDICT")
        print("=" * 60)

        if stop_check['deployable']:
            print("✅ Strategy passed all attack tests")
            print("   → Ready for deployment consideration")
        else:
            print("❌ Strategy FAILED attack tests")
            print("   → DO NOT DEPLOY")
            print("   → Review failures and redesign strategy")

        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error running attack tests: {str(e)}")
        import traceback
        traceback.print_exc()
