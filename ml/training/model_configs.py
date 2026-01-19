"""
Model configurations and hyperparameters.

This module contains hyperparameters for different ML models used in the system.
"""

from typing import Dict, Any


# LightGBM Directional Classifier Configuration
DIRECTIONAL_CLASSIFIER_CONFIG = {
    'model_type': 'lightgbm',
    'objective': 'multiclass',
    'num_class': 3,  # UP, DOWN, NONE
    'metric': 'multi_logloss',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.03,  # Lower for more stable learning with class weights
    'feature_fraction': 0.9,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'max_depth': 7,
    'min_child_samples': 10,  # Lower to help minority class
    'reg_alpha': 0.1,
    'reg_lambda': 0.1,
    'n_estimators': 1000,  # More trees with lower learning rate
    'early_stopping_rounds': 100,  # More patience
    'random_state': 42,
}

# XGBoost Entry Quality Scorer Configuration (Phase 3)
ENTRY_QUALITY_CONFIG = {
    'model_type': 'xgboost',
    'objective': 'binary:logistic',
    'eval_metric': 'logloss',
    'max_depth': 6,
    'learning_rate': 0.05,
    'n_estimators': 300,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 3,
    'gamma': 0.1,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'early_stopping_rounds': 50,
    'random_state': 42,
}

# XGBoost R-Multiple Predictor Configuration (Phase 3)
R_MULTIPLE_CONFIG = {
    'model_type': 'xgboost',
    'objective': 'reg:squarederror',
    'eval_metric': 'mae',
    'max_depth': 5,
    'learning_rate': 0.05,
    'n_estimators': 300,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 5,
    'gamma': 0.0,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'early_stopping_rounds': 50,
    'random_state': 42,
}

# Training configuration
TRAINING_CONFIG = {
    # Data splits
    'train_split': 0.60,  # 60% for training
    'val_split': 0.20,    # 20% for validation
    'test_split': 0.20,   # 20% for testing

    # Time-series CV
    'use_timeseries_split': True,
    'n_splits': 5,
    'gap': 30,  # Gap between train/test in days

    # Minimum samples per class
    'min_samples_per_class': 50,

    # Feature selection
    'feature_importance_threshold': 0.001,  # Drop features below this
    'max_features': 50,  # Maximum features to use

    # Class weights (for imbalanced data)
    'use_class_weights': True,

    # Validation
    'stratify': True,  # Stratify by target class
}

# Inference configuration
INFERENCE_CONFIG = {
    # Confidence thresholds
    'min_confidence': 0.60,  # Minimum confidence to show prediction
    'high_confidence': 0.75,  # Threshold for "high confidence"

    # Caching
    'cache_ttl': 300,  # 5 minutes

    # Performance
    'max_inference_time_ms': 100,  # Maximum allowed inference time

    # Model versioning
    'model_version': 'latest',  # or specific version like 'v_20260117'
}

# Monitoring configuration
MONITORING_CONFIG = {
    # Accuracy thresholds (for alerts)
    'min_directional_accuracy': 0.50,
    'min_entry_quality_accuracy': 0.55,
    'min_r_mae': 0.8,

    # Drift detection
    'drift_threshold': 0.10,  # 10% change in feature distribution
    'drift_window_days': 30,

    # Retraining triggers
    'retrain_accuracy_drop': 0.05,  # Retrain if accuracy drops by 5%
    'retrain_min_days': 7,  # Minimum days between retrains
}

# Model registry configuration
MODEL_REGISTRY_CONFIG = {
    'base_path': 'ml_models/registry',
    'metadata_file': 'metadata.json',
    'model_file': 'model.txt',  # LightGBM saves as .txt
    'feature_importance_file': 'feature_importance.json',
    'metrics_file': 'metrics.json',
    'predictions_file': 'predictions.parquet',
}


def get_model_config(model_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific model.

    Args:
        model_name: Name of the model (directional, entry_quality, r_multiple)

    Returns:
        Dictionary of model configuration
    """
    configs = {
        'directional': DIRECTIONAL_CLASSIFIER_CONFIG,
        'entry_quality': ENTRY_QUALITY_CONFIG,
        'r_multiple': R_MULTIPLE_CONFIG,
    }

    if model_name not in configs:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(configs.keys())}")

    return configs[model_name].copy()


def get_target_mapping(model_name: str) -> Dict[str, Any]:
    """
    Get target variable mapping for a model.

    Args:
        model_name: Name of the model

    Returns:
        Dictionary with target column and encoding
    """
    mappings = {
        'directional': {
            'target_column': 'orb_break_dir',
            'target_type': 'classification',
            'classes': ['UP', 'DOWN', 'NONE'],
            'class_mapping': {'UP': 0, 'DOWN': 1, 'NONE': 2},
        },
        'entry_quality': {
            'target_column': 'orb_outcome',
            'target_type': 'classification',
            'classes': ['WIN', 'LOSS'],
            'class_mapping': {'WIN': 1, 'LOSS': 0},
            'filter': "orb_break_dir != 'NONE'",  # Only breaks
        },
        'r_multiple': {
            'target_column': 'orb_r_multiple',
            'target_type': 'regression',
            'clip_range': (-2.0, 5.0),  # Clip outliers
        },
    }

    if model_name not in mappings:
        raise ValueError(f"Unknown model: {model_name}")

    return mappings[model_name].copy()


def get_feature_config() -> Dict[str, Any]:
    """
    Get feature engineering configuration.

    Returns:
        Dictionary of feature configuration
    """
    return {
        'categorical_features': ['orb_time', 'instrument', 'session_context', 'asia_type_code', 'london_type_code', 'pre_ny_type_code'],
        'numeric_features': [
            'day_of_week_sin', 'day_of_week_cos', 'orb_hour',
            'pre_asia_range', 'pre_london_range', 'pre_ny_range',
            'asia_range', 'london_range', 'ny_range',
            'atr_14', 'rsi_14',
            'pre_ny_travel', 'pre_orb_travel',
            'orb_size', 'orb_size_pct_atr',
            'asia_range_pct_atr', 'london_range_pct_atr', 'ny_range_pct_atr',
            'asia_to_london_gap', 'london_to_ny_gap',
            'london_asia_range_ratio', 'ny_london_range_ratio',
            'prev_day_avg_r', 'avg_r_last_3d',
        ],
        'drop_features': [
            'date_local',  # Don't use date directly (use day_of_week instead)
            'orb_high', 'orb_low',  # Use orb_size instead
            'orb_break_dir', 'orb_outcome', 'orb_r_multiple',  # Target variables
        ],
    }


# Optuna hyperparameter search spaces (for Phase 4)
OPTUNA_SEARCH_SPACES = {
    'directional': {
        'num_leaves': [15, 31, 63],
        'max_depth': [5, 7, 10],
        'learning_rate': [0.01, 0.05, 0.1],
        'feature_fraction': [0.7, 0.8, 0.9],
        'bagging_fraction': [0.7, 0.8, 0.9],
        'min_child_samples': [10, 20, 30],
        'reg_alpha': [0.0, 0.1, 0.5],
        'reg_lambda': [0.0, 0.1, 0.5],
    },
}


if __name__ == "__main__":
    # Test configurations
    print("Testing model configurations...\n")

    for model_name in ['directional', 'entry_quality', 'r_multiple']:
        print(f"{model_name.upper()} Model:")
        config = get_model_config(model_name)
        print(f"  Type: {config.get('model_type')}")
        print(f"  Objective: {config.get('objective')}")

        target_info = get_target_mapping(model_name)
        print(f"  Target: {target_info['target_column']}")
        print(f"  Type: {target_info['target_type']}")
        if 'classes' in target_info:
            print(f"  Classes: {target_info['classes']}")
        print()

    print("Feature configuration:")
    feature_config = get_feature_config()
    print(f"  Categorical features: {len(feature_config['categorical_features'])}")
    print(f"  Numeric features: {len(feature_config['numeric_features'])}")
    print(f"  Drop features: {len(feature_config['drop_features'])}")
