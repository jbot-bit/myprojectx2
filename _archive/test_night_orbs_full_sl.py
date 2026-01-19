"""Test night ORBs (2300, 0030) with FULL SL mode for big moves"""

import duckdb
from test_night_orb_extended_windows import simulate_night_orb_extended

con = duckdb.connect('gold.db', read_only=True)

dates_query = """
SELECT DISTINCT date_local
FROM daily_features_v2
WHERE instrument = 'MGC'
    AND date_local >= '2024-01-02'
    AND date_local <= '2026-01-10'
ORDER BY date_local
"""
dates = [row[0] for row in con.execute(dates_query).fetchall()]

print('\n' + '='*80)
print('NIGHT ORBS WITH FULL SL (BIG MOVES)')
print('='*80 + '\n')

for orb in ['2300', '0030']:
    print(f'\n{orb} ORB - FULL SL (scan until 09:00):')
    print('-' * 60)

    for rr in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]:
        trades = 0
        wins = 0
        total_r = 0.0

        for d in dates:
            result = simulate_night_orb_extended(con, d, orb, rr, 'full')
            if result.outcome in ('WIN', 'LOSS'):
                trades += 1
                total_r += result.r_multiple
                if result.outcome == 'WIN':
                    wins += 1

        wr = wins / trades if trades > 0 else 0.0
        avg_r = total_r / trades if trades > 0 else 0.0

        print(f'  RR={rr}: {trades} trades, {wr*100:5.1f}% WR, {avg_r:+.3f}R avg, {total_r:+5.0f}R total')

    # Find best
    best_rr = None
    best_avg_r = -999
    for rr in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]:
        trades = wins = 0
        total_r = 0.0
        for d in dates:
            result = simulate_night_orb_extended(con, d, orb, rr, 'full')
            if result.outcome in ('WIN', 'LOSS'):
                trades += 1
                total_r += result.r_multiple
                if result.outcome == 'WIN':
                    wins += 1
        avg_r = total_r / trades if trades > 0 else 0.0
        if avg_r > best_avg_r:
            best_avg_r = avg_r
            best_rr = rr
            best_wr = wins / trades if trades > 0 else 0.0
            best_total = total_r

    print(f'\n  ⭐ OPTIMAL: RR={best_rr}, {best_wr*100:.1f}% WR, {best_avg_r:+.3f}R avg, ~{best_total/2:+.0f}R/year')

con.close()

print('\n' + '='*80)
print('DONE!')
print('='*80)
