#!/usr/bin/env python3
"""
Convert asia_edge_specs.json to format expected by edge_import.py
"""

import json
from pathlib import Path

# Load Asia edge specs
specs_path = Path(__file__).parent / "asia_edge_specs.json"
with open(specs_path, 'r') as f:
    specs = json.load(f)

# Convert to import format
candidates_for_import = []

for edge in specs["viable_edges"]:
    candidate = {
        "research_id": edge["id"],
        "name": f"Asia {edge['orb_time']} ORB - RR{edge['rr']} {edge['sl_mode']}",
        "instrument": edge["instrument"],
        "hypothesis_text": (
            f"{edge['orb_time']} ORB breakout with {edge['sl_mode']} SL mode. "
            f"Entry: {edge['entry_rule']}. Stop: {edge['stop_rule']}. Target: RR={edge['rr']}. "
            f"Scan window: {edge['scan_window']['start']} → {edge['scan_window']['end']} ({edge['scan_window']['description']}). "
            f"Expected: {edge['expected_metrics']['365d_avg_r']:.3f}R avg ({edge['expected_metrics']['365d_trades']} trades), "
            f"{edge['expected_metrics']['split_stability']} split stability."
        ),
        "filter_spec": {
            "type": "Asia ORB - Isolation Mode",
            "description": edge['scan_window']['description'],
            "scan_window_start": edge['scan_window']['start'],
            "scan_window_end": edge['scan_window']['end'],
            "filters_applied": edge['filters'] if edge['filters'] else []
        },
        "test_config": {
            "orb_time": edge['orb_time'],
            "orb_duration_min": edge['orb_duration_min'],
            "entry_rule": edge['entry_rule'],
            "stop_rule": edge['stop_rule'],
            "sl_mode": edge['sl_mode'],
            "target_rule": f"RR={edge['rr']}",
            "rr": edge['rr'],
            "scan_window": f"{edge['scan_window']['start']} → {edge['scan_window']['end']}"
        },
        "metrics": {
            "365d": {
                "trades": edge['expected_metrics']['365d_trades'],
                "win_rate": edge['expected_metrics']['365d_win_rate'],
                "avg_r": edge['expected_metrics']['365d_avg_r'],
                "total_r": edge['expected_metrics']['365d_total_r']
            },
            "splits": {
                "stability": edge['expected_metrics']['split_stability'],
                "split1_avg_r": edge['expected_metrics']['split1_avg_r'],
                "split2_avg_r": edge['expected_metrics']['split2_avg_r'],
                "split3_avg_r": edge['expected_metrics']['split3_avg_r']
            }
        },
        "slippage_assumptions": {
            "entry": 0,
            "exit": 0,
            "notes": "Zero slippage assumed in research. Stress tests pending."
        },
        "code_version": "asia_backtest_core.py (2026-01-21)",
        "data_version": f"bars_1m ({specs['metadata']['date_range']})",
        "survival_score": "HIGH" if edge['expected_metrics']['split_stability'] == "3/3 positive" else "MEDIUM",
        "confidence_level": "HIGH" if edge['expected_metrics']['split_stability'] == "3/3 positive" else "MEDIUM"
    }

    # Add source metadata to notes
    candidate["source_notes"] = (
        f"Source: {specs['metadata']['source']} | "
        f"Date range: {specs['metadata']['date_range']} | "
        f"Total days: {specs['metadata']['total_days']} | "
        f"Determinism hash: {specs['metadata']['determinism_hash']} | "
        f"Zero-lookahead: {specs['metadata']['zero_lookahead_verified']} | "
        f"Recommendation: {edge['recommendation']} | "
        f"Notes: {edge['notes']}"
    )

    candidates_for_import.append(candidate)

# Save
output_path = Path(__file__).parent / "asia_candidates_for_import.json"
with open(output_path, 'w') as f:
    json.dump(candidates_for_import, f, indent=2)

print(f"Converted {len(candidates_for_import)} viable Asia edges to import format")
print(f"Saved to: {output_path}")
print()
print("Candidates:")
for c in candidates_for_import:
    print(f"  - {c['name']} (research_id: {c['research_id']})")
