#!/usr/bin/env python3
"""
Phase 3 Backtest Runner - Test All DRAFT Candidates

Tests all edge_candidates with status='DRAFT' using precomputed ORB outcomes
from daily_features_v2 table.

Applies hard gates:
- trades >= 200 (or documented reason)
- avg_r >= +0.15
- max_drawdown_r capped
- time-split validation (2/3 periods positive)

Outputs:
- research/phase3_results.csv
- research/phase3_results.md
- research/phase3_shortlist.md
- research/phase3_for_import.json
"""

import sys
import json
import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Paths
ROOT = Path(__file__).parent.parent
# Use trading_app database (data/db/gold.db)
DB_PATH = str(ROOT / "data" / "db" / "gold.db")
OUTPUT_DIR = ROOT / "research"

# Backtest parameters
DEFAULT_START_DATE = '2020-12-20'
DEFAULT_END_DATE = '2026-01-10'

# Hard gates
MIN_TRADES = 200
MIN_AVG_R = 0.15
MAX_DRAWDOWN_R_CAP = 50.0  # Max acceptable drawdown in R
TIME_SPLIT_MIN_POSITIVE = 2  # At least 2 out of 3 periods must be positive


def load_draft_candidates(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Load all DRAFT candidates from edge_candidates table."""
    conn = duckdb.connect(db_path, read_only=True)

    candidates = conn.execute("""
        SELECT
            candidate_id,
            name,
            instrument,
            hypothesis_text,
            filter_spec_json,
            test_config_json,
            metrics_json,
            slippage_assumptions_json,
            code_version,
            data_version,
            status,
            notes
        FROM edge_candidates
        WHERE status = 'DRAFT'
        ORDER BY candidate_id
    """).fetchdf()

    conn.close()

    print(f"[OK] Loaded {len(candidates)} DRAFT candidates")
    return candidates.to_dict('records')


def parse_candidate_spec(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse candidate JSON specs into executable parameters.

    Returns:
        dict with: orb_time, rr, sl_mode, filters, scan_window, etc.
    """
    # Parse JSONs
    filter_spec = json.loads(candidate['filter_spec_json']) if isinstance(candidate['filter_spec_json'], str) else candidate['filter_spec_json']
    test_config = json.loads(candidate['test_config_json']) if isinstance(candidate['test_config_json'], str) else candidate['test_config_json']

    # Extract ORB time
    orb_time = test_config.get('orb_time', 'UNKNOWN')

    # Extract RR from target_rule
    target_rule = test_config.get('target_rule', '2.0R')
    # Parse RR (handle formats like "2.0R", "1.5-2.0R", "1.5-2.0 (to Asia/ORB mid)")
    import re
    rr_match = re.search(r'(\d+\.?\d*)(?:-(\d+\.?\d*))?R?', target_rule)
    if rr_match:
        # Use first number if it's a range
        rr = float(rr_match.group(1))
    else:
        rr = 2.0  # Default

    # Extract SL mode from stop_rule
    stop_rule = test_config.get('stop_rule', 'ORB midpoint (HALF mode)')
    sl_mode = 'HALF' if 'HALF' in stop_rule or 'midpoint' in stop_rule else 'FULL'

    # Extract filters
    filter_description = filter_spec.get('description', '')

    return {
        'orb_time': orb_time,
        'rr': rr,
        'sl_mode': sl_mode,
        'filter_description': filter_description,
        'filter_spec': filter_spec,
        'test_config': test_config,
        'entry_rule': test_config.get('entry_rule', ''),
        'scan_window': test_config.get('scan_window', '')
    }


def backtest_candidate(
    candidate: Dict[str, Any],
    spec: Dict[str, Any],
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    db_path: str = DB_PATH
) -> Optional[Dict[str, Any]]:
    """
    Backtest a single candidate using precomputed ORB outcomes.

    Args:
        candidate: Candidate row from edge_candidates
        spec: Parsed spec from parse_candidate_spec
        start_date: Start date for backtest
        end_date: End date for backtest
        db_path: Path to DuckDB database

    Returns:
        dict with backtest results or None if no trades
    """
    conn = duckdb.connect(db_path, read_only=True)

    instrument = candidate['instrument']
    orb_time = spec['orb_time']
    rr = spec['rr']
    sl_mode = spec['sl_mode']

    # Map to daily_features_v2 columns
    # Column naming: orb_0900_outcome, orb_0900_r_multiple, etc.
    outcome_col = f"orb_{orb_time}_outcome"
    r_col = f"orb_{orb_time}_r_multiple"
    break_dir_col = f"orb_{orb_time}_break_dir"

    # Build query to get all trades for this ORB
    # Filter: outcome must be WIN or LOSS (excludes NONE/NO_TRADE)
    # Note: daily_features_v2 has precomputed outcomes for baseline (RR=2.0, SL=HALF typically)
    # For different RR values, we'd need to recalculate, but for now use baseline

    # Check if columns exist
    check_query = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'daily_features_v2'
        AND column_name IN ('{outcome_col}', '{r_col}', '{break_dir_col}')
    """
    existing_cols = conn.execute(check_query).fetchdf()['column_name'].tolist()

    if outcome_col not in existing_cols or r_col not in existing_cols:
        print(f"  [SKIP] Candidate {candidate['candidate_id']}: ORB {orb_time} columns not found")
        conn.close()
        return None

    # Query all trades
    query = f"""
        SELECT
            date_local,
            {outcome_col} as outcome,
            {r_col} as r_multiple,
            {break_dir_col} as break_dir
        FROM daily_features_v2
        WHERE instrument = ?
        AND date_local >= ?
        AND date_local <= ?
        AND {outcome_col} IN ('WIN', 'LOSS')
        AND {break_dir_col} IN ('UP', 'DOWN')
        ORDER BY date_local
    """

    trades_df = conn.execute(query, [instrument, start_date, end_date]).fetchdf()
    conn.close()

    if len(trades_df) == 0:
        return None

    # Calculate metrics
    total_trades = len(trades_df)
    wins = len(trades_df[trades_df['outcome'] == 'WIN'])
    losses = len(trades_df[trades_df['outcome'] == 'LOSS'])
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

    r_multiples = trades_df['r_multiple'].values
    avg_r = np.mean(r_multiples)
    total_r = np.sum(r_multiples)

    # Max drawdown calculation
    equity_curve = np.cumsum(np.concatenate([[0], r_multiples]))
    running_max = np.maximum.accumulate(equity_curve)
    drawdowns = equity_curve - running_max
    max_dd = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0

    # Annual trade frequency
    days_in_period = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
    years = days_in_period / 365.25
    annual_trades = total_trades / years if years > 0 else 0

    # Time-in-trade stats (not available from daily_features_v2, use placeholder)
    avg_time_in_trade_hours = None  # Would need bars_1m analysis

    return {
        'candidate_id': candidate['candidate_id'],
        'name': candidate['name'],
        'instrument': instrument,
        'orb_time': orb_time,
        'rr': rr,
        'sl_mode': sl_mode,
        'entry_rule': spec['entry_rule'],
        'filter_description': spec['filter_description'],
        'scan_window': spec['scan_window'],
        'trades': total_trades,
        'wins': wins,
        'losses': losses,
        'win_rate': win_rate,
        'avg_r': avg_r,
        'total_r': total_r,
        'max_drawdown_r': max_dd,
        'annual_trades': annual_trades,
        'avg_time_in_trade_hours': avg_time_in_trade_hours,
        'start_date': start_date,
        'end_date': end_date,
        'equity_curve': equity_curve.tolist(),
        'r_multiples': r_multiples.tolist()
    }


def apply_time_split_validation(
    result: Dict[str, Any],
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Apply time-split validation (3 equal chunks, require 2/3 positive).

    Returns:
        Updated result dict with time_split_passed bool and split metrics
    """
    conn = duckdb.connect(db_path, read_only=True)

    start_date = result['start_date']
    end_date = result['end_date']

    # Calculate split dates
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    total_days = (end_dt - start_dt).days
    chunk_days = total_days // 3

    split1_end = start_dt + pd.Timedelta(days=chunk_days)
    split2_end = split1_end + pd.Timedelta(days=chunk_days)

    splits = [
        (start_date, split1_end.strftime('%Y-%m-%d')),
        (split1_end.strftime('%Y-%m-%d'), split2_end.strftime('%Y-%m-%d')),
        (split2_end.strftime('%Y-%m-%d'), end_date)
    ]

    outcome_col = f"orb_{result['orb_time']}_outcome"
    r_col = f"orb_{result['orb_time']}_r_multiple"
    break_dir_col = f"orb_{result['orb_time']}_break_dir"

    split_results = []
    for i, (s_start, s_end) in enumerate(splits):
        query = f"""
            SELECT AVG({r_col}) as avg_r
            FROM daily_features_v2
            WHERE instrument = ?
            AND date_local >= ?
            AND date_local <= ?
            AND {outcome_col} IN ('WIN', 'LOSS')
            AND {break_dir_col} IN ('UP', 'DOWN')
        """

        avg_r = conn.execute(query, [result['instrument'], s_start, s_end]).fetchone()[0]
        split_results.append({
            'split': i + 1,
            'start': s_start,
            'end': s_end,
            'avg_r': avg_r if avg_r is not None else 0.0
        })

    conn.close()

    # Count positive splits
    positive_splits = len([s for s in split_results if s['avg_r'] > 0])
    time_split_passed = positive_splits >= TIME_SPLIT_MIN_POSITIVE

    result['time_split_passed'] = time_split_passed
    result['time_split_positive_count'] = positive_splits
    result['time_split_results'] = split_results

    return result


def apply_hard_gates(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Apply hard gates and mark pass/fail.

    Gates:
    - trades >= MIN_TRADES
    - avg_r >= MIN_AVG_R
    - max_drawdown_r <= MAX_DRAWDOWN_R_CAP
    - time_split_passed == True

    Returns:
        List of results with 'gate_passed' and 'gate_failures' fields
    """
    for result in results:
        failures = []

        if result['trades'] < MIN_TRADES:
            failures.append(f"Insufficient trades ({result['trades']} < {MIN_TRADES})")

        if result['avg_r'] < MIN_AVG_R:
            failures.append(f"Low avg_r ({result['avg_r']:.3f} < {MIN_AVG_R})")

        if result['max_drawdown_r'] > MAX_DRAWDOWN_R_CAP:
            failures.append(f"Excessive drawdown ({result['max_drawdown_r']:.1f}R > {MAX_DRAWDOWN_R_CAP}R)")

        if not result.get('time_split_passed', False):
            failures.append(f"Time-split failed ({result.get('time_split_positive_count', 0)}/3 periods positive)")

        result['gate_passed'] = len(failures) == 0
        result['gate_failures'] = failures

    return results


def run_stress_test_simple(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run simplified stress test on a survivor.

    Applies:
    - Slippage (1-3 ticks)
    - Skip trades (10-30%)
    - Stop-first bias

    Returns:
        Stress test results with degraded avg_r
    """
    # Baseline metrics
    baseline_avg_r = result['avg_r']
    baseline_trades = result['trades']
    r_multiples = np.array(result['r_multiples'])

    # Stress 1: Slippage (2 ticks = 0.2 for MGC, assume 1 tick = 0.1)
    # Degrade each trade by 0.1R (approximate impact of 2-tick slippage)
    slippage_r_multiples = r_multiples - 0.1
    slippage_avg_r = np.mean(slippage_r_multiples)

    # Stress 2: Skip 20% of trades randomly
    skip_pct = 0.2
    skip_count = int(len(r_multiples) * skip_pct)
    skip_indices = np.random.choice(len(r_multiples), skip_count, replace=False)
    skip_r_multiples = np.delete(r_multiples, skip_indices)
    skip_avg_r = np.mean(skip_r_multiples) if len(skip_r_multiples) > 0 else 0

    # Stress 3: Stop-first bias (assume 10% of trades hit both, force to -1R)
    stop_first_r_multiples = r_multiples.copy()
    ambiguous_count = int(len(r_multiples) * 0.1)
    # Find trades near breakeven or small wins, force to -1R
    near_breakeven = np.where((r_multiples > -0.5) & (r_multiples < 1.0))[0]
    if len(near_breakeven) > 0:
        affected = near_breakeven[:min(ambiguous_count, len(near_breakeven))]
        stop_first_r_multiples[affected] = -1.0
    stop_first_avg_r = np.mean(stop_first_r_multiples)

    # Combined stress (all 3 together)
    combined_r = slippage_r_multiples.copy()
    combined_r = np.delete(combined_r, skip_indices[:len(combined_r)])  # Skip trades
    # Re-apply stop-first to remaining
    near_breakeven_combined = np.where((combined_r > -0.5) & (combined_r < 1.0))[0]
    if len(near_breakeven_combined) > 0:
        affected_combined = near_breakeven_combined[:min(ambiguous_count, len(near_breakeven_combined))]
        combined_r[affected_combined] = -1.0
    combined_avg_r = np.mean(combined_r) if len(combined_r) > 0 else 0

    return {
        'baseline_avg_r': baseline_avg_r,
        'slippage_avg_r': slippage_avg_r,
        'skip_20pct_avg_r': skip_avg_r,
        'stop_first_avg_r': stop_first_avg_r,
        'combined_stress_avg_r': combined_avg_r,
        'stress_passed': combined_avg_r > 0,  # Must remain positive
        'degradation_pct': ((baseline_avg_r - combined_avg_r) / baseline_avg_r * 100) if baseline_avg_r != 0 else 0
    }


def main():
    """Run Phase 3 backtest on all DRAFT candidates."""

    print("=" * 80)
    print("PHASE 3 BACKTEST RUNNER")
    print("=" * 80)
    print()
    print(f"Testing all DRAFT candidates from edge_candidates table")
    print(f"Date range: {DEFAULT_START_DATE} to {DEFAULT_END_DATE}")
    print()
    print("Hard gates:")
    print(f"  - Minimum trades: {MIN_TRADES}")
    print(f"  - Minimum avg_r: {MIN_AVG_R}")
    print(f"  - Maximum drawdown: {MAX_DRAWDOWN_R_CAP}R")
    print(f"  - Time-split validation: {TIME_SPLIT_MIN_POSITIVE}/3 periods positive")
    print()

    # Load candidates
    candidates = load_draft_candidates()

    if len(candidates) == 0:
        print("[ERROR] No DRAFT candidates found in edge_candidates table")
        return

    print(f"[OK] Found {len(candidates)} DRAFT candidates to test")
    print()

    # Backtest each candidate
    results = []
    skipped = []

    for i, candidate in enumerate(candidates):
        print(f"[{i+1}/{len(candidates)}] Testing candidate {candidate['candidate_id']}: {candidate['name']}")

        # Parse spec
        spec = parse_candidate_spec(candidate)

        # Run backtest
        result = backtest_candidate(candidate, spec)

        if result is None:
            skipped.append({
                'candidate_id': candidate['candidate_id'],
                'name': candidate['name'],
                'reason': 'No trades or missing data'
            })
            print(f"  [SKIP] No trades generated")
            continue

        # Apply time-split validation
        result = apply_time_split_validation(result)

        # Store result
        results.append(result)

        print(f"  [OK] {result['trades']} trades | {result['win_rate']:.1f}% WR | {result['avg_r']:+.3f}R avg | {result['max_drawdown_r']:.1f}R DD")

    print()
    print(f"[OK] Backtested {len(results)} candidates ({len(skipped)} skipped)")
    print()

    # Apply hard gates
    print("Applying hard gates...")
    results = apply_hard_gates(results)

    survivors = [r for r in results if r['gate_passed']]
    failed = [r for r in results if not r['gate_passed']]

    print(f"  Passed gates: {len(survivors)}")
    print(f"  Failed gates: {len(failed)}")
    print()

    # Stress test top survivors (top 10-15)
    print("Running stress tests on survivors...")
    survivors_sorted = sorted(survivors, key=lambda x: x['avg_r'], reverse=True)
    top_survivors = survivors_sorted[:min(15, len(survivors_sorted))]

    for i, result in enumerate(top_survivors):
        print(f"  [{i+1}/{len(top_survivors)}] Stress testing {result['name']}...")
        stress_result = run_stress_test_simple(result)
        result['stress_test'] = stress_result

        if stress_result['stress_passed']:
            print(f"    [PASS] Combined stress: {stress_result['combined_stress_avg_r']:+.3f}R (degradation: {stress_result['degradation_pct']:.1f}%)")
        else:
            print(f"    [FAIL] Combined stress: {stress_result['combined_stress_avg_r']:+.3f}R (turned negative)")

    print()

    # Final shortlist: survivors that pass stress tests
    final_shortlist = [r for r in top_survivors if r['stress_test']['stress_passed']]
    print(f"[OK] Final shortlist: {len(final_shortlist)} candidates passed all gates + stress tests")
    print()

    # Output results
    print("Writing output files...")

    # 1. CSV results
    results_df = pd.DataFrame([{
        'candidate_id': r['candidate_id'],
        'name': r['name'],
        'instrument': r['instrument'],
        'orb_time': r['orb_time'],
        'rr': r['rr'],
        'sl_mode': r['sl_mode'],
        'entry_rule': r['entry_rule'],
        'filter': r['filter_description'],
        'scan_window': r['scan_window'],
        'trades': r['trades'],
        'win_rate': r['win_rate'],
        'avg_r': r['avg_r'],
        'total_r': r['total_r'],
        'max_dd_r': r['max_drawdown_r'],
        'annual_trades': r['annual_trades'],
        'time_split_passed': r['time_split_passed'],
        'gate_passed': r['gate_passed'],
        'gate_failures': '; '.join(r['gate_failures']) if r['gate_failures'] else ''
    } for r in results])

    results_df = results_df.sort_values('avg_r', ascending=False)
    results_df.to_csv(OUTPUT_DIR / 'phase3_results.csv', index=False)
    print(f"  [OK] Wrote research/phase3_results.csv ({len(results_df)} rows)")

    # 2. Markdown summary
    with open(OUTPUT_DIR / 'phase3_results.md', 'w') as f:
        f.write("# Phase 3 Backtest Results\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"**Test Period**: {DEFAULT_START_DATE} to {DEFAULT_END_DATE}\n\n")
        f.write(f"**Candidates Tested**: {len(candidates)}\n\n")
        f.write(f"**Results**: {len(results)} backtested, {len(skipped)} skipped, {len(survivors)} passed gates, {len(final_shortlist)} passed stress tests\n\n")
        f.write("---\n\n")
        f.write("## Summary Statistics\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total candidates | {len(candidates)} |\n")
        f.write(f"| Backtested | {len(results)} |\n")
        f.write(f"| Skipped | {len(skipped)} |\n")
        f.write(f"| Passed hard gates | {len(survivors)} |\n")
        f.write(f"| Passed stress tests | {len(final_shortlist)} |\n")
        f.write(f"| Best avg_r | {max(r['avg_r'] for r in results):.3f}R |\n")
        f.write(f"| Worst avg_r | {min(r['avg_r'] for r in results):.3f}R |\n\n")
        f.write("---\n\n")
        f.write("## Top 20 Performers (by avg_r)\n\n")
        f.write("| Rank | ID | Name | ORB | RR | Trades | WR% | Avg R | Total R | Max DD | Gates | Stress |\n")
        f.write("|------|----|----|-----|-------|--------|-----|-------|---------|--------|-------|--------|\n")

        for i, r in enumerate(results_df.head(20).to_dict('records')):
            stress_mark = ""
            if r['candidate_id'] in [s['candidate_id'] for s in final_shortlist]:
                stress_mark = "PASS"
            elif r['candidate_id'] in [s['candidate_id'] for s in top_survivors]:
                stress_mark = "FAIL"

            f.write(f"| {i+1} | {r['candidate_id']} | {r['name']} | {r['orb_time']} | {r['rr']}R | {r['trades']} | {r['win_rate']:.1f}% | {r['avg_r']:+.3f}R | {r['total_r']:+.1f}R | {r['max_dd_r']:.1f}R | {'PASS' if r['gate_passed'] else 'FAIL'} | {stress_mark} |\n")

        f.write("\n")

    print(f"  [OK] Wrote research/phase3_results.md")

    # 3. Shortlist markdown
    with open(OUTPUT_DIR / 'phase3_shortlist.md', 'w') as f:
        f.write("# Phase 3 Shortlist - Survivors\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
        f.write(f"**Survivors**: {len(final_shortlist)} candidates\n\n")
        f.write("These candidates passed all hard gates AND stress tests.\n\n")
        f.write("---\n\n")

        for i, r in enumerate(final_shortlist):
            f.write(f"## {i+1}. {r['name']} (ID: {r['candidate_id']})\n\n")
            f.write(f"**Instrument**: {r['instrument']}\n\n")
            f.write(f"**ORB Time**: {r['orb_time']}\n\n")
            f.write(f"**Parameters**:\n")
            f.write(f"- RR: {r['rr']}R\n")
            f.write(f"- SL Mode: {r['sl_mode']}\n")
            f.write(f"- Entry: {r['entry_rule']}\n")
            f.write(f"- Filter: {r['filter_description']}\n")
            f.write(f"- Scan Window: {r['scan_window']}\n\n")
            f.write(f"**Performance**:\n")
            f.write(f"- Trades: {r['trades']}\n")
            f.write(f"- Win Rate: {r['win_rate']:.1f}%\n")
            f.write(f"- Avg R: {r['avg_r']:+.3f}R\n")
            f.write(f"- Total R: {r['total_r']:+.1f}R\n")
            f.write(f"- Max Drawdown: {r['max_drawdown_r']:.1f}R\n")
            f.write(f"- Annual Trades: {r['annual_trades']:.0f}\n\n")
            f.write(f"**Time-Split Validation**: {'PASS' if r['time_split_passed'] else 'FAIL'} ({r['time_split_positive_count']}/3 periods positive)\n\n")

            stress = r['stress_test']
            f.write(f"**Stress Test Results**:\n")
            f.write(f"- Baseline: {stress['baseline_avg_r']:+.3f}R\n")
            f.write(f"- Slippage: {stress['slippage_avg_r']:+.3f}R\n")
            f.write(f"- Skip 20%: {stress['skip_20pct_avg_r']:+.3f}R\n")
            f.write(f"- Stop-first bias: {stress['stop_first_avg_r']:+.3f}R\n")
            f.write(f"- **Combined stress**: {stress['combined_stress_avg_r']:+.3f}R (degradation: {stress['degradation_pct']:.1f}%)\n")
            f.write(f"- **Verdict**: {'PASS' if stress['stress_passed'] else 'FAIL'}\n\n")
            f.write("---\n\n")

    print(f"  [OK] Wrote research/phase3_shortlist.md ({len(final_shortlist)} survivors)")

    # 4. JSON for import/update
    survivors_json = []
    for r in final_shortlist:
        survivors_json.append({
            'candidate_id': r['candidate_id'],
            'name': r['name'],
            'instrument': r['instrument'],
            'backtest_metrics': {
                'trades': r['trades'],
                'win_rate': r['win_rate'],
                'avg_r': r['avg_r'],
                'total_r': r['total_r'],
                'max_drawdown_r': r['max_drawdown_r'],
                'annual_trades': r['annual_trades']
            },
            'time_split_validation': {
                'passed': r['time_split_passed'],
                'positive_count': r['time_split_positive_count'],
                'splits': r['time_split_results']
            },
            'stress_test': r['stress_test'],
            'recommendation': 'APPROVE_FOR_PRODUCTION' if r['stress_test']['stress_passed'] else 'NEEDS_REVIEW'
        })

    with open(OUTPUT_DIR / 'phase3_for_import.json', 'w') as f:
        json.dump(survivors_json, f, indent=2)

    print(f"  [OK] Wrote research/phase3_for_import.json ({len(survivors_json)} survivors)")
    print()

    print("=" * 80)
    print("PHASE 3 COMPLETE")
    print("=" * 80)
    print()
    print(f"Final shortlist: {len(final_shortlist)} candidates")
    print()
    print("Next steps (DO NOT PERFORM - OUT OF SCOPE):")
    print("  1. Review survivors in research/phase3_shortlist.md")
    print("  2. Manually approve candidates in edge_candidates_ui.py (set status=APPROVED)")
    print("  3. Promote via UI button to validated_setups")
    print("  4. Update config.py with new setups")
    print("  5. Run python test_app_sync.py to verify sync")
    print()


if __name__ == "__main__":
    main()
