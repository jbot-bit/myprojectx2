"""
ML Inference Engine

This module provides real-time ML predictions for the trading system.

Usage:
    from ml_inference.inference_engine import MLInferenceEngine

    engine = MLInferenceEngine()
    prediction = engine.predict_directional_bias(features)
    recommendation = engine.generate_trade_recommendation(features)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json
import time

import numpy as np
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
import joblib
import sys

# Add parent directory to path for imports
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_training.model_configs import INFERENCE_CONFIG, MODEL_REGISTRY_CONFIG
from ml_training.feature_engineering import engineer_all_features, get_feature_columns

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelLoader:
    """Utility class for loading models from the registry."""

    @staticmethod
    def load_model(model_name: str, version: str = 'latest') -> Tuple[Any, Dict[str, Any], list]:
        """
        Load a model from the registry.

        Args:
            model_name: Name of the model (e.g., 'directional_v1')
            version: Version to load ('latest' or specific version like 'v_20260117_022937')

        Returns:
            Tuple of (model, metadata, feature_names)
        """
        # Resolve path relative to this file's location (ml_inference/)
        # Project structure: myprojectx/ml_inference/inference_engine.py
        # Models are at: myprojectx/ml_models/registry/
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        base_path = project_root / MODEL_REGISTRY_CONFIG['base_path'] / model_name

        # Resolve version
        if version == 'latest':
            # Check for marker file first (Windows compatibility)
            marker_file = base_path / "LATEST_VERSION.txt"
            if marker_file.exists():
                version = marker_file.read_text().strip()
            else:
                # Try symlink
                latest_link = base_path / "latest"
                if latest_link.exists():
                    version = latest_link.readlink().name
                else:
                    # Get most recent version
                    versions = sorted([d for d in base_path.iterdir() if d.is_dir()])
                    if not versions:
                        raise FileNotFoundError(f"No models found for {model_name}")
                    version = versions[-1].name

        model_dir = base_path / version

        if not model_dir.exists():
            raise FileNotFoundError(f"Model not found: {model_dir}")

        logger.info(f"Loading model from {model_dir}")

        # Load model
        model_file = model_dir / MODEL_REGISTRY_CONFIG['model_file']
        metadata_file = model_dir / MODEL_REGISTRY_CONFIG['metadata_file']
        features_file = model_dir / "feature_names.json"
        encoders_file = model_dir / "label_encoders.pkl"

        # Load metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        model_type = metadata.get('model_type', 'lightgbm')

        # Load model based on type
        if model_type == 'lightgbm':
            model = lgb.Booster(model_file=str(model_file))
        elif model_type == 'xgboost':
            model = xgb.Booster()
            model.load_model(str(model_file))
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        # Load feature names
        with open(features_file, 'r') as f:
            feature_names = json.load(f)

        # Load label encoders
        label_encoders = None
        if encoders_file.exists():
            label_encoders = joblib.load(encoders_file)

        metadata['label_encoders'] = label_encoders
        metadata['model_type'] = model_type

        logger.info(f"Loaded {model_type} model (version: {version})")
        logger.info(f"Features: {len(feature_names)}")

        return model, metadata, feature_names


class MLInferenceEngine:
    """
    Main ML inference engine for real-time predictions.

    This class provides methods for:
    - Directional bias prediction
    - Entry quality scoring
    - R-multiple prediction
    - Trade recommendations with explanations
    """

    def __init__(self, use_cache: bool = True):
        """
        Initialize the inference engine.

        Args:
            use_cache: Whether to use prediction caching
        """
        self.use_cache = use_cache
        self.cache = {} if use_cache else None
        self.cache_ttl = INFERENCE_CONFIG.get('cache_ttl', 300)  # 5 minutes

        # Load models
        self.directional_model = None
        self.directional_metadata = None
        self.directional_features = None

        self._load_directional_model()

        logger.info("ML Inference Engine initialized")

    def _load_directional_model(self):
        """Load the directional classifier model."""
        try:
            self.directional_model, self.directional_metadata, self.directional_features = (
                ModelLoader.load_model('directional_v1', version='latest')
            )
            logger.info("Directional model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load directional model: {e}")
            self.directional_model = None

    def _prepare_features(self, features: Dict[str, Any], feature_names: list) -> pd.DataFrame:
        """
        Prepare features for model input.

        Args:
            features: Dictionary of features
            feature_names: List of feature names expected by model

        Returns:
            DataFrame ready for prediction
        """
        # Engineer features from raw inputs
        engineered = engineer_all_features(features)

        # Create DataFrame with model's expected features
        feature_dict = {}
        for feat in feature_names:
            if feat in engineered:
                feature_dict[feat] = engineered[feat]
            else:
                # Missing feature - use default
                feature_dict[feat] = 0

        df = pd.DataFrame([feature_dict])

        # Encode categorical features using saved encoders
        if 'label_encoders' in self.directional_metadata:
            encoders = self.directional_metadata['label_encoders']
            for col, encoder in encoders.items():
                if col in df.columns and col != 'target':
                    try:
                        df[col] = encoder.transform(df[col].astype(str))
                    except ValueError:
                        # Unknown category - use most frequent
                        df[col] = 0

        # Fill missing values
        df = df.fillna(0)

        return df

    def predict_directional_bias(
        self, features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Predict directional bias (UP/DOWN/NONE).

        Args:
            features: Dictionary of features (from data_loader or similar)

        Returns:
            Dictionary with:
                - prob_up: Probability of UP break
                - prob_down: Probability of DOWN break
                - prob_none: Probability of no break
                - predicted_direction: Most likely direction
                - confidence: Confidence in prediction (max probability)
        """
        if self.directional_model is None:
            logger.warning("Directional model not loaded")
            return {
                'prob_up': 0.33,
                'prob_down': 0.33,
                'prob_none': 0.34,
                'predicted_direction': 'UNKNOWN',
                'confidence': 0.34
            }

        start_time = time.time()

        # Check cache
        cache_key = str(sorted(features.items()))
        if self.use_cache and cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if time.time() - cache_entry['timestamp'] < self.cache_ttl:
                logger.debug("Using cached prediction")
                return cache_entry['result']

        # Prepare features
        X = self._prepare_features(features, self.directional_features)

        # Make prediction
        if self.directional_metadata['model_type'] == 'lightgbm':
            proba = self.directional_model.predict(X)
        elif self.directional_metadata['model_type'] == 'xgboost':
            dmatrix = xgb.DMatrix(X)
            proba = self.directional_model.predict(dmatrix)

        # Parse probabilities
        # Note: Model was trained with class mapping: UP=0, DOWN=1, NONE=2
        # But NONE class might not be in predictions
        if proba.ndim == 1:
            # Binary classification (UP vs DOWN)
            prob_up = float(proba[0])
            prob_down = 1.0 - prob_up
            prob_none = 0.0
        else:
            # Multi-class classification
            prob_up = float(proba[0][0]) if len(proba[0]) > 0 else 0.33
            prob_down = float(proba[0][1]) if len(proba[0]) > 1 else 0.33
            prob_none = float(proba[0][2]) if len(proba[0]) > 2 else 0.34

        # Determine predicted direction
        max_prob = max(prob_up, prob_down, prob_none)
        if max_prob == prob_up:
            predicted_direction = 'UP'
        elif max_prob == prob_down:
            predicted_direction = 'DOWN'
        else:
            predicted_direction = 'NONE'

        result = {
            'prob_up': prob_up,
            'prob_down': prob_down,
            'prob_none': prob_none,
            'predicted_direction': predicted_direction,
            'confidence': max_prob
        }

        # Cache result
        if self.use_cache:
            self.cache[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }

        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Prediction completed in {elapsed_ms:.1f}ms")

        return result

    def generate_trade_recommendation(
        self, features: Dict[str, Any], rule_evaluation: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive trade recommendation with ML insights.

        Args:
            features: Dictionary of features
            rule_evaluation: Optional rule-based evaluation from StrategyEngine

        Returns:
            Dictionary with:
                - ml_prediction: Directional bias prediction
                - confidence_level: 'HIGH', 'MEDIUM', 'LOW'
                - reasoning: List of explanation bullets
                - risk_adjustment: Suggested risk multiplier (0.5x to 1.5x)
                - agree_with_rules: Whether ML agrees with rule-based system
        """
        # Get directional prediction
        ml_pred = self.predict_directional_bias(features)

        # Determine confidence level
        confidence = ml_pred['confidence']
        if confidence >= INFERENCE_CONFIG.get('high_confidence', 0.75):
            confidence_level = 'HIGH'
            risk_adjustment = 1.2
        elif confidence >= INFERENCE_CONFIG.get('min_confidence', 0.60):
            confidence_level = 'MEDIUM'
            risk_adjustment = 1.0
        else:
            confidence_level = 'LOW'
            risk_adjustment = 0.7

        # Generate reasoning
        reasoning = self._generate_reasoning(ml_pred, features)

        # Check agreement with rules
        agree_with_rules = None
        if rule_evaluation:
            rule_direction = rule_evaluation.get('direction', 'UNKNOWN')
            if rule_direction in ['LONG', 'SHORT']:
                ml_direction = ml_pred['predicted_direction']
                if (rule_direction == 'LONG' and ml_direction == 'UP') or \
                   (rule_direction == 'SHORT' and ml_direction == 'DOWN'):
                    agree_with_rules = True
                else:
                    agree_with_rules = False

        recommendation = {
            'ml_prediction': ml_pred,
            'confidence_level': confidence_level,
            'reasoning': reasoning,
            'risk_adjustment': risk_adjustment,
            'agree_with_rules': agree_with_rules
        }

        return recommendation

    def _generate_reasoning(self, prediction: Dict[str, float], features: Dict[str, Any]) -> list:
        """
        Generate human-readable reasoning for the prediction.

        Args:
            prediction: ML prediction dictionary
            features: Input features

        Returns:
            List of reasoning bullets
        """
        reasoning = []

        # Main prediction
        direction = prediction['predicted_direction']
        confidence = prediction['confidence'] * 100

        reasoning.append(
            f"ML predicts {direction} with {confidence:.1f}% confidence"
        )

        # Feature-based reasoning
        orb_size = features.get('orb_size', 0)
        atr = features.get('atr_14', 0)
        if atr > 0:
            orb_size_pct = (orb_size / atr) * 100
            if orb_size_pct < 10:
                reasoning.append(f"Small ORB ({orb_size_pct:.1f}% of ATR) - tight range")
            elif orb_size_pct > 30:
                reasoning.append(f"Large ORB ({orb_size_pct:.1f}% of ATR) - wide range")

        # Session analysis
        session_context = features.get('session_context', 'UNKNOWN')
        reasoning.append(f"Trading in {session_context} session")

        # RSI analysis
        rsi = features.get('rsi_14', 50)
        if rsi < 30:
            reasoning.append(f"RSI oversold ({rsi:.1f}) - potential reversal")
        elif rsi > 70:
            reasoning.append(f"RSI overbought ({rsi:.1f}) - potential reversal")

        return reasoning

    def clear_cache(self):
        """Clear the prediction cache."""
        if self.cache:
            self.cache.clear()
            logger.info("Prediction cache cleared")


# Singleton instance for easy import
_engine_instance = None


def get_inference_engine() -> MLInferenceEngine:
    """Get the singleton inference engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MLInferenceEngine()
    return _engine_instance


# For testing
if __name__ == "__main__":
    # Example usage
    sample_features = {
        'date_local': '2026-01-17',
        'instrument': 'MGC',
        'orb_time': '0900',
        'orb_size': 0.7,
        'asia_range': 3.0,
        'london_range': 3.0,
        'ny_range': 4.5,
        'atr_14': 5.2,
        'rsi_14': 55.0,
        'pre_asia_range': 2.8,
        'pre_london_range': 3.1,
        'pre_ny_range': 4.0,
        'session_context': 'ASIA',
    }

    print("Initializing ML Inference Engine...")
    engine = MLInferenceEngine()

    print("\nMaking prediction...")
    prediction = engine.predict_directional_bias(sample_features)

    print("\nPrediction:")
    print(f"  Direction: {prediction['predicted_direction']}")
    print(f"  Confidence: {prediction['confidence']:.1%}")
    print(f"  P(UP): {prediction['prob_up']:.1%}")
    print(f"  P(DOWN): {prediction['prob_down']:.1%}")

    print("\nGenerating recommendation...")
    recommendation = engine.generate_trade_recommendation(sample_features)

    print("\nRecommendation:")
    print(f"  Confidence Level: {recommendation['confidence_level']}")
    print(f"  Risk Adjustment: {recommendation['risk_adjustment']:.1f}x")
    print("\n  Reasoning:")
    for reason in recommendation['reasoning']:
        print(f"    - {reason}")
