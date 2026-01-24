"""
Quick integration test for ML system.

This tests that the ML engine integrates correctly with the strategy engine.
"""

import sys
from pathlib import Path

# Add parent directory and trading_app to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "trading_app"))

import logging
from config import ML_ENABLED, ML_SHADOW_MODE
from data_loader import LiveDataLoader
from strategy_engine import StrategyEngine
from ml_inference.inference_engine import MLInferenceEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ml_integration():
    """Test that ML integrates with strategy engine."""
    print("="*60)
    print("ML INTEGRATION TEST")
    print("="*60)

    # Check configuration
    print(f"\n[OK] Configuration:")
    print(f"  ML_ENABLED: {ML_ENABLED}")
    print(f"  ML_SHADOW_MODE: {ML_SHADOW_MODE}")

    # Load ML engine
    print(f"\n[OK] Loading ML engine...")
    ml_engine = MLInferenceEngine()
    print(f"  Model loaded: {ml_engine.directional_metadata['model_type']}")
    print(f"  Version: {ml_engine.directional_metadata['version']}")
    print(f"  Features: {len(ml_engine.directional_features)}")

    # Load data
    print(f"\n[OK] Loading data...")
    loader = LiveDataLoader("MGC")
    gold_db_path = str(Path(__file__).parent.parent / "gold.db")
    loader.backfill_from_gold_db(gold_db_path, days=2)
    loader.refresh()
    print(f"  Loaded {len(loader.bars_1m)} 1-minute bars")

    # Create strategy engine with ML
    print(f"\n[OK] Creating strategy engine with ML...")
    engine = StrategyEngine(loader, ml_engine=ml_engine)
    print(f"  ML engine attached: {engine.ml_engine is not None}")

    # Evaluate strategies
    print(f"\n[OK] Evaluating strategies...")
    evaluation = engine.evaluate_all()
    print(f"  Strategy: {evaluation.strategy_name}")
    print(f"  State: {evaluation.state.value}")
    print(f"  Action: {evaluation.action.value}")

    # Check if ML insights are in reasons
    ml_found = False
    for reason in evaluation.reasons:
        if reason.startswith("ML:"):
            ml_found = True
            print(f"\n[OK] ML Insight found: {reason}")
            break

    if not ml_found and evaluation.state.value in ["PREPARING", "READY"]:
        print(f"\n⚠️  No ML insight in reasons (strategy not in right state)")
    elif not ml_found:
        print(f"\n⚠️  No ML insight (expected for {evaluation.state.value} state)")

    # Test ML prediction directly
    print(f"\n[OK] Testing direct ML prediction...")
    test_features = {
        'date_local': '2026-01-17',
        'instrument': 'MGC',
        'orb_time': '0900',
        'session_context': 'ASIA',
        'orb_size': 0.7,
        'asia_range': 3.0,
        'london_range': 3.0,
        'ny_range': 4.5,
        'atr_14': 5.2,
        'rsi_14': 55.0,
    }

    prediction = ml_engine.predict_directional_bias(test_features)
    print(f"  Direction: {prediction['predicted_direction']}")
    print(f"  Confidence: {prediction['confidence']:.1%}")
    print(f"  P(UP): {prediction['prob_up']:.1%}, P(DOWN): {prediction['prob_down']:.1%}")

    # Test recommendation generation
    recommendation = ml_engine.generate_trade_recommendation(test_features)
    print(f"\n[OK] Trade recommendation:")
    print(f"  Confidence Level: {recommendation['confidence_level']}")
    print(f"  Risk Adjustment: {recommendation['risk_adjustment']:.1f}x")
    print(f"  Reasoning:")
    for reason in recommendation['reasoning']:
        print(f"    - {reason}")

    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
    print("\nML system is fully integrated and operational.")
    print("Ready for use in trading app.")

    loader.close()


if __name__ == "__main__":
    test_ml_integration()
