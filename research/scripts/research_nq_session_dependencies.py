"""
NQ Intra-Session Dependencies Research
======================================

Goal: Discover if one session's behavior predicts the next session's behavior

Questions:
1. Does Asia trend direction predict London trend?
2. Does Asia volatility predict London/NY expansion?
3. Do Asia ORB outcomes predict later ORB outcomes?
4. Are there sequential ORB patterns (e.g., 0900 WIN → 1800 WIN)?

Methodology:
- Correlation analysis between sessions
- Conditional probabilities (if A, then B)
- Sequential pattern mining
- Robustness testing with IS/OOS, outlier removal

Zero-Lookahead: All features must be known before the predicted session starts
"""

import sys
from datetime import datetime
from typing import Dict, List, Tuple
import duckdb
import pandas as pd
import numpy as np
from scipy import stats

DB_PATH = "gold.db"


def load_daily_features() -> pd.DataFrame:
    """Load all NQ daily features"""
    con = duckdb.connect(DB_PATH, read_only=True)

    query = """
        SELECT
            date_local,
            -- Session ranges
            asia_range, london_range, ny_range,
            -- Session highs/lows
            asia_high, asia_low,
            london_high, london_low,
            ny_high, ny_low,
            -- ORB outcomes
            orb_0900_outcome, orb_0900_r_multiple, orb_0900_break_dir, orb_0900_size,
            orb_1000_outcome, orb_1000_r_multiple, orb_1000_break_dir, orb_1000_size,
            orb_1100_outcome, orb_1100_r_multiple, orb_1100_break_dir, orb_1100_size,
            orb_1800_outcome, orb_1800_r_multiple, orb_1800_break_dir, orb_1800_size,
            orb_2300_outcome, orb_2300_r_multiple, orb_2300_break_dir, orb_2300_size,
            orb_0030_outcome, orb_0030_r_multiple, orb_0030_break_dir, orb_0030_size,
            -- MAE/MFE
            orb_0900_mae, orb_0900_mfe,
            orb_1000_mae, orb_1000_mfe,
            orb_1100_mae, orb_1100_mfe,
            orb_1800_mae, orb_1800_mfe,
            orb_2300_mae, orb_2300_mfe,
            orb_0030_mae, orb_0030_mfe
        FROM daily_features_v2_nq
        ORDER BY date_local
    """

    df = con.execute(query).df()
    con.close()

    return df


def analyze_session_correlations(df: pd.DataFrame) -> Dict:
    """Analyze correlations between session ranges"""
    results = {}

    # Asia vs London
    valid = df.dropna(subset=['asia_range', 'london_range'])
    if len(valid) > 10:
        corr, pval = stats.pearsonr(valid['asia_range'], valid['london_range'])
        results['asia_london_correlation'] = {
            'correlation': corr,
            'p_value': pval,
            'n': len(valid),
            'significant': pval < 0.05
        }

    # Asia vs NY
    valid = df.dropna(subset=['asia_range', 'ny_range'])
    if len(valid) > 10:
        corr, pval = stats.pearsonr(valid['asia_range'], valid['ny_range'])
        results['asia_ny_correlation'] = {
            'correlation': corr,
            'p_value': pval,
            'n': len(valid),
            'significant': pval < 0.05
        }

    # London vs NY
    valid = df.dropna(subset=['london_range', 'ny_range'])
    if len(valid) > 10:
        corr, pval = stats.pearsonr(valid['london_range'], valid['ny_range'])
        results['london_ny_correlation'] = {
            'correlation': corr,
            'p_value': pval,
            'n': len(valid),
            'significant': pval < 0.05
        }

    return results


def analyze_asia_volatility_regime(df: pd.DataFrame) -> Dict:
    """
    Test: Does Asia volatility regime predict London/NY expansion?

    Logic:
    - If Asia range is LOW (bottom 33%), does London/NY expand (top 50%)?
    - If Asia range is HIGH (top 33%), does London/NY expand?
    """
    results = {}

    df = df.dropna(subset=['asia_range', 'london_range']).copy()

    if len(df) < 30:
        return {'status': 'INSUFFICIENT_DATA'}

    # Define Asia regimes
    asia_low_threshold = df['asia_range'].quantile(0.33)
    asia_high_threshold = df['asia_range'].quantile(0.67)

    # Define London expansion
    london_median = df['london_range'].median()

    df['asia_regime'] = 'MID'
    df.loc[df['asia_range'] <= asia_low_threshold, 'asia_regime'] = 'LOW'
    df.loc[df['asia_range'] >= asia_high_threshold, 'asia_regime'] = 'HIGH'

    df['london_expanded'] = df['london_range'] >= london_median

    # Test each regime
    for regime in ['LOW', 'HIGH', 'MID']:
        regime_df = df[df['asia_regime'] == regime]

        if len(regime_df) < 10:
            continue

        expansion_rate = regime_df['london_expanded'].mean()
        n = len(regime_df)

        results[f'asia_{regime.lower()}_regime'] = {
            'n': n,
            'london_expansion_rate': expansion_rate,
            'london_avg_range': regime_df['london_range'].mean()
        }

    # Baseline (no filter)
    results['baseline'] = {
        'n': len(df),
        'london_expansion_rate': df['london_expanded'].mean(),
        'london_avg_range': df['london_range'].mean()
    }

    return results


def analyze_orb_sequence_patterns(df: pd.DataFrame) -> Dict:
    """
    Test: Do early ORB outcomes predict later ORB outcomes?

    Patterns to test:
    1. If 0900 ORB WINs, does 1800 ORB WIN more often?
    2. If 1000 ORB WINs, does 1800 ORB WIN more often?
    3. If Asia ORBs (0900, 1000, 1100) ALL WIN, does 1800 WIN?
    """
    results = {}

    # Pattern 1: 0900 outcome → 1800 outcome
    df_valid = df.dropna(subset=['orb_0900_outcome', 'orb_1800_outcome']).copy()

    if len(df_valid) > 20:
        # Baseline: 1800 win rate
        baseline_1800_wr = (df_valid['orb_1800_outcome'] == 'WIN').mean()

        # Conditional: 1800 WR when 0900 won
        after_0900_win = df_valid[df_valid['orb_0900_outcome'] == 'WIN']
        if len(after_0900_win) > 10:
            conditional_1800_wr = (after_0900_win['orb_1800_outcome'] == 'WIN').mean()
            improvement = ((conditional_1800_wr - baseline_1800_wr) / baseline_1800_wr * 100) if baseline_1800_wr > 0 else 0

            results['0900_win_predicts_1800'] = {
                'n': len(after_0900_win),
                'baseline_1800_wr': baseline_1800_wr,
                'conditional_1800_wr': conditional_1800_wr,
                'improvement_pct': improvement
            }

    # Pattern 2: 1000 outcome → 1800 outcome
    df_valid = df.dropna(subset=['orb_1000_outcome', 'orb_1800_outcome']).copy()

    if len(df_valid) > 20:
        baseline_1800_wr = (df_valid['orb_1800_outcome'] == 'WIN').mean()

        after_1000_win = df_valid[df_valid['orb_1000_outcome'] == 'WIN']
        if len(after_1000_win) > 10:
            conditional_1800_wr = (after_1000_win['orb_1800_outcome'] == 'WIN').mean()
            improvement = ((conditional_1800_wr - baseline_1800_wr) / baseline_1800_wr * 100) if baseline_1800_wr > 0 else 0

            results['1000_win_predicts_1800'] = {
                'n': len(after_1000_win),
                'baseline_1800_wr': baseline_1800_wr,
                'conditional_1800_wr': conditional_1800_wr,
                'improvement_pct': improvement
            }

    # Pattern 3: All Asia ORBs WIN → 1800 WIN
    df_valid = df.dropna(subset=['orb_0900_outcome', 'orb_1000_outcome', 'orb_1100_outcome', 'orb_1800_outcome']).copy()

    if len(df_valid) > 20:
        baseline_1800_wr = (df_valid['orb_1800_outcome'] == 'WIN').mean()

        all_asia_win = df_valid[
            (df_valid['orb_0900_outcome'] == 'WIN') &
            (df_valid['orb_1000_outcome'] == 'WIN') &
            (df_valid['orb_1100_outcome'] == 'WIN')
        ]

        if len(all_asia_win) > 5:
            conditional_1800_wr = (all_asia_win['orb_1800_outcome'] == 'WIN').mean()
            improvement = ((conditional_1800_wr - baseline_1800_wr) / baseline_1800_wr * 100) if baseline_1800_wr > 0 else 0

            results['all_asia_win_predicts_1800'] = {
                'n': len(all_asia_win),
                'baseline_1800_wr': baseline_1800_wr,
                'conditional_1800_wr': conditional_1800_wr,
                'improvement_pct': improvement
            }

    # Pattern 4: 1800 outcome → 0030 outcome
    df_valid = df.dropna(subset=['orb_1800_outcome', 'orb_0030_outcome']).copy()

    if len(df_valid) > 20:
        baseline_0030_wr = (df_valid['orb_0030_outcome'] == 'WIN').mean()

        after_1800_win = df_valid[df_valid['orb_1800_outcome'] == 'WIN']
        if len(after_1800_win) > 10:
            conditional_0030_wr = (after_1800_win['orb_0030_outcome'] == 'WIN').mean()
            improvement = ((conditional_0030_wr - baseline_0030_wr) / baseline_0030_wr * 100) if baseline_0030_wr > 0 else 0

            results['1800_win_predicts_0030'] = {
                'n': len(after_1800_win),
                'baseline_0030_wr': baseline_0030_wr,
                'conditional_0030_wr': conditional_0030_wr,
                'improvement_pct': improvement
            }

    return results


def test_asia_direction_continuation(df: pd.DataFrame) -> Dict:
    """
    Test: Does Asia directional trend continue into London/NY?

    Logic:
    - Define Asia trend: if 2+ Asia ORBs break same direction (UP/DOWN)
    - Test if London ORBs break same direction
    - Test if 0030 breaks same direction
    """
    results = {}

    df_valid = df.dropna(subset=[
        'orb_0900_break_dir', 'orb_1000_break_dir', 'orb_1100_break_dir',
        'orb_1800_break_dir'
    ]).copy()

    if len(df_valid) < 30:
        return {'status': 'INSUFFICIENT_DATA'}

    # Count Asia ORBs by direction
    df_valid['asia_up_count'] = (
        (df_valid['orb_0900_break_dir'] == 'UP').astype(int) +
        (df_valid['orb_1000_break_dir'] == 'UP').astype(int) +
        (df_valid['orb_1100_break_dir'] == 'UP').astype(int)
    )

    df_valid['asia_down_count'] = (
        (df_valid['orb_0900_break_dir'] == 'DOWN').astype(int) +
        (df_valid['orb_1000_break_dir'] == 'DOWN').astype(int) +
        (df_valid['orb_1100_break_dir'] == 'DOWN').astype(int)
    )

    # Define strong Asia trend
    df_valid['asia_trend'] = 'MIXED'
    df_valid.loc[df_valid['asia_up_count'] >= 2, 'asia_trend'] = 'UP'
    df_valid.loc[df_valid['asia_down_count'] >= 2, 'asia_trend'] = 'DOWN'

    # Test continuation to London (1800)
    for trend in ['UP', 'DOWN']:
        trend_days = df_valid[df_valid['asia_trend'] == trend]

        if len(trend_days) < 10:
            continue

        # How often does 1800 follow the same direction?
        continuation_rate = (trend_days['orb_1800_break_dir'] == trend).mean()
        n = len(trend_days)

        # Baseline: how often does 1800 break in that direction overall?
        baseline_rate = (df_valid['orb_1800_break_dir'] == trend).mean()

        improvement = ((continuation_rate - baseline_rate) / baseline_rate * 100) if baseline_rate > 0 else 0

        results[f'asia_{trend.lower()}_to_1800'] = {
            'n': n,
            'continuation_rate': continuation_rate,
            'baseline_rate': baseline_rate,
            'improvement_pct': improvement
        }

    return results


def test_tradeable_edge(df: pd.DataFrame, condition_fn, target_orb: str, min_improvement: float = 10.0) -> Dict:
    """
    Test if a discovered dependency is tradeable

    Args:
        condition_fn: Function that returns True for days meeting condition
        target_orb: ORB to trade ('1800', '0030', etc.)
        min_improvement: Minimum % improvement required to pass

    Returns:
        Dict with trade results and robustness tests
    """
    df_valid = df.copy()

    # Apply condition
    df_valid['meets_condition'] = df_valid.apply(condition_fn, axis=1)

    filtered = df_valid[df_valid['meets_condition']].copy()

    if len(filtered) < 20:
        return {'status': 'INSUFFICIENT_SAMPLE', 'n': len(filtered)}

    # Get outcomes
    outcome_col = f'orb_{target_orb}_outcome'
    r_col = f'orb_{target_orb}_r_multiple'

    filtered = filtered.dropna(subset=[outcome_col, r_col])

    if len(filtered) < 20:
        return {'status': 'INSUFFICIENT_SAMPLE', 'n': len(filtered)}

    # Basic stats
    wins = (filtered[outcome_col] == 'WIN').sum()
    losses = (filtered[outcome_col] == 'LOSS').sum()
    total = wins + losses

    win_rate = wins / total if total > 0 else 0
    avg_r = filtered[r_col].mean()

    # Baseline (no filter)
    baseline = df_valid.dropna(subset=[outcome_col, r_col])
    baseline_wins = (baseline[outcome_col] == 'WIN').sum()
    baseline_total = baseline_wins + (baseline[outcome_col] == 'LOSS').sum()
    baseline_wr = baseline_wins / baseline_total if baseline_total > 0 else 0
    baseline_avg_r = baseline[r_col].mean()

    improvement_wr = ((win_rate - baseline_wr) / baseline_wr * 100) if baseline_wr > 0 else 0
    improvement_r = ((avg_r - baseline_avg_r) / abs(baseline_avg_r) * 100) if baseline_avg_r != 0 else 0

    # IS/OOS split
    dates_sorted = sorted(filtered.index)
    split_idx = int(len(dates_sorted) * 0.7)
    is_dates = set(dates_sorted[:split_idx])
    oos_dates = set(dates_sorted[split_idx:])

    is_trades = filtered.loc[list(is_dates & set(filtered.index))]
    oos_trades = filtered.loc[list(oos_dates & set(filtered.index))]

    is_wr = (is_trades[outcome_col] == 'WIN').mean() if len(is_trades) > 0 else 0
    oos_wr = (oos_trades[outcome_col] == 'WIN').mean() if len(oos_trades) > 0 else 0

    is_avg_r = is_trades[r_col].mean() if len(is_trades) > 0 else 0
    oos_avg_r = oos_trades[r_col].mean() if len(oos_trades) > 0 else 0

    # Pass/Fail
    pass_tests = []

    if improvement_wr >= min_improvement or improvement_r >= min_improvement:
        pass_tests.append('IMPROVEMENT')

    if win_rate > baseline_wr and avg_r > baseline_avg_r:
        pass_tests.append('BOTH_METRICS_BETTER')

    if is_wr > baseline_wr and oos_wr > baseline_wr:
        pass_tests.append('IS_OOS_BETTER')

    if total >= 20:
        pass_tests.append('MIN_SAMPLE')

    status = 'PASS' if len(pass_tests) >= 3 else 'WEAK' if len(pass_tests) >= 2 else 'FAIL'

    return {
        'status': status,
        'n': total,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'baseline_wr': baseline_wr,
        'baseline_avg_r': baseline_avg_r,
        'improvement_wr': improvement_wr,
        'improvement_r': improvement_r,
        'is_n': len(is_trades),
        'is_wr': is_wr,
        'is_avg_r': is_avg_r,
        'oos_n': len(oos_trades),
        'oos_wr': oos_wr,
        'oos_avg_r': oos_avg_r,
        'pass_tests': pass_tests
    }


def main():
    print("=" * 80)
    print("NQ INTRA-SESSION DEPENDENCIES RESEARCH")
    print("=" * 80)
    print()

    print("Loading NQ daily features...")
    df = load_daily_features()
    df = df.set_index('date_local')
    print(f"Loaded {len(df)} trading days")
    print()

    # Test 1: Session correlations
    print("=" * 80)
    print("TEST 1: Session Range Correlations")
    print("=" * 80)
    print()

    corr_results = analyze_session_correlations(df)
    for name, result in corr_results.items():
        print(f"{name}:")
        print(f"  Correlation: {result['correlation']:+.3f}")
        print(f"  P-value: {result['p_value']:.4f}")
        print(f"  Significant: {result['significant']}")
        print(f"  N: {result['n']}")
        print()

    # Test 2: Asia volatility regime
    print("=" * 80)
    print("TEST 2: Asia Volatility Regime -> London Expansion")
    print("=" * 80)
    print()

    vol_results = analyze_asia_volatility_regime(df)
    if vol_results.get('status') != 'INSUFFICIENT_DATA':
        print(f"{'Regime':<15} {'N':>6} {'London Expansion Rate':>25} {'Avg London Range':>20}")
        print("-" * 80)

        baseline = vol_results.get('baseline', {})
        for regime in ['asia_low_regime', 'asia_high_regime', 'asia_mid_regime']:
            if regime in vol_results:
                r = vol_results[regime]
                vs_baseline = ""
                if baseline.get('london_expansion_rate'):
                    diff = r['london_expansion_rate'] - baseline['london_expansion_rate']
                    vs_baseline = f" ({diff:+.1%})"

                print(f"{regime:<15} {r['n']:>6} {r['london_expansion_rate']:>24.1%}{vs_baseline} {r['london_avg_range']:>20.1f}")

        print(f"{'BASELINE':<15} {baseline['n']:>6} {baseline['london_expansion_rate']:>25.1%} {baseline['london_avg_range']:>20.1f}")
    print()

    # Test 3: ORB sequence patterns
    print("=" * 80)
    print("TEST 3: ORB Sequence Patterns")
    print("=" * 80)
    print()

    seq_results = analyze_orb_sequence_patterns(df)
    for pattern, result in seq_results.items():
        print(f"{pattern}:")
        print(f"  N: {result['n']}")

        # Determine which keys to use based on pattern
        if 'predicts_1800' in pattern:
            baseline_key = 'baseline_1800_wr'
            conditional_key = 'conditional_1800_wr'
        else:  # predicts_0030
            baseline_key = 'baseline_0030_wr'
            conditional_key = 'conditional_0030_wr'

        print(f"  Baseline WR: {result[baseline_key]:.1%}")
        print(f"  Conditional WR: {result[conditional_key]:.1%}")
        print(f"  Improvement: {result['improvement_pct']:+.1f}%")
        print()

    # Test 4: Asia direction continuation
    print("=" * 80)
    print("TEST 4: Asia Trend Continuation to London")
    print("=" * 80)
    print()

    dir_results = test_asia_direction_continuation(df)
    if dir_results.get('status') != 'INSUFFICIENT_DATA':
        for pattern, result in dir_results.items():
            print(f"{pattern}:")
            print(f"  N: {result['n']}")
            print(f"  Continuation Rate: {result['continuation_rate']:.1%}")
            print(f"  Baseline Rate: {result['baseline_rate']:.1%}")
            print(f"  Improvement: {result['improvement_pct']:+.1f}%")
            print()

    # Test 5: Best tradeable edges
    print("=" * 80)
    print("TEST 5: Tradeable Edge Validation")
    print("=" * 80)
    print()

    # Edge 1: If 0900 wins, trade 1800
    def condition_0900_win(row):
        return row.get('orb_0900_outcome') == 'WIN'

    edge1 = test_tradeable_edge(df, condition_0900_win, '1800', min_improvement=10.0)
    print("EDGE 1: Trade 1800 if 0900 won")
    print(f"  Status: {edge1['status']}")
    if edge1['status'] != 'INSUFFICIENT_SAMPLE':
        print(f"  N: {edge1['n']} | WR: {edge1['win_rate']:.1%} | Avg R: {edge1['avg_r']:+.3f}")
        print(f"  Baseline: WR {edge1['baseline_wr']:.1%} | Avg R {edge1['baseline_avg_r']:+.3f}")
        print(f"  Improvement: WR {edge1['improvement_wr']:+.1f}% | Avg R {edge1['improvement_r']:+.1f}%")
        print(f"  IS/OOS: {edge1['is_wr']:.1%} / {edge1['oos_wr']:.1%}")
        print(f"  Pass Tests: {edge1['pass_tests']}")
    print()

    # Edge 2: If Asia trend UP (2+ ORBs), trade 1800 UP
    def condition_asia_up(row):
        asia_up = (
            (row.get('orb_0900_break_dir') == 'UP') +
            (row.get('orb_1000_break_dir') == 'UP') +
            (row.get('orb_1100_break_dir') == 'UP')
        )
        return asia_up >= 2 and row.get('orb_1800_break_dir') == 'UP'

    edge2 = test_tradeable_edge(df, condition_asia_up, '1800', min_improvement=10.0)
    print("EDGE 2: Trade 1800 UP if Asia trend UP")
    print(f"  Status: {edge2['status']}")
    if edge2['status'] != 'INSUFFICIENT_SAMPLE':
        print(f"  N: {edge2['n']} | WR: {edge2['win_rate']:.1%} | Avg R: {edge2['avg_r']:+.3f}")
        print(f"  Baseline: WR {edge2['baseline_wr']:.1%} | Avg R {edge2['baseline_avg_r']:+.3f}")
        print(f"  Improvement: WR {edge2['improvement_wr']:+.1f}% | Avg R {edge2['improvement_r']:+.1f}%")
        print(f"  IS/OOS: {edge2['is_wr']:.1%} / {edge2['oos_wr']:.1%}")
        print(f"  Pass Tests: {edge2['pass_tests']}")
    print()

    # Save summary
    summary = {
        'session_correlations': corr_results,
        'volatility_regime': vol_results,
        'orb_sequences': seq_results,
        'direction_continuation': dir_results,
        'tradeable_edges': {
            'edge1_0900_to_1800': edge1,
            'edge2_asia_up_to_1800': edge2
        }
    }

    import json

    # Clean the summary to remove any non-serializable objects
    def clean_for_json(obj):
        """Recursively clean objects for JSON serialization"""
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            # Skip non-serializable objects
            return str(obj)

    cleaned_summary = clean_for_json(summary)

    with open('outputs/NQ_SESSION_DEPENDENCIES.json', 'w') as f:
        json.dump(cleaned_summary, f, indent=2)

    print("=" * 80)
    print("Analysis complete.")
    print("Saved: outputs/NQ_SESSION_DEPENDENCIES.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
