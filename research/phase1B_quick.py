#!/usr/bin/env python3
"""
PHASE 1B - CONDITION DISCOVERY (OPTIMIZED)

Tests only the TOP baseline families from Phase 1A with focused conditions.
Faster, focused approach.
"""

import pandas as pd
import sys

# Load Phase 1A results
phase1a = pd.read_csv('research/phase1A_baseline_families.csv')

# Focus on profitable families (avg_r > 0) OR families with >200 trades
promising = phase1a[
    (phase1a['avg_r'] > 0) |
    (phase1a['trades'] > 200)
].sort_values('avg_r', ascending=False)

print("=" * 80)
print("PHASE 1B - FOCUSED CONDITION DISCOVERY")
print("=" * 80)
print()
print(f"Total families in Phase 1A: {len(phase1a)}")
print(f"Promising families to test: {len(promising)}")
print()

# Break down by ORB time
for orb_time in ['0900', '1000', '1100', '1800', '2300', '0030']:
    orb_families = promising[promising['orb_time'] == orb_time]

    if len(orb_families) == 0:
        print(f"{orb_time} ORB: No promising families (skip)")
        continue

    print(f"{orb_time} ORB: {len(orb_families)} families to test")
    print(f"  Best: {orb_families.iloc[0]['family_id']} ({orb_families.iloc[0]['avg_r']:+.3f}R)")

print()
print("=" * 80)
print("RECOMMENDATION")
print("=" * 80)
print()
print("Instead of testing ALL 144 families, focus on these:")
print()

# Top 30 by avg_r
top30 = phase1a.head(30)

print("TOP 30 FAMILIES BY AVG_R:")
for i, row in enumerate(top30.itertuples(), 1):
    print(f"{i:2d}. {row.family_id:35s} {row.avg_r:+.3f}R ({row.trades} trades)")

print()
print("Create separate scripts for each ORB time:")
print("  - research/phase1B_1000.py (10am - HIGHEST PRIORITY)")
print("  - research/phase1B_1100.py (11am - 2nd priority)")
print("  - research/phase1B_1800.py (6pm - 3rd priority)")
print("  - research/phase1B_0900.py (9am - marginal, low priority)")
print()
print("Skip 2300 and 0030 entirely (no promising baselines)")
print()
