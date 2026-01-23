"""
BIG MOVE CONDITIONS ANALYSIS
=============================

CRITICAL QUESTION: How do we know BEFORE entering which setups will hit 10R vs stop out?

This analyzes:
1. Pre-trade conditions (ATR, prior session behavior, gaps, etc.)
2. ORB characteristics (size, speed of formation, etc.)
3. Market structure (where ORB sits relative to prior levels)
4. Entry quality (how clean the break is)

GOAL: Find filters that identify high-probability 10R moves BEFORE they happen
"""

import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time as dt_time
from ASIA_ORB_CLEAN import get_orb_from_bars, detect_orb_break

def analyze_big_move_conditions(orb_hour, orb_minute, duration, sl_mode, rr):
    """
    Compare winning trades vs losing trades to find distinguishing conditions
    """

    con = duckdb.connect("gold.db", read_only=True)

    # Get all dates with daily features (for context)
    dates_query = """
    SELECT date_local,
           asia_high, asia_low, asia_range,
           london_high, london_low, london_range,
           pre_asia_high, pre_asia_low, pre_asia_range,
           atr_20
    FROM daily_features_v2
    WHERE instrument = 'MGC'
        AND date_local >= '2024-01-02'
        AND date_local <= '2026-01-10'
    ORDER BY date_local
    """
    features_df = pd.DataFrame(con.execute(dates_query).fetchall(),
                               columns=['date', 'asia_high', 'asia_low', 'asia_range',
                                      'london_high', 'london_low', 'london_range',
                                      'pre_asia_high', 'pre_asia_low', 'pre_asia_range',
                                      'atr_20'])

    # Simulate all trades and collect detailed info
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
        orb_mid = (orb_high + orb_low) / 2

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
            continue  # Only analyze QUARTER for now

        r_size = abs(orb_edge - stop)
        target = orb_edge + (rr * r_size) if break_dir == 'UP' else orb_edge - (rr * r_size)

        # Get bars after entry to simulate outcome
        bars_query = f"""
        SELECT ts_utc, high, low, close
        FROM bars_1m
        WHERE symbol = 'MGC'
            AND ts_utc > '{entry_ts}'::TIMESTAMPTZ
            AND ts_utc < '{scan_end_ts}'::TIMESTAMPTZ
        ORDER BY ts_utc ASC
        """
        bars = con.execute(bars_query).fetchall()

        # Simulate outcome
        outcome = None
        exit_ts = None
        bars_to_exit = 0
        max_favorable = 0  # Max R in favorable direction

        if isinstance(entry_ts, str):
            entry_dt = datetime.fromisoformat(entry_ts.replace('+00:00', '').replace(' ', 'T'))
        else:
            entry_dt = entry_ts
        if hasattr(entry_dt, 'tzinfo') and entry_dt.tzinfo:
            entry_dt = entry_dt.replace(tzinfo=None)

        for ts_utc, h, l, c in bars:
            bars_to_exit += 1
            h, l = float(h), float(l)

            # Track max favorable excursion
            if break_dir == 'UP':
                favorable = (h - orb_edge) / r_size
                max_favorable = max(max_favorable, favorable)

                if l <= stop:
                    outcome = 'LOSS'
                    exit_ts = ts_utc
                    break
                if h >= target:
                    outcome = 'WIN'
                    exit_ts = ts_utc
                    break
            else:
                favorable = (orb_edge - l) / r_size
                max_favorable = max(max_favorable, favorable)

                if h >= stop:
                    outcome = 'LOSS'
                    exit_ts = ts_utc
                    break
                if l <= target:
                    outcome = 'WIN'
                    exit_ts = ts_utc
                    break

        if not outcome:
            continue

        # Calculate time to entry (minutes after ORB completion)
        orb_end_str = orb['end_ts']
        if isinstance(orb_end_str, str):
            orb_end_dt = datetime.fromisoformat(orb_end_str.replace('+00:00', '').replace(' ', 'T'))
        else:
            orb_end_dt = orb_end_str
        if hasattr(orb_end_dt, 'tzinfo') and orb_end_dt.tzinfo:
            orb_end_dt = orb_end_dt.replace(tzinfo=None)
        entry_delay_minutes = (entry_dt - orb_end_dt).total_seconds() / 60

        # Get prior day's range for context
        prior_date = d - timedelta(days=1)
        prior_row = features_df[features_df['date'] == prior_date]
        prior_range = prior_row['asia_range'].values[0] if len(prior_row) > 0 else None

        # Collect conditions
        trades.append({
            'date': d,
            'outcome': outcome,
            'direction': break_dir,

            # ORB characteristics
            'orb_size': orb_size,
            'orb_size_vs_atr': orb_size / row['atr_20'] if row['atr_20'] > 0 else None,

            # Entry characteristics
            'entry_delay_minutes': entry_delay_minutes,
            'entry_distance_from_mid': abs(entry_price - orb_mid),

            # Context
            'atr_20': row['atr_20'],
            'pre_asia_range': row['pre_asia_range'],
            'asia_range': row['asia_range'],
            'london_range': row['london_range'],
            'prior_asia_range': prior_range,

            # ORB position relative to prior session
            'orb_high_vs_asia_high': orb_high - row['asia_high'] if orb_hour >= 9 else None,
            'orb_low_vs_asia_low': orb_low - row['asia_low'] if orb_hour >= 9 else None,

            # Execution
            'bars_to_exit': bars_to_exit,
            'max_favorable_r': max_favorable
        })

    con.close()

    if not trades:
        return None

    df = pd.DataFrame(trades)

    # Separate winners and losers
    winners = df[df['outcome'] == 'WIN']
    losers = df[df['outcome'] == 'LOSS']

    print(f"\nTotal trades: {len(df)}")
    print(f"Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")

    # Compare conditions
    comparisons = []

    # Numeric columns to compare
    numeric_cols = ['orb_size', 'orb_size_vs_atr', 'entry_delay_minutes',
                   'entry_distance_from_mid', 'atr_20', 'pre_asia_range',
                   'asia_range', 'london_range', 'bars_to_exit', 'max_favorable_r']

    for col in numeric_cols:
        if col not in df.columns:
            continue

        winner_values = winners[col].dropna()
        loser_values = losers[col].dropna()

        if len(winner_values) == 0 or len(loser_values) == 0:
            continue

        comparisons.append({
            'condition': col,
            'winner_median': winner_values.median(),
            'loser_median': loser_values.median(),
            'winner_mean': winner_values.mean(),
            'loser_mean': loser_values.mean(),
            'difference': winner_values.median() - loser_values.median(),
            'pct_difference': ((winner_values.median() - loser_values.median()) / loser_values.median() * 100) if loser_values.median() != 0 else 0
        })

    comparison_df = pd.DataFrame(comparisons)
    comparison_df['abs_pct_diff'] = comparison_df['pct_difference'].abs()
    comparison_df = comparison_df.sort_values('abs_pct_diff', ascending=False)

    # Directional analysis
    print(f"\n" + "="*80)
    print("DIRECTIONAL ANALYSIS")
    print("="*80)

    up_winners = winners[winners['direction'] == 'UP']
    up_losers = losers[losers['direction'] == 'UP']
    down_winners = winners[winners['direction'] == 'DOWN']
    down_losers = losers[losers['direction'] == 'DOWN']

    print(f"\nUP trades:")
    print(f"  Winners: {len(up_winners)}/{len(up_winners)+len(up_losers)} ({len(up_winners)/(len(up_winners)+len(up_losers))*100:.1f}%)")

    print(f"\nDOWN trades:")
    print(f"  Winners: {len(down_winners)}/{len(down_winners)+len(down_losers)} ({len(down_winners)/(len(down_winners)+len(down_losers))*100:.1f}%)")

    return {
        'all_trades': df,
        'winners': winners,
        'losers': losers,
        'comparisons': comparison_df,
        'up_winners': up_winners,
        'down_winners': down_winners
    }


def main():
    print("\n" + "="*80)
    print("BIG MOVE CONDITIONS ANALYSIS")
    print("="*80)
    print("\nAnalyzing: 11:00 ORB, 5min, QUARTER, 10R")
    print("Question: What conditions predict 10R winners vs stop outs?\n")

    result = analyze_big_move_conditions(11, 0, 5, "QUARTER", 10.0)

    if not result:
        print("No data found!")
        return

    print("\n" + "="*80)
    print("KEY DIFFERENCES: Winners vs Losers")
    print("="*80)
    print("\nConditions ranked by % difference:\n")

    comp = result['comparisons']
    print(f"{'Condition':<30} {'Winner Med':<12} {'Loser Med':<12} {'% Diff':<10}")
    print("-"*80)

    for _, row in comp.head(15).iterrows():
        print(f"{row['condition']:<30} {row['winner_median']:>11.3f} {row['loser_median']:>11.3f} {row['pct_difference']:>9.1f}%")

    # Statistical filters
    print("\n" + "="*80)
    print("PROPOSED FILTERS (for discretionary trading)")
    print("="*80)

    df = result['all_trades']
    winners = result['winners']

    # Find optimal thresholds
    filters = []

    # ORB size filter
    if 'orb_size_vs_atr' in df.columns:
        winner_orb_sizes = winners['orb_size_vs_atr'].dropna()
        if len(winner_orb_sizes) > 0:
            p25 = winner_orb_sizes.quantile(0.25)
            p75 = winner_orb_sizes.quantile(0.75)

            # Test threshold
            optimal = None
            best_improvement = 0

            for threshold in [p25, winner_orb_sizes.median(), p75]:
                filtered = df[df['orb_size_vs_atr'] >= threshold]
                if len(filtered) > 50:
                    wr = (filtered['outcome'] == 'WIN').sum() / len(filtered)
                    base_wr = len(winners) / len(df)
                    improvement = (wr - base_wr) / base_wr * 100

                    if improvement > best_improvement:
                        best_improvement = improvement
                        optimal = threshold

            if optimal:
                filtered = df[df['orb_size_vs_atr'] >= optimal]
                wr = (filtered['outcome'] == 'WIN').sum() / len(filtered)
                filters.append({
                    'filter': f"ORB size >= {optimal:.2f} × ATR(20)",
                    'trades': len(filtered),
                    'win_rate': wr,
                    'improvement': best_improvement
                })

    # Entry delay filter
    if 'entry_delay_minutes' in df.columns:
        winner_delays = winners['entry_delay_minutes'].dropna()
        loser_delays = result['losers']['entry_delay_minutes'].dropna()

        if len(winner_delays) > 0:
            # Test if quick entries are better
            threshold = 5  # 5 minutes
            quick_entries = df[df['entry_delay_minutes'] <= threshold]
            if len(quick_entries) > 50:
                wr = (quick_entries['outcome'] == 'WIN').sum() / len(quick_entries)
                base_wr = len(winners) / len(df)
                improvement = (wr - base_wr) / base_wr * 100

                if abs(improvement) > 5:
                    filters.append({
                        'filter': f"Entry within {threshold} minutes of ORB completion",
                        'trades': len(quick_entries),
                        'win_rate': wr,
                        'improvement': improvement
                    })

    # Prior range filter
    if 'prior_asia_range' in df.columns:
        df_with_prior = df.dropna(subset=['prior_asia_range'])
        if len(df_with_prior) > 100:
            winner_prior = winners['prior_asia_range'].dropna()
            threshold = winner_prior.median()

            big_prior = df_with_prior[df_with_prior['prior_asia_range'] >= threshold]
            if len(big_prior) > 50:
                wr = (big_prior['outcome'] == 'WIN').sum() / len(big_prior)
                base_wr = len(winners) / len(df)
                improvement = (wr - base_wr) / base_wr * 100

                if abs(improvement) > 5:
                    filters.append({
                        'filter': f"Prior day Asia range >= {threshold:.1f} pts",
                        'trades': len(big_prior),
                        'win_rate': wr,
                        'improvement': improvement
                    })

    # Direction filter
    up_wr = len(result['up_winners']) / (len(result['up_winners']) + len(df[df['direction']=='UP']) - len(result['up_winners']))
    down_wr = len(result['down_winners']) / (len(result['down_winners']) + len(df[df['direction']=='DOWN']) - len(result['down_winners']))
    base_wr = len(winners) / len(df)

    if up_wr > base_wr * 1.1:  # 10% better
        up_trades = df[df['direction'] == 'UP']
        filters.append({
            'filter': "Trade UP breaks only",
            'trades': len(up_trades),
            'win_rate': up_wr,
            'improvement': (up_wr - base_wr) / base_wr * 100
        })

    # Print filters
    if filters:
        print("\nRECOMMENDED FILTERS:\n")
        for i, f in enumerate(sorted(filters, key=lambda x: x['improvement'], reverse=True), 1):
            print(f"{i}. {f['filter']}")
            print(f"   -> {f['trades']} trades, {f['win_rate']*100:.1f}% WR ({f['improvement']:+.1f}% improvement)\n")

    # Combined filter test
    print("="*80)
    print("COMBINED FILTER TEST")
    print("="*80)

    # Apply all filters together
    filtered = df.copy()
    applied_filters = []

    for f in filters:
        if "ORB size" in f['filter'] and 'orb_size_vs_atr' in filtered.columns:
            threshold = float(f['filter'].split('>=')[1].split('×')[0].strip())
            filtered = filtered[filtered['orb_size_vs_atr'] >= threshold]
            applied_filters.append(f['filter'])

        if "UP breaks only" in f['filter']:
            filtered = filtered[filtered['direction'] == 'UP']
            applied_filters.append(f['filter'])

        if "Entry within" in f['filter'] and 'entry_delay_minutes' in filtered.columns:
            threshold = int(f['filter'].split('within')[1].split('minutes')[0].strip())
            filtered = filtered[filtered['entry_delay_minutes'] <= threshold]
            applied_filters.append(f['filter'])

    if len(applied_filters) > 0 and len(filtered) > 20:
        combined_wr = (filtered['outcome'] == 'WIN').sum() / len(filtered)
        print(f"\nApplied {len(applied_filters)} filters:")
        for af in applied_filters:
            print(f"  - {af}")

        print(f"\nResults:")
        print(f"  Trades: {len(filtered)} (from {len(df)})")
        print(f"  Win rate: {combined_wr*100:.1f}% (base: {base_wr*100:.1f}%)")
        print(f"  Improvement: {(combined_wr - base_wr)/base_wr*100:+.1f}%")
        print(f"  Expected R/trade: {combined_wr * 10.0 + (1-combined_wr) * -1.0:+.2f}R")

    # Save detailed trade data
    print(f"\n{'='*80}")
    print("Saving detailed trade data to BIG_MOVE_CONDITIONS.csv...")
    result['all_trades'].to_csv("BIG_MOVE_CONDITIONS.csv", index=False)
    print("Saved!")

    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print("KEY TAKEAWAY:")
    print("Use the conditions above to FILTER which 11:00 ORB setups to take.")
    print("Don't take every break - only take the ones with favorable conditions.\n")
    print("Check BIG_MOVE_CONDITIONS.csv for all trade details.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
