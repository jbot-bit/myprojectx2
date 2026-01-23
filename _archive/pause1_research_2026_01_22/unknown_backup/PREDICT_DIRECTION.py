"""
PREDICT DIRECTION - NO LOOKAHEAD
=================================

QUESTION: Can we predict if 11:00 ORB will break UP or DOWN?

We'll analyze conditions BEFORE 11:00 that predict direction:
1. Where is price relative to prior levels? (09:00 high/low, Asia high/low)
2. What happened in 09:00-11:00 period? (trend, momentum)
3. Where does ORB sit relative to prior structure?
4. Gap conditions at Asia open?
5. Prior day's direction?

Compare:
- Trades that broke UP
- Trades that broke DOWN
- Find distinguishing features available BEFORE 11:05
"""

import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time as dt_time

def analyze_directional_bias():
    """Find conditions that predict UP vs DOWN breaks"""

    con = duckdb.connect("gold.db", read_only=True)

    # Get all 11:00 ORB trades with context
    query = """
    WITH orb_context AS (
        SELECT
            date_local,

            -- Prior sessions
            pre_asia_high,
            pre_asia_low,
            pre_asia_range,

            -- Asia session (09:00-11:00 available before 11:00 ORB)
            asia_high,
            asia_low,
            asia_range,

            -- 09:00 ORB (completes at 09:05, known before 11:00)
            orb_0900_high,
            orb_0900_low,
            orb_0900_size,
            orb_0900_break_dir,

            -- 10:00 ORB (completes at 10:05, known before 11:00)
            orb_1000_high,
            orb_1000_low,
            orb_1000_size,
            orb_1000_break_dir,

            -- 11:00 ORB itself
            orb_1100_high,
            orb_1100_low,
            orb_1100_size,
            orb_1100_break_dir,

            -- Volatility
            atr_20

        FROM daily_features_v2
        WHERE instrument = 'MGC'
            AND date_local >= '2024-01-02'
            AND date_local <= '2026-01-10'
            AND orb_1100_break_dir IS NOT NULL  -- Only days that broke
    )
    SELECT * FROM orb_context
    """

    df = pd.DataFrame(con.execute(query).fetchall(),
                     columns=['date', 'pre_asia_high', 'pre_asia_low', 'pre_asia_range',
                             'asia_high', 'asia_low', 'asia_range',
                             'orb_0900_high', 'orb_0900_low', 'orb_0900_size', 'orb_0900_break_dir',
                             'orb_1000_high', 'orb_1000_low', 'orb_1000_size', 'orb_1000_break_dir',
                             'orb_1100_high', 'orb_1100_low', 'orb_1100_size', 'orb_1100_break_dir',
                             'atr_20'])

    con.close()

    print(f"\n{'='*80}")
    print("DIRECTIONAL BIAS ANALYSIS - 11:00 ORB")
    print(f"{'='*80}\n")

    print(f"Total trades: {len(df)}")

    # Separate by direction
    up_breaks = df[df['orb_1100_break_dir'] == 'UP'].copy()
    down_breaks = df[df['orb_1100_break_dir'] == 'DOWN'].copy()

    print(f"UP breaks: {len(up_breaks)} ({len(up_breaks)/len(df)*100:.1f}%)")
    print(f"DOWN breaks: {len(down_breaks)} ({len(down_breaks)/len(df)*100:.1f}%)")

    # Calculate derived features (all available before 11:05)
    for direction_df in [up_breaks, down_breaks]:
        # ORB position relative to Asia range
        direction_df['orb_1100_mid'] = (direction_df['orb_1100_high'] + direction_df['orb_1100_low']) / 2
        direction_df['orb_mid_vs_asia_high'] = direction_df['orb_1100_mid'] - direction_df['asia_high']
        direction_df['orb_mid_vs_asia_low'] = direction_df['orb_1100_mid'] - direction_df['asia_low']

        # Where is ORB relative to Asia range? (0 = at low, 1 = at high)
        direction_df['orb_position_in_asia'] = (direction_df['orb_1100_mid'] - direction_df['asia_low']) / direction_df['asia_range']

        # ORB position relative to 09:00 ORB
        direction_df['orb_1100_vs_0900_high'] = direction_df['orb_1100_high'] - direction_df['orb_0900_high']
        direction_df['orb_1100_vs_0900_low'] = direction_df['orb_1100_low'] - direction_df['orb_0900_low']

        # 09:00 and 10:00 momentum alignment
        direction_df['orb_0900_is_up'] = (direction_df['orb_0900_break_dir'] == 'UP').astype(int)
        direction_df['orb_1000_is_up'] = (direction_df['orb_1000_break_dir'] == 'UP').astype(int)

    # Compare conditions
    print(f"\n{'='*80}")
    print("KEY DIFFERENCES: UP vs DOWN Breaks")
    print(f"{'='*80}\n")

    comparisons = []

    # Numeric features
    features = ['orb_1100_size', 'asia_range', 'pre_asia_range', 'atr_20',
               'orb_position_in_asia', 'orb_mid_vs_asia_high', 'orb_mid_vs_asia_low',
               'orb_1100_vs_0900_high', 'orb_1100_vs_0900_low',
               'orb_0900_size', 'orb_1000_size']

    for feat in features:
        if feat not in up_breaks.columns or feat not in down_breaks.columns:
            continue

        up_vals = up_breaks[feat].dropna()
        down_vals = down_breaks[feat].dropna()

        if len(up_vals) == 0 or len(down_vals) == 0:
            continue

        comparisons.append({
            'feature': feat,
            'up_median': up_vals.median(),
            'down_median': down_vals.median(),
            'up_mean': up_vals.mean(),
            'down_mean': down_vals.mean(),
            'difference': up_vals.median() - down_vals.median(),
            'pct_diff': ((up_vals.median() - down_vals.median()) / abs(down_vals.median()) * 100) if down_vals.median() != 0 else 0
        })

    comp_df = pd.DataFrame(comparisons)
    comp_df['abs_pct_diff'] = comp_df['pct_diff'].abs()
    comp_df = comp_df.sort_values('abs_pct_diff', ascending=False)

    print(f"{'Feature':<30} {'UP Median':<12} {'DOWN Median':<12} {'% Diff':<10}")
    print("-"*80)

    for _, row in comp_df.head(15).iterrows():
        print(f"{row['feature']:<30} {row['up_median']:>11.3f} {row['down_median']:>11.3f} {row['pct_diff']:>9.1f}%")

    # Categorical features (prior ORB directions)
    print(f"\n{'='*80}")
    print("PRIOR ORB MOMENTUM")
    print(f"{'='*80}\n")

    # 09:00 ORB direction
    orb_0900_up_count_when_1100_up = up_breaks['orb_0900_is_up'].sum()
    orb_0900_up_count_when_1100_down = down_breaks['orb_0900_is_up'].sum()

    print(f"When 09:00 ORB broke UP:")
    print(f"  11:00 broke UP:   {orb_0900_up_count_when_1100_up}/{len(up_breaks)} ({orb_0900_up_count_when_1100_up/len(up_breaks)*100:.1f}%)")
    print(f"  11:00 broke DOWN: {orb_0900_up_count_when_1100_down}/{len(down_breaks)} ({orb_0900_up_count_when_1100_down/len(down_breaks)*100:.1f}%)")

    # 10:00 ORB direction
    orb_1000_up_count_when_1100_up = up_breaks['orb_1000_is_up'].sum()
    orb_1000_up_count_when_1100_down = down_breaks['orb_1000_is_up'].sum()

    print(f"\nWhen 10:00 ORB broke UP:")
    print(f"  11:00 broke UP:   {orb_1000_up_count_when_1100_up}/{len(up_breaks)} ({orb_1000_up_count_when_1100_up/len(up_breaks)*100:.1f}%)")
    print(f"  11:00 broke DOWN: {orb_1000_up_count_when_1100_down}/{len(down_breaks)} ({orb_1000_up_count_when_1100_down/len(down_breaks)*100:.1f}%)")

    # Both aligned
    both_up_in_up_breaks = ((up_breaks['orb_0900_is_up'] == 1) & (up_breaks['orb_1000_is_up'] == 1)).sum()
    both_down_in_up_breaks = ((up_breaks['orb_0900_is_up'] == 0) & (up_breaks['orb_1000_is_up'] == 0)).sum()

    both_up_in_down_breaks = ((down_breaks['orb_0900_is_up'] == 1) & (down_breaks['orb_1000_is_up'] == 1)).sum()
    both_down_in_down_breaks = ((down_breaks['orb_0900_is_up'] == 0) & (down_breaks['orb_1000_is_up'] == 0)).sum()

    print(f"\nWhen 09:00 AND 10:00 BOTH broke UP:")
    print(f"  11:00 broke UP:   {both_up_in_up_breaks}/{len(up_breaks)} ({both_up_in_up_breaks/len(up_breaks)*100:.1f}%)")
    print(f"  11:00 broke DOWN: {both_up_in_down_breaks}/{len(down_breaks)} ({both_up_in_down_breaks/len(down_breaks)*100:.1f}%)")

    print(f"\nWhen 09:00 AND 10:00 BOTH broke DOWN:")
    print(f"  11:00 broke UP:   {both_down_in_up_breaks}/{len(up_breaks)} ({both_down_in_up_breaks/len(up_breaks)*100:.1f}%)")
    print(f"  11:00 broke DOWN: {both_down_in_down_breaks}/{len(down_breaks)} ({both_down_in_down_breaks/len(down_breaks)*100:.1f}%)")

    # Position in range analysis
    print(f"\n{'='*80}")
    print("ORB POSITION IN ASIA RANGE")
    print(f"{'='*80}\n")

    print("ORB position (0 = at Asia low, 1 = at Asia high):\n")

    up_position = up_breaks['orb_position_in_asia'].dropna()
    down_position = down_breaks['orb_position_in_asia'].dropna()

    print(f"UP breaks:   Median = {up_position.median():.2f}")
    print(f"DOWN breaks: Median = {down_position.median():.2f}")

    # Bucket analysis
    up_high = (up_position >= 0.6).sum()
    up_mid = ((up_position >= 0.4) & (up_position < 0.6)).sum()
    up_low = (up_position < 0.4).sum()

    down_high = (down_position >= 0.6).sum()
    down_mid = ((down_position >= 0.4) & (down_position < 0.6)).sum()
    down_low = (down_position < 0.4).sum()

    print(f"\nWhen ORB is in UPPER part of Asia range (>= 0.6):")
    print(f"  Breaks UP:   {up_high}/{len(up_position)} ({up_high/len(up_position)*100:.1f}%)")
    print(f"  Breaks DOWN: {down_high}/{len(down_position)} ({down_high/len(down_position)*100:.1f}%)")

    print(f"\nWhen ORB is in MIDDLE part of Asia range (0.4-0.6):")
    print(f"  Breaks UP:   {up_mid}/{len(up_position)} ({up_mid/len(up_position)*100:.1f}%)")
    print(f"  Breaks DOWN: {down_mid}/{len(down_position)} ({down_mid/len(down_position)*100:.1f}%)")

    print(f"\nWhen ORB is in LOWER part of Asia range (< 0.4):")
    print(f"  Breaks UP:   {up_low}/{len(up_position)} ({up_low/len(up_position)*100:.1f}%)")
    print(f"  Breaks DOWN: {down_low}/{len(down_position)} ({down_low/len(down_position)*100:.1f}%)")

    # Predictive filters
    print(f"\n{'='*80}")
    print("DIRECTIONAL FILTERS (Use BEFORE 11:05)")
    print(f"{'='*80}\n")

    filters = []

    # Filter 1: Momentum alignment
    momentum_up_df = df[(df['orb_0900_break_dir'] == 'UP') & (df['orb_1000_break_dir'] == 'UP')]
    if len(momentum_up_df) > 20:
        up_rate = (momentum_up_df['orb_1100_break_dir'] == 'UP').sum() / len(momentum_up_df)
        base_up_rate = len(up_breaks) / len(df)

        if up_rate > base_up_rate * 1.1:
            filters.append({
                'filter': "Both 09:00 and 10:00 broke UP (momentum continuation)",
                'direction': 'UP',
                'trades': len(momentum_up_df),
                'accuracy': up_rate,
                'improvement': (up_rate - base_up_rate) / base_up_rate * 100
            })

    momentum_down_df = df[(df['orb_0900_break_dir'] == 'DOWN') & (df['orb_1000_break_dir'] == 'DOWN')]
    if len(momentum_down_df) > 20:
        down_rate = (momentum_down_df['orb_1100_break_dir'] == 'DOWN').sum() / len(momentum_down_df)
        base_down_rate = len(down_breaks) / len(df)

        if down_rate > base_down_rate * 1.1:
            filters.append({
                'filter': "Both 09:00 and 10:00 broke DOWN (momentum continuation)",
                'direction': 'DOWN',
                'trades': len(momentum_down_df),
                'accuracy': down_rate,
                'improvement': (down_rate - base_down_rate) / base_down_rate * 100
            })

    # Filter 2: ORB position
    # Add position data back to main df
    df['orb_position_in_asia'] = (((df['orb_1100_high'] + df['orb_1100_low']) / 2) - df['asia_low']) / df['asia_range']

    high_position_df = df[df['orb_position_in_asia'] >= 0.6]
    if len(high_position_df) > 20:
        up_rate = (high_position_df['orb_1100_break_dir'] == 'UP').sum() / len(high_position_df)
        base_up_rate = len(up_breaks) / len(df)

        if up_rate > base_up_rate * 1.05:
            filters.append({
                'filter': "ORB in upper 40% of Asia range (likely to break UP)",
                'direction': 'UP',
                'trades': len(high_position_df),
                'accuracy': up_rate,
                'improvement': (up_rate - base_up_rate) / base_up_rate * 100
            })

    low_position_df = df[df['orb_position_in_asia'] < 0.4]
    if len(low_position_df) > 20:
        down_rate = (low_position_df['orb_1100_break_dir'] == 'DOWN').sum() / len(low_position_df)
        base_down_rate = len(down_breaks) / len(df)

        if down_rate > base_down_rate * 1.05:
            filters.append({
                'filter': "ORB in lower 40% of Asia range (likely to break DOWN)",
                'direction': 'DOWN',
                'trades': len(low_position_df),
                'accuracy': down_rate,
                'improvement': (down_rate - base_down_rate) / base_down_rate * 100
            })

    # Print filters
    if filters:
        print("PREDICTIVE FILTERS:\n")
        for i, f in enumerate(sorted(filters, key=lambda x: x['improvement'], reverse=True), 1):
            print(f"{i}. {f['filter']}")
            print(f"   Predicts: {f['direction']}")
            print(f"   Accuracy: {f['accuracy']*100:.1f}% ({f['trades']} trades)")
            print(f"   Improvement: {f['improvement']:+.1f}% over base\n")

    # Save data
    print(f"{'='*80}")
    print("Saving directional analysis to DIRECTION_PREDICTION.csv...")

    analysis_df = pd.concat([up_breaks.assign(actual_direction='UP'),
                            down_breaks.assign(actual_direction='DOWN')])
    analysis_df.to_csv("DIRECTION_PREDICTION.csv", index=False)
    print("Saved!")

    print(f"\n{'='*80}")
    print("SUMMARY - HOW TO PREDICT DIRECTION")
    print(f"{'='*80}\n")

    print("BEFORE 11:05, check these conditions:\n")

    print("1. MOMENTUM ALIGNMENT (strongest signal):")
    print("   - If 09:00 AND 10:00 both broke UP -> Expect 11:00 UP")
    print("   - If 09:00 AND 10:00 both broke DOWN -> Expect 11:00 DOWN")

    print("\n2. ORB POSITION IN ASIA RANGE:")
    print("   - ORB in upper 40% (>= 0.6) -> More likely UP")
    print("   - ORB in lower 40% (< 0.4) -> More likely DOWN")
    print("   - ORB in middle -> No clear bias")

    print("\n3. PRICE STRUCTURE:")
    best_feature = comp_df.iloc[0]
    print(f"   - {best_feature['feature']}: ")
    print(f"     UP breaks: {best_feature['up_median']:.2f}")
    print(f"     DOWN breaks: {best_feature['down_median']:.2f}")

    print("\nBase rates (no filter):")
    print(f"  UP breaks: {len(up_breaks)/len(df)*100:.1f}%")
    print(f"  DOWN breaks: {len(down_breaks)/len(df)*100:.1f}%")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    analyze_directional_bias()
