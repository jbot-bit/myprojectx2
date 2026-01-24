"""
Analyze Tier 1 ORBs for filter opportunities.

Focus: 1800, 1100, 2300, 0030 (survive worst-case 2.0t slippage)
Goal: Find filters that improve net edge while maintaining frequency
Balance: Don't over-filter (want 150+ trades/year per ORB)
"""

import duckdb
import pandas as pd

con = duckdb.connect('data/db/gold.db', read_only=True)

TIER1_ORBS = ['1800', '1100', '2300', '0030']

print('=' * 100)
print('TIER 1 ORB ANALYSIS - FILTER OPPORTUNITIES')
print('=' * 100)
print()
print('Focus: 4 robust ORBs that survive worst-case slippage (2.0 ticks)')
print('Goal: Find filters to improve edge while maintaining frequency (150+ trades/year)')
print()
print('=' * 100)

for orb_time in TIER1_ORBS:
    print()
    print(f'=== ORB {orb_time} ===')
    print()

    # Get all trades with detailed features
    df = con.execute(f"""
        SELECT
            date_local,
            orb_{orb_time}_size,
            orb_{orb_time}_risk_ticks,
            orb_{orb_time}_outcome,
            orb_{orb_time}_r_multiple,
            orb_{orb_time}_outcome_net,
            orb_{orb_time}_r_multiple_net,
            orb_{orb_time}_break_dir,
            -- Pre-ORB context
            pre_asia_range,
            pre_london_range,
            pre_ny_range,
            -- Session ranges
            asia_range,
            london_range,
            ny_range,
            -- Volatility
            atr_20
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND orb_{orb_time}_outcome IS NOT NULL
    """).fetchdf()

    if len(df) == 0:
        print('No trades found')
        continue

    # Separate winners and losers (NET)
    winners = df[df['orb_{}_outcome_net'.format(orb_time)] == 'WIN']
    losers = df[df['orb_{}_outcome_net'.format(orb_time)] == 'LOSS']

    total_trades = len(df)
    win_rate = len(winners) / total_trades * 100
    avg_net_r = df[f'orb_{orb_time}_r_multiple_net'].mean()

    print(f'Baseline Performance (no filters):')
    print(f'  Trades: {total_trades} ({total_trades * 2:.0f}/year estimated)')
    print(f'  Win Rate: {win_rate:.1f}%')
    print(f'  Avg Net R: {avg_net_r:+.3f}')
    print()

    # Analyze potential filters
    print('Filter Opportunities:')
    print()

    # 1. ORB Size Analysis
    print('1. ORB SIZE RANGES')
    print('   Winners vs Losers comparison:')

    if len(winners) > 0 and len(losers) > 0:
        win_orb_size = winners[f'orb_{orb_time}_size'].mean()
        loss_orb_size = losers[f'orb_{orb_time}_size'].mean()

        print(f'   Winners avg ORB size: {win_orb_size:.3f} points ({win_orb_size*10:.1f} ticks)')
        print(f'   Losers avg ORB size: {loss_orb_size:.3f} points ({loss_orb_size*10:.1f} ticks)')

        if win_orb_size > loss_orb_size * 1.1:
            print(f'   -> OPPORTUNITY: Winners have larger ORBs (+{(win_orb_size/loss_orb_size - 1)*100:.1f}%)')
            print(f'      Consider filter: ORB size > {loss_orb_size:.3f}')
        elif loss_orb_size > win_orb_size * 1.1:
            print(f'   -> OPPORTUNITY: Winners have smaller ORBs (-{(1 - win_orb_size/loss_orb_size)*100:.1f}%)')
            print(f'      Consider filter: ORB size < {win_orb_size * 1.2:.3f}')
        else:
            print('   -> No clear pattern in ORB size')

    print()

    # 2. Pre-NY Range Analysis (overnight range)
    print('2. PRE-NY RANGE (overnight range before ORB)')

    if 'pre_ny_range' in df.columns and len(winners) > 0 and len(losers) > 0:
        win_pre_ny = winners['pre_ny_range'].dropna().mean()
        loss_pre_ny = losers['pre_ny_range'].dropna().mean()

        if not pd.isna(win_pre_ny) and not pd.isna(loss_pre_ny):
            print(f'   Winners avg pre-NY range: {win_pre_ny:.3f} points')
            print(f'   Losers avg pre-NY range: {loss_pre_ny:.3f} points')

            if abs(win_pre_ny - loss_pre_ny) > 0.1:
                print(f'   -> OPPORTUNITY: Pre-NY range pattern differs')
                print(f'      Test filters around: {win_pre_ny:.3f} points')
            else:
                print('   -> No clear pattern in pre-NY range')
        else:
            print('   -> Insufficient data')
    else:
        print('   -> Feature not available')

    print()

    # 3. Break Direction Analysis
    print('3. BREAK DIRECTION (UP vs DOWN)')

    if f'orb_{orb_time}_break_dir' in df.columns:
        up_trades = df[df[f'orb_{orb_time}_break_dir'] == 'UP']
        down_trades = df[df[f'orb_{orb_time}_break_dir'] == 'DOWN']

        if len(up_trades) > 0 and len(down_trades) > 0:
            up_net_r = up_trades[f'orb_{orb_time}_r_multiple_net'].mean()
            down_net_r = down_trades[f'orb_{orb_time}_r_multiple_net'].mean()
            up_wr = (up_trades[f'orb_{orb_time}_outcome_net'] == 'WIN').sum() / len(up_trades) * 100
            down_wr = (down_trades[f'orb_{orb_time}_outcome_net'] == 'WIN').sum() / len(down_trades) * 100

            print(f'   UP breaks: {len(up_trades)} trades, {up_wr:.1f}% WR, {up_net_r:+.3f}R avg')
            print(f'   DOWN breaks: {len(down_trades)} trades, {down_wr:.1f}% WR, {down_net_r:+.3f}R avg')

            if up_net_r > down_net_r + 0.05:
                print(f'   -> OPPORTUNITY: UP breaks perform better (+{up_net_r - down_net_r:.3f}R)')
                print(f'      Consider: Trade only UP breaks (loses {len(down_trades)} trades)')
            elif down_net_r > up_net_r + 0.05:
                print(f'   -> OPPORTUNITY: DOWN breaks perform better (+{down_net_r - up_net_r:.3f}R)')
                print(f'      Consider: Trade only DOWN breaks (loses {len(up_trades)} trades)')
            else:
                print('   -> Both directions similar, keep both')

    print()

    # 4. Volatility (ATR) Analysis
    print('4. VOLATILITY CONTEXT (ATR_20)')

    if 'atr_20' in df.columns and len(winners) > 0 and len(losers) > 0:
        win_atr = winners['atr_20'].dropna().mean()
        loss_atr = losers['atr_20'].dropna().mean()

        if not pd.isna(win_atr) and not pd.isna(loss_atr):
            print(f'   Winners avg ATR: {win_atr:.3f}')
            print(f'   Losers avg ATR: {loss_atr:.3f}')

            if win_atr > loss_atr * 1.1:
                print(f'   -> OPPORTUNITY: Winners have higher volatility (+{(win_atr/loss_atr - 1)*100:.1f}%)')
                print(f'      Consider: ATR > {loss_atr:.3f}')
            elif loss_atr > win_atr * 1.1:
                print(f'   -> OPPORTUNITY: Winners have lower volatility')
                print(f'      Consider: ATR < {win_atr * 1.2:.3f}')
            else:
                print('   -> No clear ATR pattern')
        else:
            print('   -> Insufficient data')

    print()

    # 5. Session Range Analysis (for context)
    print('5. SESSION CONTEXT (preceding ranges)')

    # Asia range (for 1800 ORB)
    if orb_time == '1800' and 'asia_range' in df.columns:
        if len(winners) > 0 and len(losers) > 0:
            win_asia = winners['asia_range'].dropna().mean()
            loss_asia = losers['asia_range'].dropna().mean()

            if not pd.isna(win_asia) and not pd.isna(loss_asia):
                print(f'   Asia range (before 1800 ORB):')
                print(f'   Winners: {win_asia:.3f} | Losers: {loss_asia:.3f}')

                if abs(win_asia - loss_asia) / max(win_asia, loss_asia) > 0.15:
                    print(f'   -> OPPORTUNITY: Asia range matters for 1800 ORB')

    # London range (for 2300 ORB)
    if orb_time == '2300' and 'london_range' in df.columns:
        if len(winners) > 0 and len(losers) > 0:
            win_london = winners['london_range'].dropna().mean()
            loss_london = losers['london_range'].dropna().mean()

            if not pd.isna(win_london) and not pd.isna(loss_london):
                print(f'   London range (before 2300 ORB):')
                print(f'   Winners: {win_london:.3f} | Losers: {loss_london:.3f}')

                if abs(win_london - loss_london) / max(win_london, loss_london) > 0.15:
                    print(f'   -> OPPORTUNITY: London range matters for 2300 ORB')

    print()
    print('-' * 100)

print()
print('=' * 100)
print()
print('SUMMARY & NEXT STEPS')
print()
print('For each OPPORTUNITY identified above:')
print('  1. Create a test filter')
print('  2. Backtest on full dataset')
print('  3. Check impact on:')
print('     - Net R (must improve)')
print('     - Trade frequency (want 150+ trades/year minimum)')
print('     - Win rate (nice but not required)')
print()
print('Priority order for filter testing:')
print('  1. 1800 ORB (best performer)')
print('  2. 2300 ORB (high frequency)')
print('  3. 1100 ORB (large ORBs)')
print('  4. 0030 ORB (lowest cost impact)')
print()
print('Balance frequency + profitability:')
print('  - Don\'t accept <100 trades/year for any single ORB')
print('  - Prefer +0.070R with 200 trades over +0.120R with 50 trades')
print('  - Aim for consistent, frequent edge')
print()
print('=' * 100)

con.close()
