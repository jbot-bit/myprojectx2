"""
TOP 10 ASIA MOTHERLOADS - DEEP ANALYSIS
========================================

Analyzes the top 10 setups from ASIA_MOTHERLOADS_CLEAN.csv:
1. Month-by-month performance
2. Temporal stability (2024 vs 2025)
3. Drawdown analysis
4. Trade distribution
5. Hold time patterns
6. Directional bias details
"""

import pandas as pd
import numpy as np
import duckdb
from datetime import datetime, timedelta, date, time as dt_time
from ASIA_ORB_CLEAN import simulate_trade

def analyze_setup_temporal(orb_hour, orb_minute, duration, sl_mode, rr, direction_filter):
    """Analyze a setup's performance over time"""

    con = duckdb.connect("gold.db", read_only=True)

    dates_query = """
    SELECT DISTINCT date_local
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    dates = [row[0] for row in con.execute(dates_query).fetchall()]

    # Simulate all trades
    trades = []
    for d in dates:
        result = simulate_trade(con, d, orb_hour, orb_minute, duration, sl_mode, rr, direction_filter)
        if result:
            trades.append({
                'date': d,
                'outcome': result['outcome'],
                'r': result['r'],
                'hold_hours': result['hold_hours'],
                'direction': result['direction']
            })

    con.close()

    if not trades:
        return None

    df = pd.DataFrame(trades)
    df['date'] = pd.to_datetime(df['date'])

    # Overall stats
    total_trades = len(df)
    wins = len(df[df['outcome'] == 'WIN'])
    win_rate = wins / total_trades
    total_r = df['r'].sum()
    avg_r = df['r'].mean()

    # Cumulative R curve
    df['cum_r'] = df['r'].cumsum()

    # Max drawdown
    df['peak'] = df['cum_r'].cummax()
    df['drawdown'] = df['cum_r'] - df['peak']
    max_dd = df['drawdown'].min()

    # Worst losing streak
    df['is_loss'] = df['outcome'] == 'LOSS'
    df['loss_streak'] = df['is_loss'].cumsum() - df['is_loss'].cumsum().where(~df['is_loss']).ffill().fillna(0)
    max_loss_streak = int(df['loss_streak'].max())

    # Best winning streak
    df['is_win'] = df['outcome'] == 'WIN'
    df['win_streak'] = df['is_win'].cumsum() - df['is_win'].cumsum().where(~df['is_win']).ffill().fillna(0)
    max_win_streak = int(df['win_streak'].max())

    # Monthly performance
    df['year_month'] = df['date'].dt.to_period('M')
    monthly = df.groupby('year_month').agg({
        'r': ['sum', 'count', 'mean'],
        'outcome': lambda x: (x == 'WIN').sum()
    }).reset_index()
    monthly.columns = ['month', 'monthly_r', 'trades', 'avg_r', 'wins']
    monthly['win_rate'] = monthly['wins'] / monthly['trades']

    # Split by year
    df_2024 = df[df['date'].dt.year == 2024]
    df_2025 = df[df['date'].dt.year == 2025]
    df_2026 = df[df['date'].dt.year == 2026]

    year_2024_r = df_2024['r'].sum() if len(df_2024) > 0 else 0
    year_2024_trades = len(df_2024)
    year_2024_wr = (df_2024['outcome'] == 'WIN').sum() / len(df_2024) if len(df_2024) > 0 else 0

    year_2025_r = df_2025['r'].sum() if len(df_2025) > 0 else 0
    year_2025_trades = len(df_2025)
    year_2025_wr = (df_2025['outcome'] == 'WIN').sum() / len(df_2025) if len(df_2025) > 0 else 0

    year_2026_r = df_2026['r'].sum() if len(df_2026) > 0 else 0
    year_2026_trades = len(df_2026)
    year_2026_wr = (df_2026['outcome'] == 'WIN').sum() / len(df_2026) if len(df_2026) > 0 else 0

    # Directional stats
    up_trades = df[df['direction'] == 'UP']
    down_trades = df[df['direction'] == 'DOWN']

    up_wr = (up_trades['outcome'] == 'WIN').sum() / len(up_trades) if len(up_trades) > 0 else 0
    down_wr = (down_trades['outcome'] == 'WIN').sum() / len(down_trades) if len(down_trades) > 0 else 0

    up_avg_r = up_trades['r'].mean() if len(up_trades) > 0 else 0
    down_avg_r = down_trades['r'].mean() if len(down_trades) > 0 else 0

    # Hold time analysis
    median_hold = df['hold_hours'].median()
    mean_hold = df['hold_hours'].mean()
    max_hold = df['hold_hours'].max()

    win_hold = df[df['outcome'] == 'WIN']['hold_hours'].median() if len(df[df['outcome'] == 'WIN']) > 0 else 0
    loss_hold = df[df['outcome'] == 'LOSS']['hold_hours'].median() if len(df[df['outcome'] == 'LOSS']) > 0 else 0

    return {
        'total_trades': total_trades,
        'wins': wins,
        'win_rate': win_rate,
        'total_r': total_r,
        'avg_r': avg_r,
        'max_dd': max_dd,
        'max_loss_streak': max_loss_streak,
        'max_win_streak': max_win_streak,
        'monthly': monthly,
        'year_2024_r': year_2024_r,
        'year_2024_trades': year_2024_trades,
        'year_2024_wr': year_2024_wr,
        'year_2025_r': year_2025_r,
        'year_2025_trades': year_2025_trades,
        'year_2025_wr': year_2025_wr,
        'year_2026_r': year_2026_r,
        'year_2026_trades': year_2026_trades,
        'year_2026_wr': year_2026_wr,
        'up_trades': len(up_trades),
        'down_trades': len(down_trades),
        'up_wr': up_wr,
        'down_wr': down_wr,
        'up_avg_r': up_avg_r,
        'down_avg_r': down_avg_r,
        'median_hold': median_hold,
        'mean_hold': mean_hold,
        'max_hold': max_hold,
        'win_hold': win_hold,
        'loss_hold': loss_hold,
        'cum_r_curve': df[['date', 'cum_r']].to_dict('records')
    }


def main():
    print("\n" + "="*80)
    print("TOP 10 ASIA MOTHERLOADS - DEEP ANALYSIS")
    print("="*80)

    # Load top 10
    df = pd.read_csv("ASIA_MOTHERLOADS_CLEAN.csv")
    df = df.sort_values('avg_r', ascending=False).head(10)

    print(f"\nAnalyzing top 10 setups...\n")

    results = []

    for i, row in df.iterrows():
        orb_time = row['orb_time']
        hour, minute = map(int, orb_time.split(':'))
        duration = int(row['duration_min'])
        sl_mode = row['sl_mode']
        rr = float(row['rr'])
        direction = row['direction'] if row['direction'] != 'ANY' else None

        print(f"Analyzing #{len(results)+1}: {orb_time} ORB, {duration}min, {sl_mode}, RR={rr}...")

        analysis = analyze_setup_temporal(hour, minute, duration, sl_mode, rr, direction)
        if analysis:
            results.append({
                'setup': f"{orb_time} {duration}min {sl_mode} RR{rr}",
                'orb_time': orb_time,
                'duration': duration,
                'sl_mode': sl_mode,
                'rr': rr,
                'direction': direction if direction else 'ANY',
                **analysis
            })

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}\n")

    # Print detailed report
    for i, r in enumerate(results, 1):
        print(f"\n{'='*80}")
        print(f"#{i}: {r['setup']}")
        print(f"{'='*80}\n")

        print(f"OVERALL PERFORMANCE:")
        print(f"  Total trades:     {r['total_trades']}")
        print(f"  Win rate:         {r['win_rate']*100:.1f}%")
        print(f"  Avg R/trade:      {r['avg_r']:+.3f}R")
        print(f"  Total R:          {r['total_r']:+.1f}R")
        print(f"  Annual R:         {r['total_r']/2.0:+.0f}R/year")
        print(f"  Max drawdown:     {r['max_dd']:.1f}R")
        print(f"  Max loss streak:  {r['max_loss_streak']} trades")
        print(f"  Max win streak:   {r['max_win_streak']} trades")

        print(f"\nTEMPORAL STABILITY:")
        print(f"  2024: {r['year_2024_trades']} trades, {r['year_2024_wr']*100:.1f}% WR, {r['year_2024_r']:+.1f}R")
        print(f"  2025: {r['year_2025_trades']} trades, {r['year_2025_wr']*100:.1f}% WR, {r['year_2025_r']:+.1f}R")
        if r['year_2026_trades'] > 0:
            print(f"  2026: {r['year_2026_trades']} trades, {r['year_2026_wr']*100:.1f}% WR, {r['year_2026_r']:+.1f}R (partial)")

        print(f"\nDIRECTIONAL BIAS:")
        print(f"  UP:   {r['up_trades']} trades ({r['up_trades']/r['total_trades']*100:.1f}%), {r['up_wr']*100:.1f}% WR, {r['up_avg_r']:+.3f}R avg")
        print(f"  DOWN: {r['down_trades']} trades ({r['down_trades']/r['total_trades']*100:.1f}%), {r['down_wr']*100:.1f}% WR, {r['down_avg_r']:+.3f}R avg")

        print(f"\nHOLD TIMES:")
        print(f"  Median:      {r['median_hold']:.1f} hours")
        print(f"  Mean:        {r['mean_hold']:.1f} hours")
        print(f"  Max:         {r['max_hold']:.1f} hours")
        print(f"  Winners:     {r['win_hold']:.1f} hours (median)")
        print(f"  Losers:      {r['loss_hold']:.1f} hours (median)")

        # Monthly breakdown
        print(f"\nMONTHLY BREAKDOWN (Best 5 months):")
        monthly = r['monthly'].sort_values('monthly_r', ascending=False).head(5)
        for _, m in monthly.iterrows():
            print(f"  {m['month']}: {m['trades']:3.0f} trades, {m['win_rate']*100:5.1f}% WR, {m['monthly_r']:+6.1f}R ({m['avg_r']:+.3f}R avg)")

        print(f"\nWORST 3 MONTHS:")
        monthly_worst = r['monthly'].sort_values('monthly_r', ascending=True).head(3)
        for _, m in monthly_worst.iterrows():
            print(f"  {m['month']}: {m['trades']:3.0f} trades, {m['win_rate']*100:5.1f}% WR, {m['monthly_r']:+6.1f}R ({m['avg_r']:+.3f}R avg)")

    # Comparative summary
    print(f"\n\n{'='*80}")
    print("COMPARATIVE SUMMARY - TOP 10")
    print(f"{'='*80}\n")

    summary_df = pd.DataFrame([{
        'Rank': i,
        'Setup': r['setup'][:30],
        'Trades': r['total_trades'],
        'WR%': r['win_rate']*100,
        'Avg R': r['avg_r'],
        'Total R': r['total_r'],
        'Max DD': r['max_dd'],
        'Sharpe': r['avg_r'] / (r['monthly']['avg_r'].std() if len(r['monthly']) > 1 else 1),
        '2024 R': r['year_2024_r'],
        '2025 R': r['year_2025_r']
    } for i, r in enumerate(results, 1)])

    print(summary_df.to_string(index=False))

    # Save detailed results
    print(f"\n\nSaving detailed analysis to TOP10_ANALYSIS.csv...")

    detailed_df = pd.DataFrame([{
        'rank': i,
        'setup': r['setup'],
        'orb_time': r['orb_time'],
        'duration': r['duration'],
        'sl_mode': r['sl_mode'],
        'rr': r['rr'],
        'direction': r['direction'],
        'total_trades': r['total_trades'],
        'win_rate': r['win_rate'],
        'avg_r': r['avg_r'],
        'total_r': r['total_r'],
        'annual_r': r['total_r']/2.0,
        'max_dd': r['max_dd'],
        'max_loss_streak': r['max_loss_streak'],
        'max_win_streak': r['max_win_streak'],
        'year_2024_r': r['year_2024_r'],
        'year_2024_trades': r['year_2024_trades'],
        'year_2024_wr': r['year_2024_wr'],
        'year_2025_r': r['year_2025_r'],
        'year_2025_trades': r['year_2025_trades'],
        'year_2025_wr': r['year_2025_wr'],
        'up_trades': r['up_trades'],
        'down_trades': r['down_trades'],
        'up_wr': r['up_wr'],
        'down_wr': r['down_wr'],
        'up_avg_r': r['up_avg_r'],
        'down_avg_r': r['down_avg_r'],
        'median_hold_hours': r['median_hold'],
        'mean_hold_hours': r['mean_hold'],
        'win_hold_hours': r['win_hold'],
        'loss_hold_hours': r['loss_hold']
    } for i, r in enumerate(results, 1)])

    detailed_df.to_csv("TOP10_ANALYSIS.csv", index=False)
    print("Saved!")

    print(f"\n{'='*80}")
    print("KEY FINDINGS")
    print(f"{'='*80}\n")

    # Best by different metrics
    best_wr = max(results, key=lambda x: x['win_rate'])
    best_r = max(results, key=lambda x: x['avg_r'])
    best_dd = min(results, key=lambda x: x['max_dd'])

    print(f"HIGHEST WIN RATE:")
    print(f"  {best_wr['setup']}: {best_wr['win_rate']*100:.1f}% WR, {best_wr['avg_r']:+.3f}R avg\n")

    print(f"HIGHEST AVG R:")
    print(f"  {best_r['setup']}: {best_r['avg_r']:+.3f}R avg, {best_r['win_rate']*100:.1f}% WR\n")

    print(f"SMALLEST DRAWDOWN:")
    print(f"  {best_dd['setup']}: {best_dd['max_dd']:.1f}R max DD, {best_dd['avg_r']:+.3f}R avg\n")

    # Common patterns
    print(f"COMMON PATTERNS:")
    orb_times = [r['orb_time'] for r in results]
    sl_modes = [r['sl_mode'] for r in results]

    from collections import Counter
    orb_counter = Counter(orb_times)
    sl_counter = Counter(sl_modes)

    print(f"  Most common ORB time: {orb_counter.most_common(1)[0][0]} ({orb_counter.most_common(1)[0][1]}/10 setups)")
    print(f"  Most common SL mode:  {sl_counter.most_common(1)[0][0]} ({sl_counter.most_common(1)[0][1]}/10 setups)")

    avg_rr = np.mean([r['rr'] for r in results])
    print(f"  Average RR:           {avg_rr:.1f}x")

    print(f"\n{'='*80}")
    print("DONE! Check TOP10_ANALYSIS.csv for full details.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
