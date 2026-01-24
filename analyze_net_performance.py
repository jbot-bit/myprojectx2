"""
Analyze net performance (after transaction costs) across all ORBs.

Shows impact of $2.50 transaction costs on each ORB time.
"""

import duckdb

con = duckdb.connect('data/db/gold.db', read_only=True)

print('=' * 100)
print('NET PERFORMANCE ANALYSIS - ALL ORBs')
print('=' * 100)
print()
print('Transaction Costs: $2.50 per trade ($2.00 commission + $0.50 slippage)')
print('Dataset: 2024-01-01 to 2026-01-24 (755 days total)')
print()
print('=' * 100)

orb_times = ['0900', '1000', '1100', '1800', '2300', '0030']

for orb_time in orb_times:
    print()
    print(f'=== ORB {orb_time} ===')
    print()

    # Query gross and net performance
    result = con.execute(f"""
        SELECT
            COUNT(*) as trades,
            SUM(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1 ELSE 0 END) as gross_wins,
            SUM(CASE WHEN orb_{orb_time}_outcome_net = 'WIN' THEN 1 ELSE 0 END) as net_wins,
            AVG(orb_{orb_time}_r_multiple) as avg_gross_r,
            AVG(orb_{orb_time}_r_multiple_net) as avg_net_r,
            AVG(orb_{orb_time}_risk_ticks) as avg_risk_ticks
        FROM daily_features_v2
        WHERE instrument = 'MGC'
          AND orb_{orb_time}_outcome IS NOT NULL
    """).fetchone()

    if result and result[0] > 0:
        trades, gross_wins, net_wins, avg_gross_r, avg_net_r, avg_risk_ticks = result

        gross_wr = gross_wins / trades * 100
        net_wr = net_wins / trades * 100

        # Calculate flipped trades
        flipped = gross_wins - net_wins

        print(f'Trades: {trades}')
        print()
        print('GROSS Performance (before costs):')
        print(f'  Win Rate: {gross_wr:.1f}% ({gross_wins}/{trades})')
        print(f'  Avg R: {avg_gross_r:+.3f}')
        print()
        print('NET Performance (after costs):')
        print(f'  Win Rate: {net_wr:.1f}% ({net_wins}/{trades})')
        print(f'  Avg R: {avg_net_r:+.3f}')
        print()
        print('Impact:')
        print(f'  Cost impact: {avg_gross_r - avg_net_r:.3f}R per trade')
        print(f'  WIN -> LOSS flips: {flipped} trades ({flipped/trades*100:.1f}%)')
        print(f'  Avg risk: {avg_risk_ticks:.1f} ticks')
        print()

        # Profitability check
        if avg_net_r > 0:
            print(f'  Status: PROFITABLE (net +{avg_net_r:.3f}R per trade)')
        elif avg_net_r > -0.1:
            print(f'  Status: BREAKEVEN (net {avg_net_r:+.3f}R per trade)')
        else:
            print(f'  Status: UNPROFITABLE (net {avg_net_r:+.3f}R per trade)')
    else:
        print('No trades found')

print()
print('=' * 100)
print()

# Overall summary
print('=== OVERALL SUMMARY (All 6 ORBs Combined) ===')
print()

total_result = con.execute("""
    SELECT
        SUM(CASE WHEN orb_0900_outcome IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN orb_1000_outcome IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN orb_1100_outcome IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN orb_1800_outcome IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN orb_2300_outcome IS NOT NULL THEN 1 ELSE 0 END +
            CASE WHEN orb_0030_outcome IS NOT NULL THEN 1 ELSE 0 END) as total_trades
    FROM daily_features_v2
    WHERE instrument = 'MGC'
""").fetchone()[0]

print(f'Total ORB trades across all 6 ORBs: {total_result}')
print()
print('Note: Each ORB analyzed independently above.')
print('      Profitable ORBs can be prioritized in live trading.')

con.close()
