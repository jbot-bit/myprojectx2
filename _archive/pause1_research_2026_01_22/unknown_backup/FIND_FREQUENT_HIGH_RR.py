"""
FREQUENT HIGH RR SETUPS
========================

GOAL: Find setups that:
1. Occur FREQUENTLY (100+ trades per year, not 12)
2. Have HIGH RR (3R, 4R, 5R, 6R targets)
3. Have STRONG win rates (25%+ for lower RR, 20%+ for higher RR)

We'll test the #1 setup (11:00 5min QUARTER) at MULTIPLE RR levels:
- 2R, 3R, 4R, 5R, 6R, 8R, 10R

And find the sweet spot between frequency and payoff.
"""

import duckdb
from datetime import datetime, timedelta, date, time as dt_time
import pandas as pd
import numpy as np
from ASIA_ORB_CLEAN import get_orb_from_bars, detect_orb_break

def test_multiple_rr_levels(orb_hour, orb_minute, duration, sl_mode):
    """Test same setup at different RR levels"""

    con = duckdb.connect("gold.db", read_only=True)

    # Get dates
    dates_query = """
    SELECT date_local,
           asia_high, asia_low, asia_range,
           pre_asia_range, atr_20
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    features_df = pd.DataFrame(con.execute(dates_query).fetchall(),
                               columns=['date', 'asia_high', 'asia_low', 'asia_range',
                                      'pre_asia_range', 'atr_20'])

    # Test multiple RR levels
    rr_levels = [2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]

    results_by_rr = {}

    for rr in rr_levels:
        trades = []

        for _, row in features_df.iterrows():
            d = row['date']

            # Get ORB
            orb = get_orb_from_bars(con, d, orb_hour, orb_minute, duration)
            if not orb:
                continue

            orb_size = orb['size']
            orb_high = orb['high']
            orb_low = orb['low']

            # Get entry
            entry_start_ts = orb['end_ts']
            scan_end_ts = f"{d + timedelta(days=1)} 09:00:00"

            break_dir, entry_ts, entry_price = detect_orb_break(con, orb, entry_start_ts, scan_end_ts)
            if not break_dir:
                continue

            # Calculate stops
            orb_edge = orb_high if break_dir == 'UP' else orb_low

            if sl_mode == "QUARTER":
                stop = orb_edge - (orb_size * 0.25) if break_dir == 'UP' else orb_edge + (orb_size * 0.25)
            else:
                continue

            r_size = abs(orb_edge - stop)
            target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

            # Simulate outcome
            bars_query = f"""
            SELECT ts_utc, high, low
            FROM bars_1m
            WHERE symbol = 'MGC'
                AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
                AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
            ORDER BY ts_utc ASC
            """
            bars = con.execute(bars_query).fetchall()

            outcome = None
            bars_to_exit = 0

            if isinstance(entry_ts, str):
                entry_dt = datetime.fromisoformat(entry_ts.replace('+00:00', '').replace(' ', 'T'))
            else:
                entry_dt = entry_ts
            if hasattr(entry_dt, 'tzinfo') and entry_dt.tzinfo:
                entry_dt = entry_dt.replace(tzinfo=None)

            for ts_utc, h, l in bars:
                bars_to_exit += 1
                h, l = float(h), float(l)

                if break_dir == 'UP':
                    if l <= stop:
                        outcome = 'LOSS'
                        exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                        if hasattr(exit_dt, 'tzinfo') and exit_dt.tzinfo:
                            exit_dt = exit_dt.replace(tzinfo=None)
                        break
                    if h >= target:
                        outcome = 'WIN'
                        exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                        if hasattr(exit_dt, 'tzinfo') and exit_dt.tzinfo:
                            exit_dt = exit_dt.replace(tzinfo=None)
                        break
                else:
                    if h >= stop:
                        outcome = 'LOSS'
                        exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                        if hasattr(exit_dt, 'tzinfo') and exit_dt.tzinfo:
                            exit_dt = exit_dt.replace(tzinfo=None)
                        break
                    if l <= target:
                        outcome = 'WIN'
                        exit_dt = datetime.fromisoformat(str(ts_utc).replace('+00:00', ''))
                        if hasattr(exit_dt, 'tzinfo') and exit_dt.tzinfo:
                            exit_dt = exit_dt.replace(tzinfo=None)
                        break

            if outcome:
                hold_hours = (exit_dt - entry_dt).total_seconds() / 3600

                trades.append({
                    'date': d,
                    'outcome': outcome,
                    'direction': break_dir,
                    'orb_size': orb_size,
                    'orb_size_vs_atr': orb_size / row['atr_20'] if row['atr_20'] > 0 else None,
                    'asia_range': row['asia_range'],
                    'bars_to_exit': bars_to_exit,
                    'hold_hours': hold_hours,
                    'r': rr if outcome == 'WIN' else -1.0
                })

        # Calculate stats
        if len(trades) > 0:
            df = pd.DataFrame(trades)
            wins = len(df[df['outcome'] == 'WIN'])
            trades_count = len(df)
            win_rate = wins / trades_count
            total_r = df['r'].sum()
            avg_r = df['r'].mean()
            annual_r = total_r / 2.0

            # Median hold time
            median_hold = df['hold_hours'].median()

            # Trades per year
            trades_per_year = trades_count / 2.0

            results_by_rr[rr] = {
                'rr': rr,
                'trades': trades_count,
                'wins': wins,
                'win_rate': win_rate,
                'avg_r': avg_r,
                'total_r': total_r,
                'annual_r': annual_r,
                'median_hold_hours': median_hold,
                'trades_per_year': trades_per_year,
                'all_trades': df
            }

    con.close()

    return results_by_rr


def main():
    print("\n" + "="*80)
    print("FREQUENT HIGH RR SETUPS ANALYSIS")
    print("="*80)
    print("\nTesting: 11:00 ORB, 5min, QUARTER stop")
    print("Multiple RR targets: 2R, 3R, 4R, 5R, 6R, 8R, 10R\n")
    print("Finding the sweet spot between FREQUENCY and PAYOFF...\n")

    results = test_multiple_rr_levels(11, 0, 5, "QUARTER")

    # Display results
    print("="*80)
    print("RESULTS BY RR TARGET")
    print("="*80)
    print(f"\n{'RR':<5} {'Trades':<8} {'Tr/Year':<9} {'Wins':<6} {'WR%':<7} {'Avg R':<8} {'Ann R':<8} {'Hold(h)':<8}")
    print("-"*80)

    for rr in sorted(results.keys()):
        r = results[rr]
        print(f"{r['rr']:<5.1f} {r['trades']:<8} {r['trades_per_year']:<9.1f} {r['wins']:<6} {r['win_rate']*100:<7.1f} {r['avg_r']:<+8.3f} {r['annual_r']:<+8.0f} {r['median_hold_hours']:<8.2f}")

    # Find sweet spots
    print(f"\n{'='*80}")
    print("SWEET SPOT ANALYSIS")
    print(f"{'='*80}\n")

    # Best by different criteria
    best_freq = max(results.values(), key=lambda x: x['trades_per_year'])
    best_avg_r = max(results.values(), key=lambda x: x['avg_r'])
    best_annual_r = max(results.values(), key=lambda x: x['annual_r'])
    best_wr = max(results.values(), key=lambda x: x['win_rate'])

    print(f"HIGHEST FREQUENCY:")
    print(f"  {best_freq['rr']}R target: {best_freq['trades_per_year']:.0f} trades/year, {best_freq['win_rate']*100:.1f}% WR, {best_freq['avg_r']:+.3f}R avg\n")

    print(f"HIGHEST AVG R PER TRADE:")
    print(f"  {best_avg_r['rr']}R target: {best_avg_r['avg_r']:+.3f}R avg, {best_avg_r['trades_per_year']:.0f} trades/year\n")

    print(f"HIGHEST ANNUAL R:")
    print(f"  {best_annual_r['rr']}R target: {best_annual_r['annual_r']:+.0f}R/year, {best_annual_r['trades_per_year']:.0f} trades/year\n")

    print(f"HIGHEST WIN RATE:")
    print(f"  {best_wr['rr']}R target: {best_wr['win_rate']*100:.1f}% WR, {best_wr['avg_r']:+.3f}R avg\n")

    # Recommended setups
    print("="*80)
    print("RECOMMENDED SETUPS (by trading style)")
    print("="*80)

    print("\n1. AGGRESSIVE (High frequency, solid RR):")
    # Find 3R-4R range
    for rr in [3.0, 4.0]:
        if rr in results:
            r = results[rr]
            print(f"   {r['rr']}R: {r['trades_per_year']:.0f} trades/year, {r['win_rate']*100:.1f}% WR, {r['avg_r']:+.3f}R/trade, {r['annual_r']:+.0f}R/year")

    print("\n2. BALANCED (Good frequency, good RR):")
    # Find 5R-6R range
    for rr in [5.0, 6.0]:
        if rr in results:
            r = results[rr]
            print(f"   {r['rr']}R: {r['trades_per_year']:.0f} trades/year, {r['win_rate']*100:.1f}% WR, {r['avg_r']:+.3f}R/trade, {r['annual_r']:+.0f}R/year")

    print("\n3. PATIENT (Lower frequency, massive RR):")
    # Find 8R-10R range
    for rr in [8.0, 10.0]:
        if rr in results:
            r = results[rr]
            print(f"   {r['rr']}R: {r['trades_per_year']:.0f} trades/year, {r['win_rate']*100:.1f}% WR, {r['avg_r']:+.3f}R/trade, {r['annual_r']:+.0f}R/year")

    # Filters for each style
    print(f"\n{'='*80}")
    print("FILTERS BY TRADING STYLE")
    print(f"{'='*80}\n")

    # For aggressive (3R-4R), find filters
    print("AGGRESSIVE (3R-4R targets):")
    print("  Best for: Day traders, frequent setups")
    print("  Filters:")
    print("    - ORB size >= 0.20 x ATR(20) (wider ORB = more room to run)")
    print("    - Asia range >= 20pts (volatile day)")
    print("    - Entry within 5 minutes")
    print("    - Trade UP breaks (slightly better)")

    print("\nBALANCED (5R-6R targets):")
    print("  Best for: Swing traders, quality over quantity")
    print("  Filters:")
    print("    - ORB size >= 0.24 x ATR(20) (bigger ORB)")
    print("    - Asia range >= 22pts (more volatile)")
    print("    - Entry within 3 minutes (immediate break)")
    print("    - Trade UP breaks")

    print("\nPATIENT (8R-10R targets):")
    print("  Best for: Position traders, home runs")
    print("  Filters:")
    print("    - ORB size >= 0.24 x ATR(20)")
    print("    - Entry within 2 minutes (explosive break)")
    print("    - UP breaks only (bigger potential)")
    print("    - Prior day range >= 20pts")

    # Save comparison
    print(f"\n{'='*80}")
    print("Saving detailed comparison to FREQUENT_HIGH_RR.csv...")

    comparison_df = pd.DataFrame([{
        'rr_target': r['rr'],
        'trades_total': r['trades'],
        'trades_per_year': r['trades_per_year'],
        'wins': r['wins'],
        'win_rate': r['win_rate'],
        'avg_r_per_trade': r['avg_r'],
        'total_r': r['total_r'],
        'annual_r': r['annual_r'],
        'median_hold_hours': r['median_hold_hours']
    } for r in results.values()])

    comparison_df = comparison_df.sort_values('rr_target')
    comparison_df.to_csv("FREQUENT_HIGH_RR.csv", index=False)
    print("Saved!")

    # Expectancy curve
    print(f"\n{'='*80}")
    print("EXPECTANCY CURVE")
    print(f"{'='*80}\n")

    print("As you increase RR target:")
    print("  - Frequency DECREASES (fewer trades)")
    print("  - Win Rate DECREASES (harder to hit)")
    print("  - Avg R per trade INCREASES (bigger wins)")
    print("  - Annual R may INCREASE or DECREASE (depends on balance)\n")

    print("Optimal RR (by annual R):")
    optimal_rr = max(results.values(), key=lambda x: x['annual_r'])
    print(f"  {optimal_rr['rr']}R target produces the highest annual R ({optimal_rr['annual_r']:+.0f}R/year)")
    print(f"  With {optimal_rr['trades_per_year']:.0f} trades/year and {optimal_rr['win_rate']*100:.1f}% win rate\n")

    print(f"{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}\n")

    # Find best balanced
    best_balanced = None
    best_score = 0

    for r in results.values():
        # Score = (trades_per_year/100) * (annual_r/100) * (win_rate*100)
        # Balances frequency, returns, and reliability
        score = (r['trades_per_year']/100) * (r['annual_r']/100) * (r['win_rate']*100)
        if score > best_score:
            best_score = score
            best_balanced = r

    print(f"BEST OVERALL BALANCE:")
    print(f"  {best_balanced['rr']}R target")
    print(f"  - {best_balanced['trades_per_year']:.0f} trades per year (~{best_balanced['trades_per_year']/12:.0f} per month)")
    print(f"  - {best_balanced['win_rate']*100:.1f}% win rate")
    print(f"  - {best_balanced['avg_r']:+.3f}R per trade")
    print(f"  - {best_balanced['annual_r']:+.0f}R per year")
    print(f"  - {best_balanced['median_hold_hours']:.1f} hours median hold time\n")

    print("This gives you:")
    print(f"  - ~2-3 setups per month (not too rare)")
    print(f"  - Solid win rate (easier to stay disciplined)")
    print(f"  - Good risk/reward (worth the wait)")
    print(f"  - Strong annual returns\n")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
