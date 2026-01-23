"""
Import Phase 1B conditional setups into validated_setups table.

Phase 1B discovered condition-dependent edges from research/phase1B_condition_edges.csv.
This script imports setups that meet quality thresholds:
- delta_avg_r > +0.3R (meaningful improvement over baseline)
- filtered_avg_r > 0 (profitable after filtering)
- retention_pct >= 25% (sufficient trade frequency)
"""

import duckdb
import pandas as pd
import re
from datetime import date
from pathlib import Path

# Quality thresholds
MIN_DELTA_R = 0.3  # Require at least +0.3R improvement
MIN_FILTERED_AVG_R = 0.0  # Must be profitable after filtering
MIN_RETENTION_PCT = 25.0  # Must have at least 25% of trades

def parse_family_id(family_id: str) -> dict:
    """
    Parse family_id to extract setup parameters.

    Example: MGC_1000_UP_8.0R_HALF -> {instrument: MGC, orb_time: 1000, direction: UP, rr: 8.0, sl_mode: HALF}
    """
    parts = family_id.split('_')

    if len(parts) < 5:
        raise ValueError(f"Invalid family_id format: {family_id}")

    instrument = parts[0]
    orb_time = parts[1]
    direction = parts[2]
    rr_str = parts[3]  # e.g., "8.0R"
    sl_mode = parts[4]

    # Parse RR value
    rr_match = re.match(r'(\d+\.?\d*)R', rr_str)
    if not rr_match:
        raise ValueError(f"Cannot parse RR from {rr_str}")
    rr = float(rr_match.group(1))

    return {
        'instrument': instrument,
        'orb_time': orb_time,
        'direction': direction,
        'rr': rr,
        'sl_mode': sl_mode
    }

def parse_condition(condition_str: str) -> tuple:
    """
    Parse condition string to extract type and value.

    Example: "asia_bias=ABOVE" -> ("asia_bias", "ABOVE")
    """
    if '=' not in condition_str:
        raise ValueError(f"Invalid condition format: {condition_str}")

    parts = condition_str.split('=')
    return parts[0], parts[1]

def main():
    # Load Phase 1B results
    csv_path = Path("research/phase1B_condition_edges.csv")
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found!")
        return

    df = pd.read_csv(csv_path)

    print("=" * 80)
    print("PHASE 1B CONDITIONAL SETUP IMPORT")
    print("=" * 80)
    print(f"\nTotal setups in CSV: {len(df)}")

    # Filter to quality thresholds
    filtered_df = df[
        (df['delta_avg_r'] >= MIN_DELTA_R) &
        (df['filtered_avg_r'] > MIN_FILTERED_AVG_R) &
        (df['retention_pct'] >= MIN_RETENTION_PCT)
    ].copy()

    print(f"Setups meeting quality thresholds: {len(filtered_df)}")
    print(f"  - delta_avg_r >= {MIN_DELTA_R}R")
    print(f"  - filtered_avg_r > {MIN_FILTERED_AVG_R}R")
    print(f"  - retention_pct >= {MIN_RETENTION_PCT}%")

    if len(filtered_df) == 0:
        print("\nNo setups meet quality thresholds. Exiting.")
        return

    # Connect to database
    conn = duckdb.connect('data/db/gold.db')

    # Insert conditional setups
    inserted_count = 0
    skipped_count = 0

    for idx, row in filtered_df.iterrows():
        try:
            # Parse family_id
            params = parse_family_id(row['family_id'])

            # Parse condition
            condition_type, condition_value = parse_condition(row['condition'])

            # Generate setup_id (includes condition)
            setup_id = f"{params['instrument']}_{params['orb_time']}_{params['direction']}_RR{params['rr']}_{params['sl_mode']}_{condition_type}={condition_value}"

            # Generate baseline_setup_id (without condition)
            baseline_setup_id = f"{params['instrument']}_{params['orb_time']}_{params['direction']}_RR{params['rr']}_{params['sl_mode']}_BASELINE"

            # Calculate annual trades
            trades = int(row['filtered_trades'])
            annual_trades = int(trades * 365 / 740)  # 740 days in dataset

            # Determine tier based on filtered_avg_r
            filtered_avg_r = float(row['filtered_avg_r'])
            if filtered_avg_r >= 0.8:
                tier = 'S+'
            elif filtered_avg_r >= 0.5:
                tier = 'S'
            elif filtered_avg_r >= 0.3:
                tier = 'A'
            elif filtered_avg_r >= 0.15:
                tier = 'B'
            else:
                tier = 'C'

            # Create notes
            delta_r = float(row['delta_avg_r'])
            retention = float(row['retention_pct'])
            notes = f"Conditional edge: {condition_type}={condition_value} | Baseline: {row['baseline_avg_r']:.3f}R → Filtered: {filtered_avg_r:.3f}R (Δ +{delta_r:.3f}R) | {retention:.1f}% retention"

            # Insert into database
            conn.execute("""
                INSERT INTO validated_setups (
                    setup_id, instrument, orb_time, rr, sl_mode,
                    close_confirmations, buffer_ticks, orb_size_filter,
                    atr_filter, min_gap_filter,
                    trades, win_rate, avg_r, annual_trades,
                    tier, notes, validated_date, data_source,
                    condition_type, condition_value, baseline_setup_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                setup_id,
                params['instrument'],
                params['orb_time'],
                params['rr'],
                params['sl_mode'],
                1,  # close_confirmations (default)
                0.0,  # buffer_ticks (default)
                None,  # orb_size_filter (not used in conditional setups)
                None,  # atr_filter
                None,  # min_gap_filter
                trades,
                float(row['filtered_win_rate']),
                filtered_avg_r,
                annual_trades,
                tier,
                notes,
                date.today(),
                'phase1B_condition_edges.csv',
                condition_type,
                condition_value,
                baseline_setup_id
            ])

            inserted_count += 1

        except Exception as e:
            print(f"ERROR processing {row['family_id']}: {e}")
            skipped_count += 1
            continue

    conn.commit()

    # Summary
    print(f"\n{'=' * 80}")
    print("IMPORT COMPLETE")
    print(f"{'=' * 80}")
    print(f"Inserted: {inserted_count} conditional setups")
    print(f"Skipped: {skipped_count} setups (errors)")

    # Show breakdown by condition type
    result = conn.execute("""
        SELECT
            condition_type,
            condition_value,
            COUNT(*) as setup_count,
            ROUND(AVG(avg_r), 3) as avg_expectancy,
            ROUND(AVG(win_rate), 1) as avg_win_rate
        FROM validated_setups
        WHERE condition_type IS NOT NULL
        GROUP BY condition_type, condition_value
        ORDER BY condition_type, avg_expectancy DESC
    """).df()

    print(f"\nConditional setups by condition:")
    print(result.to_string(index=False))

    # Show total setup count
    total_setups = conn.execute("SELECT COUNT(*) FROM validated_setups").fetchone()[0]
    baseline_setups = conn.execute("SELECT COUNT(*) FROM validated_setups WHERE condition_type IS NULL").fetchone()[0]
    conditional_setups = conn.execute("SELECT COUNT(*) FROM validated_setups WHERE condition_type IS NOT NULL").fetchone()[0]

    print(f"\nTotal setups in database:")
    print(f"  Baseline setups: {baseline_setups}")
    print(f"  Conditional setups: {conditional_setups}")
    print(f"  Total: {total_setups}")

    conn.close()

    print(f"\n{'=' * 80}")
    print("READY FOR MARKET STATE DETECTION")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
