#!/usr/bin/env python3
"""
Phase 3 Proper Runner - Uses Real Candidate Backtest Engine

Re-runs Phase 3 with:
- Raw bars_1m (not precomputed outcomes)
- Candidate-specific RR, SL mode, scan windows, filters
- Correct midnight-crossing window handling

Outputs same files as original Phase 3 but with valid results.
"""

import sys
import duckdb
from pathlib import Path
from candidate_backtest_engine import backtest_candidate, calculate_metrics, parse_candidate_spec
import pandas as pd

OUTPUT_DIR = Path(__file__).parent
ROOT = Path(__file__).parent.parent
DB_PATH = str(ROOT / "data" / "db" / "gold.db")

print("=" * 80)
print("PHASE 3 PROPER - Testing 50 DRAFT Candidates")
print("=" * 80)
print()

# Load candidates
conn = duckdb.connect(DB_PATH, read_only=True)
candidates = conn.execute("""
    SELECT * FROM edge_candidates
    WHERE status = 'DRAFT'
    ORDER BY candidate_id
""").fetchdf()
conn.close()

print(f"Loaded {len(candidates)} DRAFT candidates")
print()

# Backtest each
results = []
for idx, cand_row in candidates.iterrows():
    cand_dict = cand_row.to_dict()
    spec = parse_candidate_spec(cand_dict)
    
    print(f"[{idx+1}/{len(candidates)}] Testing {spec.name}")
    print(f"  ORB: {spec.orb_time}, RR: {spec.rr}, SL: {spec.sl_mode}")
    print(f"  Window: {spec.scan_start_local} -> {spec.scan_end_local} (crosses midnight: {spec.crosses_midnight})")
    
    trades = backtest_candidate(cand_dict)
    metrics = calculate_metrics(trades)
    
    print(f"  Results: {metrics['total_trades']} trades, {metrics['win_rate']:.1f}% WR, {metrics['avg_r']:+.3f}R avg")
    print()
    
    results.append({
        'candidate_id': spec.candidate_id,
        'name': spec.name,
        'orb_time': spec.orb_time,
        'rr': spec.rr,
        'sl_mode': spec.sl_mode,
        **metrics
    })

# Save results
df = pd.DataFrame(results)
df.to_csv(OUTPUT_DIR / 'phase3_proper_results.csv', index=False)

print("=" * 80)
print(f"Saved results to phase3_proper_results.csv")
print(f"Total candidates: {len(results)}")
print(f"Avg trades per candidate: {df['total_trades'].mean():.0f}")
print()

# Check for 2300/0030 extended edges
ext_2300 = df[(df['orb_time'] == '2300') & (df['rr'] == 1.5)]
ext_0030 = df[(df['orb_time'] == '0030') & (df['rr'] == 3.0)]

if len(ext_2300) > 0:
    print("2300 Extended (RR=1.5) Results:")
    for _, row in ext_2300.iterrows():
        print(f"  {row['name']}: {row['total_trades']} trades, {row['win_rate']:.1f}% WR, {row['avg_r']:+.3f}R")

if len(ext_0030) > 0:
    print("0030 Extended (RR=3.0) Results:")
    for _, row in ext_0030.iterrows():
        print(f"  {row['name']}: {row['total_trades']} trades, {row['win_rate']:.1f}% WR, {row['avg_r']:+.3f}R")

print()
print("=" * 80)
