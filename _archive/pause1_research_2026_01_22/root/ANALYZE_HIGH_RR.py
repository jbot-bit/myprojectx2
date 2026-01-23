"""
Analyze ALL_ORBS_EXTENDED_WINDOWS.csv to find highest RR setup
that's NOT in validated_setups.
"""

import pandas as pd
import duckdb

# Load research data
df = pd.read_csv("unknown/ALL_ORBS_EXTENDED_WINDOWS.csv")

# Load validated setups
con = duckdb.connect("data/db/gold.db", read_only=True)
validated = con.execute("""
    SELECT orb_time, rr, sl_mode
    FROM validated_setups
    WHERE instrument = 'MGC'
""").fetchall()
con.close()

validated_set = {(orb, rr, sl.upper()) for orb, rr, sl in validated}

print("\n" + "="*80)
print("FINDING HIGHEST RR SETUP NOT IN LIBRARY")
print("="*80)
print("\nCriteria:")
print("  - Frequent: >= 400 trades (54% of days)")
print("  - Profitable: avg_r > 0.15")
print("  - NOT already in validated_setups\n")

# Filter candidates
df['orb_padded'] = df['orb'].astype(str).str.zfill(4)
df['sl_upper'] = df['sl_mode'].str.upper()

candidates = []

for _, row in df.iterrows():
    orb_key = (row['orb_padded'], row['rr'], row['sl_upper'])

    # Skip if in library
    if orb_key in validated_set:
        continue

    # Apply filters
    if row['trades'] < 400:
        continue
    if row['avg_r'] <= 0.15:
        continue

    candidates.append(row)

if not candidates:
    print("No new setups found!")
    exit(1)

# Sort by RR descending, then avg_r
candidates_df = pd.DataFrame(candidates)
candidates_df = candidates_df.sort_values(['rr', 'avg_r'], ascending=[False, False])

print("="*80)
print("TOP 10 HIGHEST RR SETUPS (not in library):")
print("="*80)
print(f"{'Rank':<5} {'ORB':<6} {'RR':<6} {'SL':<6} {'Trades':<8} {'WR%':<7} {'Avg R':<9} {'Ann R':<9}")
print("-"*80)

for i, (_, row) in enumerate(candidates_df.head(10).iterrows(), 1):
    print(f"{i:<5} {row['orb_padded']:<6} {row['rr']:<6.1f} {row['sl_upper']:<6} "
          f"{row['trades']:<8.0f} {row['win_rate']*100:<7.1f} {row['avg_r']:<+9.3f} {row['total_r']/2:<+9.0f}")

print("\n" + "="*80)
print("BEST CANDIDATE (Highest RR):")
print("="*80)

best = candidates_df.iloc[0]
print(f"\nORB: {best['orb_padded']}")
print(f"RR: {best['rr']}")
print(f"SL Mode: {best['sl_upper']}")
print(f"Trades: {best['trades']:.0f} ({best['trades']/740*100:.1f}% of days)")
print(f"Win Rate: {best['win_rate']*100:.1f}%")
print(f"Avg R: {best['avg_r']:+.3f}")
print(f"Total: {best['total_r']:+.0f}R over 2 years")
print(f"Annual: ~{best['total_r']/2:+.0f}R/year")

print("\n" + "="*80)
print("NEXT STEP: VALIDATE WITH CANONICAL DATA")
print("="*80)
print(f"\nRun proof to validate from bars_1m:\n")
print(f"  python PROOF_{best['orb_padded']}_RR{best['rr']:.1f}.py")
print("\n" + "="*80 + "\n")
