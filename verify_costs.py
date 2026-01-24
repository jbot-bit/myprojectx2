"""
Quick cost impact verification after TICK_VALUE correction.

Shows 10:00 ORB results with corrected transaction costs:
- Commission: $2.00
- Slippage: 0.5 ticks x $1.00/tick = $0.50
- Total: $2.50 per trade
"""

import duckdb

con = duckdb.connect('data/db/gold.db', read_only=True)

print('=' * 100)
print('CORRECTED COST IMPACT ANALYSIS')
print('=' * 100)
print()
print('Transaction Costs (CORRECTED):')
print('  Commission: $2.00 round-trip')
print('  Slippage: 0.5 ticks x $1.00/tick = $0.50 total')
print('  Total Cost: $2.50 per trade')
print()
print('TICK_VALUE correction: $0.10 (WRONG) -> $1.00 (CORRECT)')
print()
print('=' * 100)

# Query 10:00 ORB results
result = con.execute("""
    SELECT
        date_local,
        orb_1000_size,
        orb_1000_risk_ticks,
        orb_1000_outcome,
        orb_1000_r_multiple,
        orb_1000_outcome_net,
        orb_1000_r_multiple_net
    FROM daily_features_v2
    WHERE date_local BETWEEN '2025-01-06' AND '2025-01-12'
      AND instrument = 'MGC'
      AND orb_1000_outcome IS NOT NULL
    ORDER BY date_local
""").fetchall()

print()
print('10:00 ORB Results (Sample Period: 2025-01-06 to 2025-01-12):')
print()
print('Date       | Gross    | Gross R | Net      | Net R   | Risk    | Cost    | Impact')
print('-' * 100)

gross_wins = 0
net_wins = 0
total_gross_r = 0
total_net_r = 0

for row in result:
    date, orb_size, risk_ticks, outcome, r_gross, outcome_net, r_net = row

    cost_in_r = r_gross - r_net if (r_gross is not None and r_net is not None) else 0

    if outcome == 'WIN':
        gross_wins += 1
    if outcome_net == 'WIN':
        net_wins += 1

    total_gross_r += r_gross if r_gross else 0
    total_net_r += r_net if r_net else 0

    # Determine impact
    if outcome == 'WIN' and outcome_net == 'LOSS':
        impact = 'WIN -> LOSS'
    elif outcome == 'LOSS' and r_net < r_gross:
        impact = 'Loss worse'
    else:
        impact = 'Still WIN' if outcome_net == 'WIN' else ''

    print(f'{date} | {outcome:8s} | {r_gross:+7.3f} | {outcome_net:8s} | {r_net:+7.3f} | {risk_ticks:5.1f}t | {cost_in_r:6.3f}R | {impact}')

print('-' * 100)

num_trades = len(result)
print()
print('Summary:')
print(f'  Total trades: {num_trades}')
print(f'  Gross: {gross_wins} WIN, {num_trades - gross_wins} LOSS ({gross_wins/num_trades*100:.1f}% WR)')
print(f'  Net:   {net_wins} WIN, {num_trades - net_wins} LOSS ({net_wins/num_trades*100:.1f}% WR)')
print(f'  Average Gross R: {total_gross_r/num_trades:+.3f}')
print(f'  Average Net R:   {total_net_r/num_trades:+.3f}')
print()
print(f'Impact: {gross_wins - net_wins} gross winners became net losers')
print()

# Show breakeven analysis
print('=' * 100)
print('BREAKEVEN ANALYSIS')
print('=' * 100)
print()
print('For 1:1 RR (gross +1.0R):')
print()
print('Risk Size | Risk $  | Cost $  | Cost R  | Net R   | Result')
print('-' * 60)

for risk_ticks in [2.5, 5, 10, 15, 20, 25, 30]:
    risk_dollars = risk_ticks * 1.00
    cost_dollars = 2.50
    cost_in_r = cost_dollars / risk_dollars
    net_r = 1.0 - cost_in_r

    result_str = 'LOSS' if net_r < 0 else 'BREAKEVEN' if abs(net_r) < 0.01 else 'WIN'

    print(f'{risk_ticks:5.1f}t   | ${risk_dollars:5.2f} | ${cost_dollars:5.2f} | {cost_in_r:6.3f}R | {net_r:+6.3f}R | {result_str}')

print()
print('Breakeven point for 1:1 RR: ~2.5 ticks risk (with $2.50 cost)')
print('Viable trading threshold: 10+ ticks risk for meaningful edge')
print()

con.close()
