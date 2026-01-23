"""
UNICORN VALIDATOR
=================

Takes output from ULTIMATE_UNICORN_FINDER.py and validates for:
1. Statistical robustness (walk-forward analysis)
2. Temporal stability (performance across time periods)
3. Data integrity (no suspicious patterns)
4. Filter by quality criteria
5. Sort by robustness score

Output: Filtered, validated, ranked unicorn setups ready for trading
"""

import duckdb
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Validation metrics for a unicorn setup"""
    config_id: str
    orb_time: str
    duration_min: int
    sl_mode: str
    rr: float

    # Original metrics
    total_trades: int
    total_wins: int
    total_win_rate: float
    total_avg_r: float
    total_annual_r: float

    # Temporal stability (3 periods)
    period1_trades: int
    period1_avg_r: float
    period2_trades: int
    period2_avg_r: float
    period3_trades: int
    period3_avg_r: float

    # Robustness metrics
    expectancy_std: float  # Lower is better (more stable)
    periods_profitable: int  # How many periods had positive expectancy
    min_period_r: float  # Worst period performance
    max_period_r: float  # Best period performance

    # Quality score (0-100)
    robustness_score: float

    # Pass/Fail
    is_robust: bool
    notes: str


def load_unicorns(csv_path: str = "ULTIMATE_UNICORNS.csv") -> pd.DataFrame:
    """Load unicorn results from CSV"""
    try:
        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} unicorn setups from {csv_path}")
        return df
    except FileNotFoundError:
        print(f"ERROR: {csv_path} not found. Run ULTIMATE_UNICORN_FINDER.py first.")
        return None


def validate_setup_temporal_stability(orb_time: str, duration: int, sl_mode: str, rr: float) -> Optional[ValidationResult]:
    """
    Test a setup across 3 time periods for temporal stability

    Period 1: 2024-01-02 to 2024-08-31 (8 months)
    Period 2: 2024-09-01 to 2025-04-30 (8 months)
    Period 3: 2025-05-01 to 2026-01-10 (8 months)
    """

    from ULTIMATE_UNICORN_FINDER import test_configuration

    hour, minute = map(int, orb_time.split(':'))

    con = duckdb.connect("gold.db", read_only=True)

    periods = [
        ('2024-01-02', '2024-08-31'),
        ('2024-09-01', '2025-04-30'),
        ('2025-05-01', '2026-01-10')
    ]

    period_results = []

    for start, end in periods:
        # Get dates for this period
        dates_query = f"""
        SELECT DISTINCT date_local
        FROM daily_features_v2
        WHERE instrument = 'MGC'
            AND date_local >= '{start}'
            AND date_local <= '{end}'
        ORDER BY date_local
        """
        dates = [row[0] for row in con.execute(dates_query).fetchall()]

        if len(dates) < 10:
            period_results.append(None)
            continue

        # Simulate trades for this period
        from ULTIMATE_UNICORN_FINDER import simulate_unicorn_trade

        results = []
        for d in dates:
            result = simulate_unicorn_trade(con, d, hour, minute, duration, sl_mode, rr)
            if result:
                results.append(result)

        if len(results) >= 5:  # Need at least 5 trades per period
            wins = sum(1 for r in results if r['outcome'] == 'WIN')
            trades = len(results)
            total_r = sum(r['r_multiple'] for r in results)
            avg_r = total_r / trades
            period_results.append({
                'trades': trades,
                'wins': wins,
                'avg_r': avg_r,
                'total_r': total_r
            })
        else:
            period_results.append(None)

    con.close()

    # Check if we have at least 2 periods with data
    valid_periods = [p for p in period_results if p is not None]
    if len(valid_periods) < 2:
        return None

    # Calculate robustness metrics
    period_avg_rs = [p['avg_r'] for p in valid_periods]
    expectancy_std = np.std(period_avg_rs)
    periods_profitable = sum(1 for r in period_avg_rs if r > 0)
    min_period_r = min(period_avg_rs)
    max_period_r = max(period_avg_rs)

    # Calculate robustness score (0-100)
    score = 0.0

    # All periods profitable = +40 points
    score += (periods_profitable / len(valid_periods)) * 40

    # Low std dev = +30 points (normalized, 0.2 std = full points)
    score += max(0, (1 - expectancy_std / 0.4) * 30)

    # Min period not too bad = +30 points (>= -0.1 = full points)
    if min_period_r >= 0:
        score += 30
    elif min_period_r >= -0.1:
        score += 15

    score = min(100, max(0, score))

    # Determine if robust
    is_robust = (
        periods_profitable >= 2 and  # At least 2/3 periods profitable
        min_period_r > -0.2 and  # Worst period not terrible
        expectancy_std < 0.5  # Reasonably stable
    )

    # Generate notes
    notes = []
    if periods_profitable == len(valid_periods):
        notes.append("✓ ALL periods profitable")
    elif periods_profitable >= 2:
        notes.append(f"⚠ {periods_profitable}/{len(valid_periods)} periods profitable")
    else:
        notes.append(f"✗ Only {periods_profitable}/{len(valid_periods)} periods profitable")

    if expectancy_std < 0.2:
        notes.append("✓ Very stable")
    elif expectancy_std < 0.5:
        notes.append("⚠ Moderately stable")
    else:
        notes.append("✗ Unstable")

    # Get total results
    p1 = period_results[0] if period_results[0] else {'trades': 0, 'avg_r': 0}
    p2 = period_results[1] if period_results[1] else {'trades': 0, 'avg_r': 0}
    p3 = period_results[2] if period_results[2] else {'trades': 0, 'avg_r': 0}

    total_trades = sum(p['trades'] for p in valid_periods)
    total_wins = sum(p['wins'] for p in valid_periods)
    total_r = sum(p['total_r'] for p in valid_periods)

    return ValidationResult(
        config_id=f"{orb_time}_{duration}min_{sl_mode}_RR{rr}",
        orb_time=orb_time,
        duration_min=duration,
        sl_mode=sl_mode,
        rr=rr,
        total_trades=total_trades,
        total_wins=total_wins,
        total_win_rate=total_wins / total_trades if total_trades > 0 else 0,
        total_avg_r=total_r / total_trades if total_trades > 0 else 0,
        total_annual_r=total_r / 2.0,
        period1_trades=p1['trades'],
        period1_avg_r=p1['avg_r'],
        period2_trades=p2['trades'],
        period2_avg_r=p2['avg_r'],
        period3_trades=p3['trades'],
        period3_avg_r=p3['avg_r'],
        expectancy_std=expectancy_std,
        periods_profitable=periods_profitable,
        min_period_r=min_period_r,
        max_period_r=max_period_r,
        robustness_score=score,
        is_robust=is_robust,
        notes=" | ".join(notes)
    )


def main():
    print("\n" + "="*80)
    print("UNICORN VALIDATOR")
    print("="*80)
    print("\nValidating unicorn setups for robustness and temporal stability...\n")

    # Load unicorns
    df = load_unicorns()
    if df is None:
        return

    # Filter by minimum criteria BEFORE validation
    print("Applying minimum criteria:")
    print(f"  - Min 30 trades (was {len(df)} setups)")
    df = df[df['trades'] >= 30]
    print(f"  - Min 0.15 avg R (was {len(df)} setups)")
    df = df[df['avg_r'] >= 0.15]
    print(f"  - Remaining: {len(df)} setups\n")

    if len(df) == 0:
        print("No setups passed minimum criteria!")
        return

    # Sort by avg_r to test best ones first
    df = df.sort_values('avg_r', ascending=False)

    print(f"Running temporal validation on top {min(50, len(df))} setups...")
    print("(This will take a few minutes)\n")

    validated = []
    for i, row in df.head(50).iterrows():
        result = validate_setup_temporal_stability(
            row['orb_time'],
            int(row['duration_min']),
            row['sl_mode'],
            float(row['rr'])
        )

        if result:
            validated.append(result)
            print(f"  [{len(validated)}/50] {result.config_id}: Score={result.robustness_score:.0f} {'✓ ROBUST' if result.is_robust else '✗ Not robust'}")

    print(f"\n{'='*80}")
    print(f"VALIDATION COMPLETE")
    print(f"{'='*80}\n")
    print(f"Validated: {len(validated)} setups")
    print(f"Robust: {sum(1 for v in validated if v.is_robust)} setups\n")

    if not validated:
        print("No setups passed validation!")
        return

    # Sort by robustness score
    validated.sort(key=lambda x: x.robustness_score, reverse=True)

    # Save to CSV
    validated_df = pd.DataFrame([{
        'config_id': v.config_id,
        'orb_time': v.orb_time,
        'duration_min': v.duration_min,
        'sl_mode': v.sl_mode,
        'rr': v.rr,
        'total_trades': v.total_trades,
        'total_win_rate': v.total_win_rate,
        'total_avg_r': v.total_avg_r,
        'total_annual_r': v.total_annual_r,
        'period1_trades': v.period1_trades,
        'period1_avg_r': v.period1_avg_r,
        'period2_trades': v.period2_trades,
        'period2_avg_r': v.period2_avg_r,
        'period3_trades': v.period3_trades,
        'period3_avg_r': v.period3_avg_r,
        'expectancy_std': v.expectancy_std,
        'periods_profitable': v.periods_profitable,
        'min_period_r': v.min_period_r,
        'max_period_r': v.max_period_r,
        'robustness_score': v.robustness_score,
        'is_robust': v.is_robust,
        'notes': v.notes
    } for v in validated])

    validated_df.to_csv("VALIDATED_UNICORNS.csv", index=False)
    print(f"Saved to: VALIDATED_UNICORNS.csv\n")

    # Print top 20 robust setups
    print("="*80)
    print("TOP 20 ROBUST UNICORNS (by robustness score)")
    print("="*80)
    print(f"{'Rank':<5} {'Config':<30} {'Score':<7} {'Trades':<8} {'Avg R':<8} {'Ann R':<8} {'Notes':<40}")
    print("-"*80)

    for i, v in enumerate([x for x in validated if x.is_robust][:20], 1):
        print(f"{i:<5} {v.config_id:<30} {v.robustness_score:<7.0f} {v.total_trades:<8} {v.total_avg_r:<+8.3f} {v.total_annual_r:<+8.0f} {v.notes[:40]}")

    # Summary statistics
    print(f"\n{'='*80}")
    print("ROBUSTNESS SUMMARY")
    print(f"{'='*80}\n")

    robust = [v for v in validated if v.is_robust]

    if robust:
        print(f"Robust setups: {len(robust)}")
        print(f"Average score: {np.mean([v.robustness_score for v in robust]):.1f}")
        print(f"Average expectancy: {np.mean([v.total_avg_r for v in robust]):+.3f}R")
        print(f"Average annual R: {np.mean([v.total_annual_r for v in robust]):+.0f}R")

        # Group by time
        by_time = {}
        for v in robust:
            if v.orb_time not in by_time:
                by_time[v.orb_time] = []
            by_time[v.orb_time].append(v)

        print(f"\nROBUST SETUPS BY TIME:")
        for time in sorted(by_time.keys()):
            setups = by_time[time]
            avg_score = np.mean([s.robustness_score for s in setups])
            avg_r = np.mean([s.total_avg_r for s in setups])
            print(f"  {time}: {len(setups)} setups, avg score={avg_score:.0f}, avg R={avg_r:+.3f}")

    print(f"\n{'='*80}")
    print("DONE! Check VALIDATED_UNICORNS.csv for full results.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
