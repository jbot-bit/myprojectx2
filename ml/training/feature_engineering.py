"""
Feature engineering utilities for ML models.

This module provides reusable feature engineering functions that work
for both training (batch) and inference (real-time).

CRITICAL: All features must be calculable at decision time (no lookahead bias).
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List


# Feature column groups for model training
BASE_FEATURES = [
    # Time features
    'day_of_week_sin', 'day_of_week_cos',
    'orb_hour',

    # Pre-session ranges
    'pre_asia_range', 'pre_london_range', 'pre_ny_range',

    # Session ranges
    'asia_range', 'london_range', 'ny_range',

    # Technical indicators
    'atr_14', 'rsi_14',

    # Travel metrics
    'pre_ny_travel', 'pre_orb_travel',

    # ORB characteristics
    'orb_size', 'orb_size_pct_atr',

    # Normalized ranges
    'asia_range_pct_atr', 'london_range_pct_atr', 'ny_range_pct_atr',

    # Inter-session gaps
    'asia_to_london_gap', 'london_to_ny_gap',

    # Session ratios
    'london_asia_range_ratio', 'ny_london_range_ratio',

    # Lag features
    'prev_day_avg_r', 'avg_r_last_3d',
]

CATEGORICAL_FEATURES = [
    'orb_time',
    'instrument',
]

# Session type one-hot features (added dynamically)
SESSION_FEATURES_PREFIX = 'session_'


def engineer_time_features(date_local: pd.Timestamp) -> Dict[str, float]:
    """
    Extract time-based features from a date.

    Args:
        date_local: Trading date (local timezone)

    Returns:
        Dictionary of time features
    """
    day_of_week = date_local.dayofweek

    return {
        'day_of_week': day_of_week,
        'day_of_week_sin': np.sin(2 * np.pi * day_of_week / 7),
        'day_of_week_cos': np.cos(2 * np.pi * day_of_week / 7),
        'day_of_month': date_local.day,
        'month': date_local.month,
        'quarter': date_local.quarter,
    }


def engineer_orb_features(orb_time: str, orb_data: Dict[str, Any], atr_14: float) -> Dict[str, float]:
    """
    Engineer ORB-specific features.

    Args:
        orb_time: ORB time (e.g., '0900', '1000')
        orb_data: Dict with orb_high, orb_low, orb_size
        atr_14: 14-period ATR

    Returns:
        Dictionary of ORB features
    """
    orb_time_map = {'0900': 9, '1000': 10, '1100': 11, '1800': 18, '2300': 23, '0030': 0.5}

    # Get ORB size, ensure it's not None
    orb_size = orb_data.get('orb_size') or 0

    features = {
        'orb_hour': orb_time_map.get(orb_time, 0),
        'orb_size': orb_size,
        'orb_high': orb_data.get('orb_high'),
        'orb_low': orb_data.get('orb_low'),
    }

    # Normalized features (handle division by zero and None)
    if atr_14 and atr_14 > 0:
        features['orb_size_pct_atr'] = orb_size / atr_14
    else:
        features['orb_size_pct_atr'] = 0

    return features


def engineer_session_features(
    asia_data: Dict[str, Any],
    london_data: Dict[str, Any],
    ny_data: Dict[str, Any],
    atr_14: float
) -> Dict[str, float]:
    """
    Engineer session-based features.

    Args:
        asia_data: Dict with asia_high, asia_low, asia_range
        london_data: Dict with london_high, london_low, london_range
        ny_data: Dict with ny_high, ny_low, ny_range
        atr_14: 14-period ATR

    Returns:
        Dictionary of session features
    """
    # Get session ranges, ensure they're not None
    asia_range = asia_data.get('asia_range') or 0
    london_range = london_data.get('london_range') or 0
    ny_range = ny_data.get('ny_range') or 0

    features = {
        'asia_range': asia_range,
        'london_range': london_range,
        'ny_range': ny_range,
    }

    # Normalized ranges (handle None and division by zero)
    if atr_14 and atr_14 > 0:
        features['asia_range_pct_atr'] = asia_range / atr_14
        features['london_range_pct_atr'] = london_range / atr_14
        features['ny_range_pct_atr'] = ny_range / atr_14
    else:
        features['asia_range_pct_atr'] = 0
        features['london_range_pct_atr'] = 0
        features['ny_range_pct_atr'] = 0

    # Inter-session gaps
    asia_high = asia_data.get('asia_high', 0)
    london_low = london_data.get('london_low', 0)
    london_high = london_data.get('london_high', 0)
    ny_low = ny_data.get('ny_low', 0)

    features['asia_to_london_gap'] = max(0, london_low - asia_high) if asia_high and london_low else 0
    features['london_to_ny_gap'] = max(0, ny_low - london_high) if london_high and ny_low else 0

    # Session ratios (handle division by zero and None)
    asia_range = features.get('asia_range') or 0
    london_range = features.get('london_range') or 0
    ny_range = features.get('ny_range') or 0

    if asia_range and asia_range > 0:
        features['london_asia_range_ratio'] = london_range / asia_range
    else:
        features['london_asia_range_ratio'] = 1.0

    if london_range and london_range > 0:
        features['ny_london_range_ratio'] = ny_range / london_range
    else:
        features['ny_london_range_ratio'] = 1.0

    return features


def engineer_travel_features(pre_ny_travel: float, pre_orb_travel: float) -> Dict[str, float]:
    """
    Engineer travel-based features.

    Args:
        pre_ny_travel: Price travel before NY session
        pre_orb_travel: Price travel before ORB

    Returns:
        Dictionary of travel features
    """
    return {
        'pre_ny_travel': pre_ny_travel or 0,
        'pre_orb_travel': pre_orb_travel or 0,
    }


def engineer_all_features(feature_dict: Dict[str, Any]) -> Dict[str, float]:
    """
    Engineer all features from raw feature dictionary.

    This is the main function to use for real-time inference.

    Args:
        feature_dict: Dictionary with all raw features from data_loader

    Returns:
        Dictionary of all engineered features ready for model input
    """
    engineered = {}

    # Time features
    if 'date_local' in feature_dict:
        date_local = pd.Timestamp(feature_dict['date_local'])
        engineered.update(engineer_time_features(date_local))

    # ORB features
    if 'orb_time' in feature_dict:
        orb_data = {
            'orb_high': feature_dict.get('orb_high'),
            'orb_low': feature_dict.get('orb_low'),
            'orb_size': feature_dict.get('orb_size'),
        }
        engineered.update(
            engineer_orb_features(
                feature_dict['orb_time'],
                orb_data,
                feature_dict.get('atr_14', 0)
            )
        )

    # Session features
    asia_data = {
        'asia_high': feature_dict.get('asia_high'),
        'asia_low': feature_dict.get('asia_low'),
        'asia_range': feature_dict.get('asia_range'),
    }
    london_data = {
        'london_high': feature_dict.get('london_high'),
        'london_low': feature_dict.get('london_low'),
        'london_range': feature_dict.get('london_range'),
    }
    ny_data = {
        'ny_high': feature_dict.get('ny_high'),
        'ny_low': feature_dict.get('ny_low'),
        'ny_range': feature_dict.get('ny_range'),
    }
    engineered.update(
        engineer_session_features(asia_data, london_data, ny_data, feature_dict.get('atr_14', 0))
    )

    # Travel features
    engineered.update(
        engineer_travel_features(
            feature_dict.get('pre_ny_travel'),
            feature_dict.get('pre_orb_travel')
        )
    )

    # Pre-session ranges
    engineered['pre_asia_range'] = feature_dict.get('pre_asia_range', 0)
    engineered['pre_london_range'] = feature_dict.get('pre_london_range', 0)
    engineered['pre_ny_range'] = feature_dict.get('pre_ny_range', 0)

    # Technical indicators
    engineered['atr_14'] = feature_dict.get('atr_14', 0)
    engineered['rsi_14'] = feature_dict.get('rsi_14', 50)  # Default to neutral

    # Lag features (would come from feature store in real-time)
    engineered['prev_day_avg_r'] = feature_dict.get('prev_day_avg_r', 0)
    engineered['avg_r_last_3d'] = feature_dict.get('avg_r_last_3d', 0)

    # Categorical features
    engineered['orb_time'] = feature_dict.get('orb_time', '0900')
    engineered['instrument'] = feature_dict.get('instrument', 'MGC')

    # Session code (one-hot encoding will be done by model)
    engineered['session_code'] = feature_dict.get('session_code', 'UNKNOWN')

    return engineered


def get_feature_columns() -> List[str]:
    """
    Get the list of feature columns expected by models.

    Returns:
        List of feature column names in order
    """
    return BASE_FEATURES + CATEGORICAL_FEATURES


def validate_features(features: Dict[str, Any]) -> bool:
    """
    Validate that all required features are present.

    Args:
        features: Dictionary of features

    Returns:
        True if valid, False otherwise
    """
    required_features = get_feature_columns()

    missing = []
    for feature in required_features:
        if feature not in features:
            missing.append(feature)

    if missing:
        print(f"Missing features: {missing}")
        return False

    return True


def fill_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing values with sensible defaults.

    Args:
        df: DataFrame with features

    Returns:
        DataFrame with missing values filled
    """
    # Numeric features: fill with 0
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    # Categorical features: fill with 'UNKNOWN'
    categorical_cols = df.select_dtypes(include=['object']).columns
    df[categorical_cols] = df[categorical_cols].fillna('UNKNOWN')

    return df


def prepare_features_for_model(df: pd.DataFrame, categorical_encoders: Dict = None) -> pd.DataFrame:
    """
    Prepare features for model input.

    This includes:
    - Selecting only required columns
    - Encoding categorical variables
    - Filling missing values
    - Ensuring correct data types

    Args:
        df: DataFrame with engineered features
        categorical_encoders: Optional dict of encoders for categorical features

    Returns:
        DataFrame ready for model.predict()
    """
    # Select feature columns
    feature_cols = get_feature_columns()

    # Add session one-hot columns if present
    session_cols = [col for col in df.columns if col.startswith(SESSION_FEATURES_PREFIX)]
    feature_cols.extend(session_cols)

    # Select only available columns
    available_cols = [col for col in feature_cols if col in df.columns]
    df_model = df[available_cols].copy()

    # Fill missing values
    df_model = fill_missing_values(df_model)

    # Encode categorical variables if encoders provided
    if categorical_encoders:
        for col, encoder in categorical_encoders.items():
            if col in df_model.columns:
                df_model[col] = encoder.transform(df_model[col])

    return df_model


# For debugging/testing
if __name__ == "__main__":
    # Example usage
    sample_features = {
        'date_local': '2026-01-17',
        'instrument': 'MGC',
        'orb_time': '0900',
        'orb_high': 2680.5,
        'orb_low': 2679.8,
        'orb_size': 0.7,
        'asia_high': 2681.0,
        'asia_low': 2678.0,
        'asia_range': 3.0,
        'london_high': 2682.0,
        'london_low': 2679.0,
        'london_range': 3.0,
        'ny_high': 2683.0,
        'ny_low': 2678.5,
        'ny_range': 4.5,
        'atr_14': 5.2,
        'rsi_14': 55.0,
        'pre_ny_travel': 2.5,
        'pre_orb_travel': 1.8,
        'pre_asia_range': 2.8,
        'pre_london_range': 3.1,
        'pre_ny_range': 4.0,
        'prev_day_avg_r': 0.5,
        'avg_r_last_3d': 0.3,
        'session_code': 'A2',
    }

    print("Engineering features from sample data...")
    engineered = engineer_all_features(sample_features)

    print("\nEngineered features:")
    for key, value in sorted(engineered.items()):
        print(f"  {key}: {value}")

    print(f"\nTotal features: {len(engineered)}")
    print(f"Feature validation: {validate_features(engineered)}")
