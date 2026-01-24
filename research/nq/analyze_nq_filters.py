"""
Analyze ORB size vs ATR for NQ and find optimal filter thresholds
"""

import duckdb
import pandas as pd

def analyze_orb_filter(con, orb_name):
    """Analyze one ORB to find optimal size filter threshold."""

    # Get all trades with ORB size / ATR ratio
    df = pd.DataFrame(con.execute(f"""
        SELECT
            date_local,
            orb_{orb_name}_size,
            atr_20,
            orb_{orb_name}_size / NULLIF(atr_20, 0) as ratio,
            orb_{orb_name}_outcome,
            orb_{orb_name}_r_multiple
        FROM daily_features_v2_nq
        WHERE orb_{orb_name}_break_dir IS NOT NULL
        AND orb_{orb_name}_break_dir != 'NONE'
        AND atr_20 IS NOT NULL
        AND atr_20 > 0
    """).fetchdf())

    if len(df) == 0:
        return None

    # Baseline (no filter)
    baseline_trades = len(df)
    baseline_wins = len(df[df['orb_{}_outcome'.format(orb_name)] == 'WIN'])
    baseline_wr = baseline_wins / baseline_trades if baseline_trades > 0 else 0
    baseline_avg_r = df['orb_{}_r_multiple'.format(orb_name)].mean()

    # Test various thresholds
    thresholds = [0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.15, 0.18, 0.20, 0.25, 0.30]

    results = []
    for threshold in thresholds:
        # Filter: Keep only trades where ratio < threshold (small ORBs)
        filtered = df[df['ratio'] < threshold]

        if len(filtered) == 0:
            continue

        trades = len(filtered)
        wins = len(filtered[filtered['orb_{}_outcome'.format(orb_name)] == 'WIN'])
        wr = wins / trades if trades > 0 else 0
        avg_r = filtered['orb_{}_r_multiple'.format(orb_name)].mean()

        freq_pct = trades / baseline_trades * 100
        improvement = ((avg_r - baseline_avg_r) / abs(baseline_avg_r) * 100) if baseline_avg_r != 0 else 0

        results.append({
            'threshold': threshold,
            'trades': trades,
            'wr': wr,
            'avg_r': avg_r,
            'freq_pct': freq_pct,
            'improvement': improvement
        })

    return {
        'orb': orb_name,
        'baseline': {
            'trades': baseline_trades,
            'wr': baseline_wr,
            'avg_r': baseline_avg_r
        },
        'filters': results
    }


def main():
    con = duckdb.connect("../gold.db")

    print("=" * 80)
    print("NQ ORB SIZE FILTER ANALYSIS")
    print("=" * 80)
    print("")

    all_results = {}

    for orb in ['0900', '1000', '1100', '1800', '2300', '0030']:
        print(f"Analyzing {orb}...")
        result = analyze_orb_filter(con, orb)

        if result:
            all_results[orb] = result

            baseline = result['baseline']
            print(f"  Baseline: {baseline['trades']} trades, {baseline['wr']*100:.1f}% WR, {baseline['avg_r']:+.3f}R")

            # Find best filter (>5% improvement, >10% frequency)
            best = None
            for f in result['filters']:
                if f['improvement'] > 5 and f['freq_pct'] > 10:
                    if best is None or f['avg_r'] > best['avg_r']:
                        best = f

            if best:
                print(f"  BEST FILTER: {best['threshold']:.3f}")
                print(f"    Trades: {best['trades']} ({best['freq_pct']:.1f}%)")
                print(f"    WR: {best['wr']*100:.1f}%")
                print(f"    Avg R: {best['avg_r']:+.3f}R")
                print(f"    Improvement: {best['improvement']:+.1f}%")
            else:
                print(f"  NO FILTER RECOMMENDED (no >5% improvement with >10% frequency)")

            print("")

    # Summary table
    print("=" * 80)
    print("SUMMARY: RECOMMENDED FILTERS")
    print("=" * 80)
    print(f"{'ORB':<6} {'Baseline R':<12} {'Filter':<10} {'Filtered R':<12} {'Improvement':<12} {'Frequency':<10}")
    print("-" * 80)

    for orb, result in all_results.items():
        baseline = result['baseline']

        # Find best filter
        best = None
        for f in result['filters']:
            if f['improvement'] > 5 and f['freq_pct'] > 10:
                if best is None or f['avg_r'] > best['avg_r']:
                    best = f

        if best:
            print(f"{orb:<6} {baseline['avg_r']:+.3f}       {best['threshold']:.3f}      {best['avg_r']:+.3f}       {best['improvement']:+.1f}%        {best['freq_pct']:.1f}%")
        else:
            print(f"{orb:<6} {baseline['avg_r']:+.3f}       NONE       {baseline['avg_r']:+.3f}       --            100.0%")

    print("")
    print("Recommendation: Use filters only where improvement > 5% and frequency > 10%")

    con.close()


if __name__ == "__main__":
    main()
