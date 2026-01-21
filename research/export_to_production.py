#!/usr/bin/env python3
"""
Export Research Candidates to Production Staging

Exports EDE survivors from research/ede system to a canonical JSON file
for import into production edge_candidates table.

Usage:
    python research/export_to_production.py --output candidates_export.json --min-confidence MEDIUM

Requirements:
    - EDE schema initialized (python research/ede/init_ede_schema.py)
    - Candidates generated and validated (python research/ede/ede_cli.py)
    - Survivors available in edge_candidates_survivors table
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "trading_app"))

from cloud_mode import get_database_connection


def export_survivors_to_json(
    output_path: str,
    min_confidence: str = "MEDIUM",
    min_score: int = 60
):
    """
    Export EDE survivors to canonical JSON format.

    Args:
        output_path: Path to output JSON file
        min_confidence: Minimum confidence level (LOW, MEDIUM, HIGH, VERY_HIGH)
        min_score: Minimum survival score (0-100)

    Output Format:
        [
            {
                "research_id": "survivor_id from EDE",
                "name": "Human readable name",
                "instrument": "MGC/NQ/MPL",
                "hypothesis_text": "Edge hypothesis description",
                "filter_spec": {
                    "orb_size_filter": 0.05,
                    "sl_mode": "FULL"
                },
                "test_config": {
                    "test_window_start": "2024-01-01",
                    "test_window_end": "2026-01-15"
                },
                "metrics": {
                    "orb_time": "0900",
                    "rr": 8.0,
                    "win_rate": 63.3,
                    "avg_r": 0.266,
                    "annual_trades": 260,
                    "tier": "S+"
                },
                "slippage_assumptions": {
                    "slippage_ticks": 2
                },
                "code_version": "git_hash",
                "data_version": "daily_features_v2",
                "survival_score": 85,
                "confidence_level": "VERY_HIGH"
            }
        ]
    """
    conn = get_database_connection(read_only=True)

    try:
        print("=" * 70)
        print("Export Research Candidates to Production")
        print("=" * 70)
        print()
        print(f"Min Confidence: {min_confidence}")
        print(f"Min Score: {min_score}")
        print()

        # Query survivors from EDE
        query = """
            SELECT
                s.survivor_id,
                s.idea_id,
                c.human_name,
                c.instrument,
                c.entry_rule_json,
                c.exit_rule_json,
                c.risk_model_json,
                c.filters_json,
                c.param_hash,
                s.baseline_expectancy,
                s.baseline_win_rate,
                s.baseline_avg_r,
                s.baseline_trade_count,
                s.survival_score,
                s.confidence_level,
                s.cost_tests_json,
                s.attack_results_json,
                s.regime_splits_json,
                s.validation_timestamp
            FROM edge_candidates_survivors s
            JOIN edge_candidates_raw c ON s.idea_id = c.idea_id
            WHERE s.confidence_level IN (
                CASE
                    WHEN ? = 'LOW' THEN ('LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH')
                    WHEN ? = 'MEDIUM' THEN ('MEDIUM', 'HIGH', 'VERY_HIGH')
                    WHEN ? = 'HIGH' THEN ('HIGH', 'VERY_HIGH')
                    WHEN ? = 'VERY_HIGH' THEN ('VERY_HIGH')
                END
            )
            AND s.survival_score >= ?
            ORDER BY s.survival_score DESC
        """

        # Note: DuckDB doesn't support CASE with tuple membership, so we simplify
        confidence_filter = {
            "LOW": ["LOW", "MEDIUM", "HIGH", "VERY_HIGH"],
            "MEDIUM": ["MEDIUM", "HIGH", "VERY_HIGH"],
            "HIGH": ["HIGH", "VERY_HIGH"],
            "VERY_HIGH": ["VERY_HIGH"]
        }

        allowed_levels = confidence_filter.get(min_confidence.upper(), ["MEDIUM", "HIGH", "VERY_HIGH"])

        simple_query = """
            SELECT
                s.survivor_id,
                s.idea_id,
                c.human_name,
                c.instrument,
                c.entry_rule_json,
                c.exit_rule_json,
                c.risk_model_json,
                c.filters_json,
                c.param_hash,
                s.baseline_expectancy,
                s.baseline_win_rate,
                s.baseline_avg_r,
                s.baseline_trade_count,
                s.survival_score,
                s.confidence_level,
                s.cost_tests_json,
                s.attack_results_json,
                s.regime_splits_json,
                s.validation_timestamp
            FROM edge_candidates_survivors s
            JOIN edge_candidates_raw c ON s.idea_id = c.idea_id
            WHERE s.survival_score >= ?
            ORDER BY s.survival_score DESC
        """

        survivors = conn.execute(simple_query, [min_score]).fetchall()

        # Filter by confidence level in Python
        filtered_survivors = [s for s in survivors if s[14] in allowed_levels]

        print(f"Found {len(filtered_survivors)} survivors meeting criteria")
        print()

        if len(filtered_survivors) == 0:
            print("No survivors to export. Run EDE validation first:")
            print("  python research/ede/ede_cli.py validate --limit 50")
            return

        # Build export payload
        export_data = []

        for row in filtered_survivors:
            (survivor_id, idea_id, human_name, instrument,
             entry_rule_json, exit_rule_json, risk_model_json, filters_json, param_hash,
             baseline_expectancy, baseline_win_rate, baseline_avg_r, baseline_trade_count,
             survival_score, confidence_level,
             cost_tests_json, attack_results_json, regime_splits_json,
             validation_timestamp) = row

            # Parse JSON fields
            entry_rule = json.loads(entry_rule_json) if entry_rule_json else {}
            exit_rule = json.loads(exit_rule_json) if exit_rule_json else {}
            risk_model = json.loads(risk_model_json) if risk_model_json else {}
            filters = json.loads(filters_json) if filters_json else {}

            # Map to production edge_candidates schema
            candidate = {
                "research_id": survivor_id,
                "name": human_name,
                "instrument": instrument,
                "hypothesis_text": f"EDE survivor {survivor_id}: {human_name} (score={survival_score}, confidence={confidence_level})",
                "filter_spec": {
                    "orb_size_filter": filters.get("orb_size_filter"),
                    "sl_mode": risk_model.get("sl_mode", "FULL")
                },
                "test_config": {
                    "test_window_start": "2024-01-01",  # From EDE backtest config
                    "test_window_end": "2026-01-15"
                },
                "metrics": {
                    "orb_time": entry_rule.get("orb_time", "0900"),
                    "rr": risk_model.get("rr", 1.0),
                    "win_rate": baseline_win_rate,
                    "avg_r": baseline_avg_r,
                    "annual_trades": baseline_trade_count,  # Proxy
                    "tier": _calculate_tier(survival_score, confidence_level)
                },
                "slippage_assumptions": {
                    "slippage_ticks": 2  # Standard assumption
                },
                "code_version": param_hash[:8],  # Use param hash as version
                "data_version": "daily_features_v2",
                "survival_score": survival_score,
                "confidence_level": confidence_level
            }

            export_data.append(candidate)

        # Write to JSON file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"Exported {len(export_data)} candidates to {output_file}")
        print()
        print("Next step:")
        print(f"  python trading_app/edge_import.py --input {output_path}")
        print()

    finally:
        conn.close()


def _calculate_tier(score: int, confidence: str) -> str:
    """Calculate tier from survival score and confidence."""
    if score >= 80 and confidence == "VERY_HIGH":
        return "S+"
    elif score >= 70 and confidence in ["HIGH", "VERY_HIGH"]:
        return "S"
    elif score >= 60 and confidence in ["MEDIUM", "HIGH", "VERY_HIGH"]:
        return "A"
    else:
        return "B"


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export EDE survivors to production staging format"
    )
    parser.add_argument(
        "--output",
        default="research/candidates_export.json",
        help="Output JSON file path (default: research/candidates_export.json)"
    )
    parser.add_argument(
        "--min-confidence",
        choices=["LOW", "MEDIUM", "HIGH", "VERY_HIGH"],
        default="MEDIUM",
        help="Minimum confidence level (default: MEDIUM)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Minimum survival score 0-100 (default: 60)"
    )

    args = parser.parse_args()

    export_survivors_to_json(
        output_path=args.output,
        min_confidence=args.min_confidence,
        min_score=args.min_score
    )


if __name__ == "__main__":
    main()
