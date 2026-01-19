"""
Prepare training data from daily_features_v2 table.

This script:
1. Loads all data from gold.db → daily_features_v2
2. Transforms from wide format (1 row per day) to long format (1 row per ORB)
3. Filters out rows with missing targets (no break_dir or r_multiple)
4. Saves as Parquet for fast ML training

Output: ml_data/historical_features.parquet
"""

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DB_PATH = "gold.db"
OUTPUT_DIR = Path("ml_data")
OUTPUT_FILE = OUTPUT_DIR / "historical_features.parquet"

# ORB times to extract
ORB_TIMES = ["0900", "1000", "1100", "1800", "2300", "0030"]


def load_daily_features(conn):
    """Load all data from daily_features_v2 table."""
    logger.info("Loading daily_features_v2 from database...")

    query = """
    SELECT *
    FROM daily_features_v2
    ORDER BY date_local ASC
    """

    df = conn.execute(query).fetchdf()
    logger.info(f"Loaded {len(df)} days of data")
    logger.info(f"Date range: {df['date_local'].min()} to {df['date_local'].max()}")
    logger.info(f"Instruments: {df['instrument'].unique().tolist()}")

    return df


def transform_to_orb_rows(df):
    """
    Transform from wide format (1 row per day) to long format (1 row per ORB).

    Input: 740 rows (days) × 86 columns
    Output: ~4,440 rows (740 days × 6 ORBs) × features
    """
    logger.info("Transforming to ORB-level rows...")

    orb_rows = []

    for _, day_row in df.iterrows():
        date_local = day_row['date_local']
        instrument = day_row['instrument']

        # Base features (same for all ORBs on this day)
        base_features = {
            'date_local': date_local,
            'instrument': instrument,
            # Pre-session ranges
            'pre_asia_high': day_row.get('pre_asia_high'),
            'pre_asia_low': day_row.get('pre_asia_low'),
            'pre_asia_range': day_row.get('pre_asia_range'),
            'pre_london_high': day_row.get('pre_london_high'),
            'pre_london_low': day_row.get('pre_london_low'),
            'pre_london_range': day_row.get('pre_london_range'),
            'pre_ny_high': day_row.get('pre_ny_high'),
            'pre_ny_low': day_row.get('pre_ny_low'),
            'pre_ny_range': day_row.get('pre_ny_range'),
            # Session ranges
            'asia_high': day_row.get('asia_high'),
            'asia_low': day_row.get('asia_low'),
            'asia_range': day_row.get('asia_range'),
            'london_high': day_row.get('london_high'),
            'london_low': day_row.get('london_low'),
            'london_range': day_row.get('london_range'),
            'ny_high': day_row.get('ny_high'),
            'ny_low': day_row.get('ny_low'),
            'ny_range': day_row.get('ny_range'),
            # Technical indicators
            'atr_14': day_row.get('atr_20'),  # Using atr_20 from database
            'rsi_14': day_row.get('rsi_at_0030'),  # RSI at 00:30
            # Session type codes
            'asia_type_code': day_row.get('asia_type_code'),
            'london_type_code': day_row.get('london_type_code'),
            'pre_ny_type_code': day_row.get('pre_ny_type_code'),
        }

        # Create one row per ORB
        for orb_time in ORB_TIMES:
            orb_features = base_features.copy()

            # ORB-specific data
            orb_features['orb_time'] = orb_time
            orb_features['orb_high'] = day_row.get(f'orb_{orb_time}_high')
            orb_features['orb_low'] = day_row.get(f'orb_{orb_time}_low')
            orb_features['orb_size'] = day_row.get(f'orb_{orb_time}_size')
            orb_features['orb_break_dir'] = day_row.get(f'orb_{orb_time}_break_dir')
            orb_features['orb_outcome'] = day_row.get(f'orb_{orb_time}_outcome')
            orb_features['orb_r_multiple'] = day_row.get(f'orb_{orb_time}_r_multiple')

            # Derive session context from ORB time
            # 0900-1100: Asia session, 1800-2300: London session, 0030: NY session
            session_map = {
                '0900': 'ASIA', '1000': 'ASIA', '1100': 'ASIA',
                '1800': 'LONDON', '2300': 'LONDON', '0030': 'NY'
            }
            orb_features['session_context'] = session_map.get(orb_time, 'UNKNOWN')

            # Skip if ORB data is completely missing (weekend/holiday)
            if pd.isna(orb_features['orb_size']):
                continue

            orb_rows.append(orb_features)

    result_df = pd.DataFrame(orb_rows)
    logger.info(f"Created {len(result_df)} ORB rows from {len(df)} days")

    return result_df


def add_engineered_features(df):
    """
    Add additional engineered features for ML training.

    These are features that aren't in the database but are useful for ML.
    """
    logger.info("Engineering additional features...")

    # Time-based features
    df['date_local'] = pd.to_datetime(df['date_local'])
    df['day_of_week'] = df['date_local'].dt.dayofweek  # 0=Monday, 6=Sunday
    df['day_of_month'] = df['date_local'].dt.day
    df['month'] = df['date_local'].dt.month
    df['quarter'] = df['date_local'].dt.quarter

    # Cyclical encoding for day_of_week (better for ML)
    df['day_of_week_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
    df['day_of_week_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)

    # ORB time as integer for ordering
    orb_time_map = {'0900': 9, '1000': 10, '1100': 11, '1800': 18, '2300': 23, '0030': 0.5}
    df['orb_hour'] = df['orb_time'].map(orb_time_map)

    # Normalized ranges (size relative to ATR)
    df['orb_size_pct_atr'] = df['orb_size'] / df['atr_14']
    df['asia_range_pct_atr'] = df['asia_range'] / df['atr_14']
    df['london_range_pct_atr'] = df['london_range'] / df['atr_14']
    df['ny_range_pct_atr'] = df['ny_range'] / df['atr_14']

    # Inter-session gaps (if sessions are populated)
    df['asia_to_london_gap'] = (
        df['london_low'] - df['asia_high']
    ).where(df['london_low'] > df['asia_high'], 0)

    df['london_to_ny_gap'] = (
        df['ny_low'] - df['london_high']
    ).where(df['ny_low'] > df['london_high'], 0)

    # Session range ratios
    df['london_asia_range_ratio'] = df['london_range'] / df['asia_range']
    df['ny_london_range_ratio'] = df['ny_range'] / df['london_range']

    # ORB position in session (where is ORB relative to session high/low)
    # This will be added in Phase 2 when we have more context

    # Session type encoding (one-hot) for session context
    if 'session_context' in df.columns:
        session_dummies = pd.get_dummies(df['session_context'], prefix='session', dummy_na=False)
        df = pd.concat([df, session_dummies], axis=1)

    # Session type codes encoding (one-hot)
    for type_col in ['asia_type_code', 'london_type_code', 'pre_ny_type_code']:
        if type_col in df.columns:
            type_dummies = pd.get_dummies(df[type_col], prefix=type_col, dummy_na=False)
            df = pd.concat([df, type_dummies], axis=1)

    # Lag features (previous day outcomes) - sort first
    df = df.sort_values(['instrument', 'date_local', 'orb_time']).reset_index(drop=True)

    for instrument in df['instrument'].unique():
        instrument_mask = df['instrument'] == instrument

        # Shift by 6 rows (1 day = 6 ORBs) to get previous day
        df.loc[instrument_mask, 'prev_day_avg_r'] = (
            df.loc[instrument_mask, 'orb_r_multiple'].shift(6)
        )

        # Rolling features (last 3 days)
        df.loc[instrument_mask, 'avg_r_last_3d'] = (
            df.loc[instrument_mask, 'orb_r_multiple']
            .rolling(window=18, min_periods=1)  # 3 days × 6 ORBs
            .mean()
        )

    logger.info(f"Added engineered features. Total columns: {len(df.columns)}")

    return df


def filter_valid_targets(df):
    """
    Filter out rows without valid targets.

    For training, we need:
    - break_dir (for directional classifier)
    - r_multiple (for R-predictor)
    - outcome (for entry quality scorer)
    """
    logger.info("Filtering rows with valid targets...")

    initial_count = len(df)

    # Keep rows with valid break direction
    df = df[df['orb_break_dir'].notna()].copy()

    logger.info(f"Kept {len(df)}/{initial_count} rows with valid targets")
    logger.info(f"Break direction distribution:\n{df['orb_break_dir'].value_counts()}")

    if 'orb_outcome' in df.columns:
        logger.info(f"Outcome distribution:\n{df['orb_outcome'].value_counts()}")

    return df


def save_to_parquet(df, output_path):
    """Save DataFrame to Parquet format."""
    logger.info(f"Saving to {output_path}...")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to Parquet (fast, compressed)
    df.to_parquet(output_path, index=False, compression='snappy')

    # Log statistics
    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Saved {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"File size: {file_size_mb:.2f} MB")
    logger.info(f"Memory usage: {df.memory_usage(deep=True).sum() / (1024**2):.2f} MB")


def generate_summary_report(df):
    """Generate summary statistics of the prepared data."""
    logger.info("\n" + "="*60)
    logger.info("TRAINING DATA SUMMARY")
    logger.info("="*60)

    logger.info(f"\nTotal samples: {len(df)}")
    logger.info(f"Date range: {df['date_local'].min()} to {df['date_local'].max()}")
    logger.info(f"Total days: {df['date_local'].nunique()}")

    logger.info(f"\nInstruments:")
    for instrument in df['instrument'].unique():
        count = len(df[df['instrument'] == instrument])
        logger.info(f"  {instrument}: {count} samples")

    logger.info(f"\nORB times:")
    for orb_time in sorted(df['orb_time'].unique()):
        count = len(df[df['orb_time'] == orb_time])
        pct = 100 * count / len(df)
        logger.info(f"  {orb_time}: {count} samples ({pct:.1f}%)")

    logger.info(f"\nBreak direction distribution:")
    for direction, count in df['orb_break_dir'].value_counts().items():
        pct = 100 * count / len(df)
        logger.info(f"  {direction}: {count} samples ({pct:.1f}%)")

    logger.info(f"\nTarget variable statistics:")
    logger.info(f"  R-multiple mean: {df['orb_r_multiple'].mean():.3f}")
    logger.info(f"  R-multiple std: {df['orb_r_multiple'].std():.3f}")
    logger.info(f"  R-multiple min: {df['orb_r_multiple'].min():.3f}")
    logger.info(f"  R-multiple max: {df['orb_r_multiple'].max():.3f}")

    if 'orb_outcome' in df.columns:
        win_rate = 100 * (df['orb_outcome'] == 'WIN').sum() / len(df)
        logger.info(f"  Overall win rate: {win_rate:.1f}%")

    logger.info(f"\nMissing values:")
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if len(missing) > 0:
        for col, count in missing.head(10).items():
            pct = 100 * count / len(df)
            logger.info(f"  {col}: {count} ({pct:.1f}%)")
    else:
        logger.info("  No missing values in key features")

    logger.info("\n" + "="*60)


def main():
    """Main execution function."""
    logger.info("="*60)
    logger.info("PREPARING ML TRAINING DATA")
    logger.info("="*60)

    # Connect to database
    logger.info(f"Connecting to {DB_PATH}...")
    conn = duckdb.connect(DB_PATH, read_only=True)

    try:
        # Step 1: Load daily features
        df = load_daily_features(conn)

        # Step 2: Transform to ORB-level rows
        df = transform_to_orb_rows(df)

        # Step 3: Add engineered features
        df = add_engineered_features(df)

        # Step 4: Filter valid targets
        df = filter_valid_targets(df)

        # Step 5: Save to Parquet
        save_to_parquet(df, OUTPUT_FILE)

        # Step 6: Generate summary
        generate_summary_report(df)

        logger.info("\n✓ Data preparation complete!")
        logger.info(f"Output: {OUTPUT_FILE}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
