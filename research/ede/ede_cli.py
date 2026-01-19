"""
Edge Discovery Engine (EDE) - Command Line Interface

Main entry point for the complete edge discovery system.

Commands:
- generate: Run edge generators (brute, conditional, contrast, inversion, ml)
- validate: Run validation pipeline on candidates
- approve: Review and approve survivors
- monitor: Monitor live edge performance
- stats: Show pipeline statistics

Usage:
    python ede_cli.py generate --mode brute --count 100
    python ede_cli.py validate --limit 50
    python ede_cli.py approve --min-confidence MEDIUM
    python ede_cli.py stats
"""

import argparse
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ede.generator_brute import BruteParameterGenerator
from ede.validation_pipeline import ValidationPipeline
from ede.lifecycle_manager import LifecycleManager, EdgeStatus
from ede.backtest_engine import BacktestEngine
import duckdb

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_generate(args):
    """Run edge generators."""
    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE - GENERATION")
    print("="*70)

    if args.mode == 'brute':
        print(f"\nRunning brute parameter search...")
        print(f"  Max candidates: {args.count}")
        print(f"  Instruments: {args.instruments}")

        generator = BruteParameterGenerator(instruments=args.instruments)
        stats = generator.run_generation(
            max_candidates=args.count,
            instruments=args.instruments,
            submit_to_pipeline=True
        )

        print("\nGeneration Complete!")
        print(f"  Generated: {stats['generated']}")
        print(f"  Accepted: {stats['accepted']}")
        print(f"  Duplicates: {stats['duplicates']}")
        print(f"  Invalid: {stats['invalid']}")

    else:
        print(f"\nMode '{args.mode}' not yet implemented.")
        print("Available modes: brute")


def cmd_validate(args):
    """Run validation pipeline on candidates."""
    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE - VALIDATION")
    print("="*70)

    # Get candidates ready for validation
    manager = LifecycleManager()
    candidates = manager.get_candidates_for_backtest(limit=args.limit)

    if len(candidates) == 0:
        print("\nNo candidates ready for validation.")
        print("Run 'ede_cli.py generate' first to create candidates.")
        return

    print(f"\nFound {len(candidates)} candidates to validate")
    print(f"Date range: {args.start_date} to {args.end_date}")

    pipeline = ValidationPipeline()

    survivors = []
    failed = []

    for i, candidate in enumerate(candidates, 1):
        print(f"\n[{i}/{len(candidates)}] Validating: {candidate['idea_id']}")

        try:
            result = pipeline.validate_candidate(
                candidate,
                start_date=args.start_date,
                end_date=args.end_date
            )

            if result.passed:
                survivors.append(result)

                # Submit survivor
                survivor_data = {
                    'idea_id': result.idea_id,
                    'baseline_trades': result.baseline_result.total_trades,
                    'baseline_win_rate': result.baseline_result.win_rate,
                    'baseline_avg_r': result.baseline_result.avg_r,
                    'baseline_expectancy': result.baseline_result.expectancy,
                    'baseline_max_dd': result.baseline_result.max_dd,
                    'baseline_profit_factor': result.baseline_result.profit_factor,
                    'baseline_sharpe': result.baseline_result.sharpe,
                    'cost_1tick_expectancy': result.cost_1tick_exp,
                    'cost_2tick_expectancy': result.cost_2tick_exp,
                    'cost_3tick_expectancy': result.cost_3tick_exp,
                    'cost_atr_expectancy': result.cost_atr_exp,
                    'cost_missedfill_expectancy': result.cost_missedfill_exp,
                    'attack_stopfirst_expectancy': result.attack_stopfirst_exp,
                    'attack_entrydelay_expectancy': result.attack_entrydelay_exp,
                    'attack_exitdelay_expectancy': result.attack_exitdelay_exp,
                    'attack_noise_expectancy': result.attack_noise_exp,
                    'attack_shuffle_expectancy': result.attack_shuffle_exp,
                    'regime_year_count': result.regime_year_count,
                    'regime_year_profitable': result.regime_year_profitable,
                    'regime_volatility_count': result.regime_volatility_count,
                    'regime_volatility_profitable': result.regime_volatility_profitable,
                    'regime_session_count': result.regime_session_count,
                    'regime_session_profitable': result.regime_session_profitable,
                    'regime_max_profit_concentration': result.regime_max_concentration,
                    'walkforward_windows': 0,
                    'walkforward_profitable': 0,
                    'walkforward_avg_expectancy': 0
                }

                manager.submit_survivor(survivor_data)
                print(f"  [OK] SURVIVOR - Score: {result.survival_score:.1f}, Confidence: {result.confidence}")

            else:
                failed.append(result)
                print(f"  [FAIL] {result.failure_reason}")

        except Exception as e:
            logger.error(f"Error validating {candidate['idea_id']}: {e}")
            failed.append(None)

    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)
    print(f"\nSurvivors: {len(survivors)}")
    print(f"Failed: {len(failed)}")

    if survivors:
        print("\nTop Survivors:")
        sorted_survivors = sorted(survivors, key=lambda x: x.survival_score, reverse=True)
        for i, s in enumerate(sorted_survivors[:10], 1):
            print(f"  {i}. {s.idea_id[:30]}")
            print(f"     Score: {s.survival_score:.1f} | Confidence: {s.confidence}")
            print(f"     Expectancy: {s.baseline_result.expectancy:.2f}R | Trades: {s.baseline_result.total_trades}")


def cmd_approve(args):
    """Review and approve survivors."""
    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE - APPROVAL")
    print("="*70)

    manager = LifecycleManager()
    survivors = manager.get_survivors_for_approval(min_confidence=args.min_confidence)

    if len(survivors) == 0:
        print(f"\nNo survivors with confidence >= {args.min_confidence}")
        print("Run 'ede_cli.py validate' first to create survivors.")
        return

    print(f"\nFound {len(survivors)} survivors ready for approval")
    print(f"Minimum confidence: {args.min_confidence}")

    for i, survivor in enumerate(survivors, 1):
        print(f"\n[{i}/{len(survivors)}] {survivor['human_name']}")
        print(f"  Survivor ID: {survivor['survivor_id']}")
        print(f"  Instrument: {survivor['instrument']}")
        print(f"  Score: {survivor['survival_score']:.1f}")
        print(f"  Confidence: {survivor['confidence_level']}")
        print(f"  Expectancy: {survivor['baseline_expectancy']:.2f}R")
        print(f"  Win Rate: {survivor['baseline_win_rate']:.1f}%")
        print(f"  Trades: {survivor['baseline_trades']}")

    print("\n" + "="*70)
    print("APPROVAL FLOW")
    print("="*70)
    print("\nNext steps:")
    print("  1. Review survivors above")
    print("  2. Manual approval process (to be implemented)")
    print("  3. Sync to validated_setups and config.py")
    print("  4. Auto-generate documentation")


def cmd_monitor(args):
    """Monitor live edge performance."""
    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE - LIVE MONITORING")
    print("="*70)
    print("\nMonitoring system not yet implemented.")
    print("This will track live edge performance and detect drift.")


def cmd_stats(args):
    """Show pipeline statistics."""
    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE - PIPELINE STATISTICS")
    print("="*70)

    manager = LifecycleManager()
    stats = manager.get_pipeline_stats()

    print("\nPipeline Status:")
    print(f"  Total Candidates: {stats['total_candidates']}")
    print(f"  Generated (ready): {stats['generated']}")
    print(f"  Testing: {stats['testing']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Survivors: {stats['survivors']}")
    print(f"  Approved: {stats['approved']}")
    print(f"  Active: {stats['active']}")
    print(f"  Suspended: {stats['suspended']}")

    # Conversion funnel
    if stats['total_candidates'] > 0:
        survivor_rate = (stats['survivors'] / stats['total_candidates']) * 100
        approval_rate = (stats['approved'] / stats['total_candidates']) * 100 if stats['total_candidates'] > 0 else 0

        print(f"\nConversion Funnel:")
        print(f"  Generated -> Survivor: {survivor_rate:.1f}%")
        print(f"  Generated -> Approved: {approval_rate:.1f}%")

    # Sample candidates
    con = duckdb.connect(manager.db_path)

    print("\nRecent Candidates:")
    recent = con.execute("""
        SELECT idea_id, human_name, instrument, status
        FROM edge_candidates_raw
        ORDER BY generation_timestamp DESC
        LIMIT 5
    """).fetchdf()

    if len(recent) > 0:
        for idx, row in recent.iterrows():
            print(f"  - {row['human_name'][:40]} ({row['status']})")

    print("\nRecent Survivors:")
    survivors = con.execute("""
        SELECT
            s.survivor_id,
            c.human_name,
            c.instrument,
            s.survival_score,
            s.confidence_level
        FROM edge_candidates_survivors s
        JOIN edge_candidates_raw c ON s.idea_id = c.idea_id
        ORDER BY s.survival_timestamp DESC
        LIMIT 5
    """).fetchdf()

    if len(survivors) > 0:
        for idx, row in survivors.iterrows():
            print(f"  - {row['human_name'][:40]}")
            print(f"    Score: {row['survival_score']:.1f} | Confidence: {row['confidence_level']}")
    else:
        print("  (none yet)")

    con.close()


def main():
    parser = argparse.ArgumentParser(
        description='Edge Discovery Engine - Systematic edge discovery and validation'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Generate command
    parser_gen = subparsers.add_parser('generate', help='Run edge generators')
    parser_gen.add_argument('--mode', type=str, default='brute', choices=['brute', 'conditional', 'contrast', 'inversion', 'ml'],
                           help='Generator mode')
    parser_gen.add_argument('--count', type=int, default=100, help='Maximum candidates to generate')
    parser_gen.add_argument('--instruments', type=str, nargs='+', default=['MGC'], help='Instruments to generate for')

    # Validate command
    parser_val = subparsers.add_parser('validate', help='Run validation pipeline')
    parser_val.add_argument('--limit', type=int, default=50, help='Maximum candidates to validate')
    parser_val.add_argument('--start-date', type=str, default='2024-01-01', help='Backtest start date')
    parser_val.add_argument('--end-date', type=str, default='2026-01-15', help='Backtest end date')

    # Approve command
    parser_app = subparsers.add_parser('approve', help='Review and approve survivors')
    parser_app.add_argument('--min-confidence', type=str, default='MEDIUM', choices=['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'],
                           help='Minimum confidence level')

    # Monitor command
    parser_mon = subparsers.add_parser('monitor', help='Monitor live edge performance')

    # Stats command
    parser_stats = subparsers.add_parser('stats', help='Show pipeline statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to command handler
    if args.command == 'generate':
        cmd_generate(args)
    elif args.command == 'validate':
        cmd_validate(args)
    elif args.command == 'approve':
        cmd_approve(args)
    elif args.command == 'monitor':
        cmd_monitor(args)
    elif args.command == 'stats':
        cmd_stats(args)


if __name__ == "__main__":
    main()
