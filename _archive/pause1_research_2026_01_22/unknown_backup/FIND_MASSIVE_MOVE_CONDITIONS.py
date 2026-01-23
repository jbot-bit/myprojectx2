"""
MASSIVE MOVE CONDITIONS
=======================

QUESTION: What conditions predict the MASSIVE movers?

Not just 10R winners, but:
- Trades that hit 10R FAST (< 10 bars)
- Trades that went WAY beyond 10R (15R, 20R+)
- "Home run" setups vs "base hit" setups

We'll compare:
- MASSIVE winners (top 25% by max_favorable_r)
- Regular winners (bottom 75%)
- Losers

To find what makes the true motherloads.
"""

import pandas as pd
import numpy as np

def main():
    print("\n" + "="*80)
    print("MASSIVE MOVE CONDITIONS ANALYSIS")
    print("="*80)
    print("\nLoading trade data from BIG_MOVE_CONDITIONS.csv...\n")

    # Load all trades
    df = pd.read_csv("BIG_MOVE_CONDITIONS.csv")

    # Separate into categories
    winners = df[df['outcome'] == 'WIN'].copy()
    losers = df[df['outcome'] == 'LOSS'].copy()

    print(f"Total trades: {len(df)}")
    print(f"Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")

    # Define MASSIVE winners (top 25% by max favorable excursion)
    threshold_75 = winners['max_favorable_r'].quantile(0.75)
    threshold_50 = winners['max_favorable_r'].quantile(0.50)

    massive_winners = winners[winners['max_favorable_r'] >= threshold_75].copy()
    regular_winners = winners[winners['max_favorable_r'] < threshold_75].copy()

    print(f"\nMASSIVE winners (top 25% by max_favorable_r >= {threshold_75:.1f}R): {len(massive_winners)}")
    print(f"Regular winners (max_favorable_r < {threshold_75:.1f}R): {len(regular_winners)}")

    # Also define FAST winners (hit 10R in < 10 bars)
    fast_winners = winners[winners['bars_to_exit'] <= 10].copy()
    slow_winners = winners[winners['bars_to_exit'] > 10].copy()

    print(f"\nFAST winners (hit 10R in <= 10 bars): {len(fast_winners)}")
    print(f"Slow winners (hit 10R in > 10 bars): {len(slow_winners)}")

    # Print some examples
    print(f"\n{'='*80}")
    print("EXAMPLE MASSIVE MOVERS (Top 10 by max_favorable_r)")
    print(f"{'='*80}\n")

    top_movers = massive_winners.nlargest(10, 'max_favorable_r')
    print(f"{'Date':<12} {'Dir':<5} {'ORB Size':<10} {'Max R':<8} {'Bars':<6} {'Entry Delay':<12}")
    print("-"*80)

    for _, row in top_movers.iterrows():
        print(f"{str(row['date']):<12} {row['direction']:<5} {row['orb_size']:<10.2f} {row['max_favorable_r']:<8.1f} {row['bars_to_exit']:<6.0f} {row['entry_delay_minutes']:<12.1f}")

    # Compare conditions
    print(f"\n{'='*80}")
    print("MASSIVE vs REGULAR WINNERS - KEY DIFFERENCES")
    print(f"{'='*80}\n")

    numeric_cols = ['orb_size', 'orb_size_vs_atr', 'entry_delay_minutes',
                   'entry_distance_from_mid', 'atr_20', 'pre_asia_range',
                   'asia_range', 'london_range', 'bars_to_exit']

    comparisons = []

    for col in numeric_cols:
        if col not in df.columns:
            continue

        massive_vals = massive_winners[col].dropna()
        regular_vals = regular_winners[col].dropna()

        if len(massive_vals) == 0 or len(regular_vals) == 0:
            continue

        comparisons.append({
            'condition': col,
            'massive_median': massive_vals.median(),
            'regular_median': regular_vals.median(),
            'loser_median': losers[col].dropna().median() if len(losers[col].dropna()) > 0 else 0,
            'massive_mean': massive_vals.mean(),
            'regular_mean': regular_vals.mean(),
            'difference': massive_vals.median() - regular_vals.median(),
            'pct_difference': ((massive_vals.median() - regular_vals.median()) / regular_vals.median() * 100) if regular_vals.median() != 0 else 0
        })

    comp_df = pd.DataFrame(comparisons)
    comp_df['abs_pct_diff'] = comp_df['pct_difference'].abs()
    comp_df = comp_df.sort_values('abs_pct_diff', ascending=False)

    print(f"{'Condition':<30} {'Massive':<10} {'Regular':<10} {'Loser':<10} {'% Diff':<10}")
    print("-"*80)

    for _, row in comp_df.iterrows():
        print(f"{row['condition']:<30} {row['massive_median']:<10.2f} {row['regular_median']:<10.2f} {row['loser_median']:<10.2f} {row['pct_difference']:<+10.1f}%")

    # FAST vs SLOW winners
    print(f"\n{'='*80}")
    print("FAST vs SLOW WINNERS - KEY DIFFERENCES")
    print(f"{'='*80}\n")

    fast_comparisons = []

    for col in numeric_cols:
        if col not in df.columns or col == 'bars_to_exit':
            continue

        fast_vals = fast_winners[col].dropna()
        slow_vals = slow_winners[col].dropna()

        if len(fast_vals) == 0 or len(slow_vals) == 0:
            continue

        fast_comparisons.append({
            'condition': col,
            'fast_median': fast_vals.median(),
            'slow_median': slow_vals.median(),
            'difference': fast_vals.median() - slow_vals.median(),
            'pct_difference': ((fast_vals.median() - slow_vals.median()) / slow_vals.median() * 100) if slow_vals.median() != 0 else 0
        })

    fast_comp_df = pd.DataFrame(fast_comparisons)
    fast_comp_df['abs_pct_diff'] = fast_comp_df['pct_difference'].abs()
    fast_comp_df = fast_comp_df.sort_values('abs_pct_diff', ascending=False)

    print(f"{'Condition':<30} {'Fast (<= 10 bars)':<18} {'Slow (> 10 bars)':<18} {'% Diff':<10}")
    print("-"*80)

    for _, row in fast_comp_df.head(10).iterrows():
        print(f"{row['condition']:<30} {row['fast_median']:<18.2f} {row['slow_median']:<18.2f} {row['pct_difference']:<+10.1f}%")

    # Directional analysis for massive movers
    print(f"\n{'='*80}")
    print("DIRECTIONAL ANALYSIS - MASSIVE MOVERS")
    print(f"{'='*80}\n")

    massive_up = massive_winners[massive_winners['direction'] == 'UP']
    massive_down = massive_winners[massive_winners['direction'] == 'DOWN']

    print(f"MASSIVE UP movers: {len(massive_up)} ({len(massive_up)/len(massive_winners)*100:.1f}% of massive)")
    print(f"  Avg max_favorable_r: {massive_up['max_favorable_r'].mean():.1f}R")
    print(f"  Avg bars_to_exit: {massive_up['bars_to_exit'].mean():.0f}")

    print(f"\nMASSIVE DOWN movers: {len(massive_down)} ({len(massive_down)/len(massive_winners)*100:.1f}% of massive)")
    print(f"  Avg max_favorable_r: {massive_down['max_favorable_r'].mean():.1f}R")
    print(f"  Avg bars_to_exit: {massive_down['bars_to_exit'].mean():.0f}")

    # Find optimal filters for MASSIVE movers
    print(f"\n{'='*80}")
    print("FILTERS TO IDENTIFY MASSIVE MOVERS")
    print(f"{'='*80}\n")

    filters = []

    # ORB size filter
    if 'orb_size_vs_atr' in massive_winners.columns:
        threshold = massive_winners['orb_size_vs_atr'].median()

        filtered = df[df['orb_size_vs_atr'] >= threshold]
        massive_in_filtered = filtered[filtered['max_favorable_r'] >= threshold_75].shape[0]
        massive_rate = massive_in_filtered / len(filtered) if len(filtered) > 0 else 0

        base_massive_rate = len(massive_winners) / len(df)

        if massive_rate > base_massive_rate * 1.2:  # 20% better
            filters.append({
                'filter': f"ORB size >= {threshold:.2f} x ATR(20)",
                'trades': len(filtered),
                'massive_rate': massive_rate,
                'improvement': (massive_rate - base_massive_rate) / base_massive_rate * 100
            })

    # Asia range filter
    if 'asia_range' in massive_winners.columns:
        threshold = massive_winners['asia_range'].quantile(0.50)

        filtered = df[df['asia_range'] >= threshold]
        massive_in_filtered = filtered[filtered['max_favorable_r'] >= threshold_75].shape[0]
        massive_rate = massive_in_filtered / len(filtered) if len(filtered) > 0 else 0

        base_massive_rate = len(massive_winners) / len(df)

        if massive_rate > base_massive_rate * 1.2:
            filters.append({
                'filter': f"Asia range >= {threshold:.1f} pts",
                'trades': len(filtered),
                'massive_rate': massive_rate,
                'improvement': (massive_rate - base_massive_rate) / base_massive_rate * 100
            })

    # Entry delay filter (quick entries)
    if 'entry_delay_minutes' in massive_winners.columns:
        threshold = 2  # 2 minutes

        filtered = df[df['entry_delay_minutes'] <= threshold]
        massive_in_filtered = filtered[filtered['max_favorable_r'] >= threshold_75].shape[0]
        massive_rate = massive_in_filtered / len(filtered) if len(filtered) > 0 else 0

        base_massive_rate = len(massive_winners) / len(df)

        if massive_rate > base_massive_rate * 1.1:
            filters.append({
                'filter': f"Entry within {threshold} minutes",
                'trades': len(filtered),
                'massive_rate': massive_rate,
                'improvement': (massive_rate - base_massive_rate) / base_massive_rate * 100
            })

    # Direction filter
    up_massive_rate = len(massive_up) / len(df[df['direction'] == 'UP'])
    down_massive_rate = len(massive_down) / len(df[df['direction'] == 'DOWN'])
    base_massive_rate = len(massive_winners) / len(df)

    if up_massive_rate > base_massive_rate * 1.2:
        filters.append({
            'filter': "Trade UP breaks only",
            'trades': len(df[df['direction'] == 'UP']),
            'massive_rate': up_massive_rate,
            'improvement': (up_massive_rate - base_massive_rate) / base_massive_rate * 100
        })

    # Print filters
    if filters:
        print("RECOMMENDED FILTERS FOR MASSIVE MOVERS:\n")
        for i, f in enumerate(sorted(filters, key=lambda x: x['improvement'], reverse=True), 1):
            print(f"{i}. {f['filter']}")
            print(f"   -> {f['trades']} trades")
            print(f"   -> {f['massive_rate']*100:.1f}% chance of MASSIVE move")
            print(f"   -> {f['improvement']:+.1f}% improvement over base\n")

    # Combined filter
    print("="*80)
    print("COMBINED FILTER TEST - MASSIVE MOVERS")
    print("="*80)

    # Apply top filters
    filtered = df.copy()
    applied = []

    for f in sorted(filters, key=lambda x: x['improvement'], reverse=True)[:3]:
        if "ORB size" in f['filter'] and 'orb_size_vs_atr' in filtered.columns:
            threshold = float(f['filter'].split('>=')[1].split('x')[0].strip())
            filtered = filtered[filtered['orb_size_vs_atr'] >= threshold]
            applied.append(f['filter'])

        if "Asia range" in f['filter'] and 'asia_range' in filtered.columns:
            threshold = float(f['filter'].split('>=')[1].split('pts')[0].strip())
            filtered = filtered[filtered['asia_range'] >= threshold]
            applied.append(f['filter'])

        if "Entry within" in f['filter'] and 'entry_delay_minutes' in filtered.columns:
            threshold = int(f['filter'].split('within')[1].split('minutes')[0].strip())
            filtered = filtered[filtered['entry_delay_minutes'] <= threshold]
            applied.append(f['filter'])

        if "UP breaks" in f['filter']:
            filtered = filtered[filtered['direction'] == 'UP']
            applied.append(f['filter'])

    if len(applied) > 0 and len(filtered) > 10:
        filtered_massive = filtered[filtered['max_favorable_r'] >= threshold_75]
        filtered_winners = filtered[filtered['outcome'] == 'WIN']

        print(f"\nApplied {len(applied)} filters:")
        for a in applied:
            print(f"  - {a}")

        print(f"\nResults:")
        print(f"  Trades: {len(filtered)} (from {len(df)})")
        print(f"  Winners: {len(filtered_winners)} ({len(filtered_winners)/len(filtered)*100:.1f}%)")
        print(f"  MASSIVE movers: {len(filtered_massive)} ({len(filtered_massive)/len(filtered)*100:.1f}%)")
        print(f"  Base massive rate: {len(massive_winners)/len(df)*100:.1f}%")
        print(f"  Improvement: {(len(filtered_massive)/len(filtered) - len(massive_winners)/len(df))/(len(massive_winners)/len(df))*100:+.1f}%")

        if len(filtered_winners) > 0:
            avg_max_r = filtered_winners['max_favorable_r'].mean()
            print(f"  Avg max_favorable_r of winners: {avg_max_r:.1f}R")

    # Save massive movers
    print(f"\n{'='*80}")
    print("Saving MASSIVE movers to MASSIVE_MOVERS.csv...")
    massive_winners.to_csv("MASSIVE_MOVERS.csv", index=False)
    print("Saved!")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print("KEY FINDINGS:")
    print(f"1. MASSIVE movers (top 25%) have max_favorable_r >= {threshold_75:.1f}R")
    print(f"2. They are characterized by:")

    # Top 3 differences
    for _, row in comp_df.head(3).iterrows():
        print(f"   - {row['condition']}: {row['massive_median']:.1f} vs {row['regular_median']:.1f} (regular)")

    print(f"\n3. Use the filters above to identify high-probability MASSIVE setups")
    print(f"4. Check MASSIVE_MOVERS.csv for examples to study\n")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
