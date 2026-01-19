"""
ML Training Pipeline

This script trains ML models for the trading system.

Usage:
    python ml_training/train_pipeline.py --model directional
    python ml_training/train_pipeline.py --model entry_quality
    python ml_training/train_pipeline.py --model r_multiple

The trained model will be saved to ml_models/registry/{model_name}_v1/
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Any

import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    mean_absolute_error, mean_squared_error, r2_score
)
from sklearn.preprocessing import LabelEncoder
import joblib

from ml_training.model_configs import (
    get_model_config, get_target_mapping, get_feature_config,
    TRAINING_CONFIG, MODEL_REGISTRY_CONFIG
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLTrainingPipeline:
    """Main training pipeline for ML models."""

    def __init__(self, model_name: str):
        """
        Initialize training pipeline.

        Args:
            model_name: Name of model to train (directional, entry_quality, r_multiple)
        """
        self.model_name = model_name
        self.model_config = get_model_config(model_name)
        self.target_info = get_target_mapping(model_name)
        self.feature_config = get_feature_config()

        self.model = None
        self.label_encoders = {}
        self.feature_names = []
        self.metrics = {}

        logger.info(f"Initialized training pipeline for {model_name}")

    def load_data(self, data_path: str = "ml_data/historical_features.parquet") -> pd.DataFrame:
        """Load training data from Parquet file."""
        logger.info(f"Loading data from {data_path}...")

        df = pd.read_parquet(data_path)
        logger.info(f"Loaded {len(df)} samples")

        # Apply filters if specified
        if 'filter' in self.target_info:
            filter_expr = self.target_info['filter']
            logger.info(f"Applying filter: {filter_expr}")
            df = df.query(filter_expr)
            logger.info(f"After filtering: {len(df)} samples")

        return df

    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features and target for training.

        Returns:
            X: Feature DataFrame
            y: Target Series
        """
        logger.info("Preparing features and target...")

        # Get target
        target_col = self.target_info['target_column']
        y = df[target_col].copy()

        # Remove rows with missing target
        valid_mask = y.notna()
        df = df[valid_mask].copy()
        y = y[valid_mask].copy()

        logger.info(f"Samples with valid target: {len(df)}")

        # Select features
        drop_cols = self.feature_config['drop_features'] + [target_col]

        # Also drop other target columns
        for col in ['orb_break_dir', 'orb_outcome', 'orb_r_multiple']:
            if col != target_col and col in df.columns:
                drop_cols.append(col)

        # Get available feature columns
        feature_cols = [col for col in df.columns if col not in drop_cols]

        X = df[feature_cols].copy()

        logger.info(f"Feature columns: {len(feature_cols)}")
        logger.info(f"Features: {feature_cols[:10]}...")  # Show first 10

        # Encode categorical features
        for cat_col in self.feature_config['categorical_features']:
            if cat_col in X.columns:
                logger.info(f"Encoding categorical feature: {cat_col}")
                le = LabelEncoder()
                X[cat_col] = le.fit_transform(X[cat_col].astype(str))
                self.label_encoders[cat_col] = le

        # Encode target if classification
        if self.target_info['target_type'] == 'classification':
            logger.info("Encoding target labels...")
            if 'class_mapping' in self.target_info:
                # Use predefined mapping
                y = y.map(self.target_info['class_mapping'])
            else:
                # Auto-encode
                le = LabelEncoder()
                y = pd.Series(le.fit_transform(y), index=y.index)
                self.label_encoders['target'] = le

            logger.info(f"Target distribution:\n{y.value_counts()}")

        # Clip target if regression
        elif self.target_info['target_type'] == 'regression':
            if 'clip_range' in self.target_info:
                clip_min, clip_max = self.target_info['clip_range']
                y = y.clip(clip_min, clip_max)
                logger.info(f"Clipped target to [{clip_min}, {clip_max}]")

        # Fill missing values
        X = X.fillna(0)

        # Store feature names
        self.feature_names = X.columns.tolist()

        return X, y

    def split_data(
        self, X: pd.DataFrame, y: pd.Series, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
        """
        Split data into train/val/test sets using time-series split.

        Args:
            X: Features
            y: Target
            df: Original DataFrame (for date column)

        Returns:
            X_train, X_val, X_test, y_train, y_val, y_test
        """
        logger.info("Splitting data...")

        # Get dates for time-based split
        dates = pd.to_datetime(df['date_local'].loc[X.index])

        # Sort by date
        sort_idx = dates.argsort()
        X = X.iloc[sort_idx]
        y = y.iloc[sort_idx]
        dates = dates.iloc[sort_idx]

        # Calculate split indices
        n = len(X)
        train_end = int(n * TRAINING_CONFIG['train_split'])
        val_end = int(n * (TRAINING_CONFIG['train_split'] + TRAINING_CONFIG['val_split']))

        # Split
        X_train = X.iloc[:train_end]
        y_train = y.iloc[:train_end]

        X_val = X.iloc[train_end:val_end]
        y_val = y.iloc[train_end:val_end]

        X_test = X.iloc[val_end:]
        y_test = y.iloc[val_end:]

        logger.info(f"Train: {len(X_train)} samples ({dates.iloc[:train_end].min()} to {dates.iloc[train_end-1]})")
        logger.info(f"Val: {len(X_val)} samples ({dates.iloc[train_end]} to {dates.iloc[val_end-1]})")
        logger.info(f"Test: {len(X_test)} samples ({dates.iloc[val_end]} to {dates.iloc[-1]})")

        return X_train, X_val, X_test, y_train, y_val, y_test

    def train_model(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series
    ):
        """Train the model."""
        logger.info(f"Training {self.model_config['model_type']} model...")

        model_type = self.model_config['model_type']

        if model_type == 'lightgbm':
            self.model = self._train_lightgbm(X_train, y_train, X_val, y_val)
        elif model_type == 'xgboost':
            self.model = self._train_xgboost(X_train, y_train, X_val, y_val)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        logger.info("Training complete!")

    def _train_lightgbm(
        self, X_train, y_train, X_val, y_val
    ) -> lgb.Booster:
        """Train LightGBM model."""
        # Compute class weights for balanced training
        class_weights = None
        if TRAINING_CONFIG.get('use_class_weights', True):
            from sklearn.utils.class_weight import compute_class_weight

            classes = np.unique(y_train)
            weights = compute_class_weight('balanced', classes=classes, y=y_train)

            # Create weight array for each sample
            sample_weights = np.ones(len(y_train))
            for i, cls in enumerate(classes):
                sample_weights[y_train == cls] = weights[i]

            logger.info(f"Using class weights: {dict(zip(classes, weights))}")
            class_weights = sample_weights

        # Prepare datasets
        train_data = lgb.Dataset(X_train, label=y_train, weight=class_weights)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Extract training params
        params = {k: v for k, v in self.model_config.items()
                  if k not in ['n_estimators', 'early_stopping_rounds', 'model_type']}

        # Train
        model = lgb.train(
            params,
            train_data,
            num_boost_round=self.model_config.get('n_estimators', 500),
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            callbacks=[
                lgb.early_stopping(self.model_config.get('early_stopping_rounds', 50)),
                lgb.log_evaluation(period=50)
            ]
        )

        return model

    def _train_xgboost(
        self, X_train, y_train, X_val, y_val
    ) -> xgb.Booster:
        """Train XGBoost model."""
        # Prepare DMatrix
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)

        # Extract training params
        params = {k: v for k, v in self.model_config.items()
                  if k not in ['n_estimators', 'early_stopping_rounds', 'model_type']}

        # Train
        evals = [(dtrain, 'train'), (dval, 'val')]
        model = xgb.train(
            params,
            dtrain,
            num_boost_round=self.model_config.get('n_estimators', 300),
            evals=evals,
            early_stopping_rounds=self.model_config.get('early_stopping_rounds', 50),
            verbose_eval=50
        )

        return model

    def evaluate_model(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ) -> Dict[str, Any]:
        """Evaluate model on test set."""
        logger.info("Evaluating model on test set...")

        # Make predictions
        if self.model_config['model_type'] == 'lightgbm':
            y_pred_proba = self.model.predict(X_test)
            if self.target_info['target_type'] == 'classification':
                y_pred = np.argmax(y_pred_proba, axis=1)
            else:
                y_pred = y_pred_proba

        elif self.model_config['model_type'] == 'xgboost':
            dtest = xgb.DMatrix(X_test)
            if self.target_info['target_type'] == 'classification':
                y_pred_proba = self.model.predict(dtest)
                if self.target_info.get('num_class', 2) == 2:
                    y_pred = (y_pred_proba > 0.5).astype(int)
                else:
                    y_pred = y_pred_proba  # XGBoost already returns class
            else:
                y_pred = self.model.predict(dtest)

        metrics = {}

        # Classification metrics
        if self.target_info['target_type'] == 'classification':
            accuracy = accuracy_score(y_test, y_pred)
            metrics['accuracy'] = float(accuracy)

            logger.info(f"Test Accuracy: {accuracy:.4f}")

            # Classification report
            if 'classes' in self.target_info:
                # Get unique labels present in test set
                unique_labels = sorted(np.unique(np.concatenate([y_test, y_pred])))
                class_names = [self.target_info['classes'][i] for i in unique_labels]

                report = classification_report(
                    y_test, y_pred,
                    labels=unique_labels,
                    target_names=class_names,
                    zero_division=0
                )
                logger.info(f"\nClassification Report:\n{report}")

                # Confusion matrix
                cm = confusion_matrix(y_test, y_pred, labels=unique_labels)
                logger.info(f"\nConfusion Matrix:\n{cm}")
                logger.info(f"Labels: {class_names}")

                metrics['classification_report'] = report
                metrics['confusion_matrix'] = cm.tolist()
                metrics['class_labels'] = class_names

        # Regression metrics
        else:
            mae = mean_absolute_error(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)

            metrics['mae'] = float(mae)
            metrics['mse'] = float(mse)
            metrics['rmse'] = float(rmse)
            metrics['r2'] = float(r2)

            logger.info(f"Test MAE: {mae:.4f}")
            logger.info(f"Test RMSE: {rmse:.4f}")
            logger.info(f"Test R²: {r2:.4f}")

        self.metrics = metrics
        return metrics

    def save_model(self, version: str = None):
        """Save model to registry."""
        if version is None:
            version = datetime.now().strftime("v_%Y%m%d_%H%M%S")

        # Create model directory
        model_dir = Path(MODEL_REGISTRY_CONFIG['base_path']) / f"{self.model_name}_v1" / version
        model_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Saving model to {model_dir}...")

        # Save model
        model_path = model_dir / MODEL_REGISTRY_CONFIG['model_file']
        if self.model_config['model_type'] == 'lightgbm':
            self.model.save_model(str(model_path))
        elif self.model_config['model_type'] == 'xgboost':
            self.model.save_model(str(model_path))

        # Save label encoders
        encoders_path = model_dir / "label_encoders.pkl"
        joblib.dump(self.label_encoders, encoders_path)

        # Save feature names
        features_path = model_dir / "feature_names.json"
        with open(features_path, 'w') as f:
            json.dump(self.feature_names, f, indent=2)

        # Save feature importance
        if hasattr(self.model, 'feature_importance'):
            importance = self.model.feature_importance()
            importance_dict = dict(zip(self.feature_names, importance.tolist()))
            # Sort by importance
            importance_dict = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

            importance_path = model_dir / MODEL_REGISTRY_CONFIG['feature_importance_file']
            with open(importance_path, 'w') as f:
                json.dump(importance_dict, f, indent=2)

            # Log top features
            logger.info("\nTop 10 Features:")
            for i, (feat, imp) in enumerate(list(importance_dict.items())[:10], 1):
                logger.info(f"  {i}. {feat}: {imp:.1f}")

        # Save metrics
        metrics_path = model_dir / MODEL_REGISTRY_CONFIG['metrics_file']
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)

        # Save metadata
        metadata = {
            'model_name': self.model_name,
            'model_type': self.model_config['model_type'],
            'version': version,
            'created_at': datetime.now().isoformat(),
            'target_info': self.target_info,
            'feature_count': len(self.feature_names),
            'metrics': self.metrics,
        }

        metadata_path = model_dir / MODEL_REGISTRY_CONFIG['metadata_file']
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Create "latest" symlink
        latest_link = model_dir.parent / "latest"
        if latest_link.exists():
            if latest_link.is_symlink():
                latest_link.unlink()
            else:
                logger.warning(f"'latest' exists but is not a symlink: {latest_link}")

        # Create symlink (Windows: requires admin or developer mode)
        try:
            latest_link.symlink_to(version, target_is_directory=True)
            logger.info(f"Updated 'latest' symlink to {version}")
        except OSError as e:
            logger.warning(f"Could not create symlink (this is OK on Windows): {e}")
            # Create a marker file instead
            marker_file = model_dir.parent / "LATEST_VERSION.txt"
            with open(marker_file, 'w') as f:
                f.write(version)
            logger.info(f"Created marker file: {marker_file}")

        logger.info(f"✓ Model saved to {model_dir}")

        return model_dir

    def run(self):
        """Run the full training pipeline."""
        logger.info("="*60)
        logger.info(f"TRAINING {self.model_name.upper()} MODEL")
        logger.info("="*60)

        # Load data
        df = self.load_data()

        # Prepare features
        X, y = self.prepare_features(df)

        # Split data
        X_train, X_val, X_test, y_train, y_val, y_test = self.split_data(X, y, df)

        # Train model
        self.train_model(X_train, y_train, X_val, y_val)

        # Evaluate model
        self.evaluate_model(X_test, y_test)

        # Save model
        model_dir = self.save_model()

        logger.info("\n" + "="*60)
        logger.info("TRAINING COMPLETE!")
        logger.info("="*60)
        logger.info(f"Model saved to: {model_dir}")

        return model_dir


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Train ML models for trading system')
    parser.add_argument(
        '--model',
        type=str,
        required=True,
        choices=['directional', 'entry_quality', 'r_multiple'],
        help='Model to train'
    )
    parser.add_argument(
        '--data',
        type=str,
        default='ml_data/historical_features.parquet',
        help='Path to training data'
    )

    args = parser.parse_args()

    # Run training pipeline
    pipeline = MLTrainingPipeline(args.model)
    pipeline.run()


if __name__ == "__main__":
    main()
