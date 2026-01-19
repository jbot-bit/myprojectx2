"""
ML System Diagnostic Script

Run this to diagnose ML system issues.
"""

import sys
from pathlib import Path

print("="*60)
print("ML SYSTEM DIAGNOSTIC")
print("="*60)

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "trading_app"))

print("\n[1/6] Checking file structure...")
required_files = [
    "ml_models/registry/directional_v1/LATEST_VERSION.txt",
    "ml_models/registry/directional_v1/v_20260117_023515/model.txt",
    "ml_inference/inference_engine.py",
    "trading_app/config.py",
    "trading_app/strategy_engine.py",
]

all_exist = True
for file_path in required_files:
    full_path = project_root / file_path
    exists = full_path.exists()
    status = "[OK]" if exists else "[MISSING]"
    print(f"  {status} {file_path}")
    if not exists:
        all_exist = False

if not all_exist:
    print("\n[ERROR] Some required files are missing!")
    sys.exit(1)

print("\n[2/6] Checking configuration...")
try:
    from config import ML_ENABLED, ML_SHADOW_MODE
    print(f"  [OK] ML_ENABLED = {ML_ENABLED}")
    print(f"  [OK] ML_SHADOW_MODE = {ML_SHADOW_MODE}")
except Exception as e:
    print(f"  [ERROR] Config import failed: {e}")
    sys.exit(1)

print("\n[3/6] Loading ML engine...")
try:
    from ml_inference.inference_engine import MLInferenceEngine
    engine = MLInferenceEngine()

    if engine.directional_model:
        print(f"  [OK] Model loaded successfully")
        print(f"  [OK] Model type: {engine.directional_metadata['model_type']}")
        print(f"  [OK] Version: {engine.directional_metadata['version']}")
        print(f"  [OK] Features: {len(engine.directional_features)}")
    else:
        print(f"  [ERROR] Model failed to load")
        sys.exit(1)
except Exception as e:
    print(f"  [ERROR] ML engine failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[4/6] Testing prediction...")
try:
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

    prediction = engine.predict_directional_bias(test_features)
    print(f"  [OK] Prediction: {prediction['predicted_direction']}")
    print(f"  [OK] Confidence: {prediction['confidence']:.1%}")
except Exception as e:
    print(f"  [ERROR] Prediction failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[5/6] Testing strategy engine integration...")
try:
    from data_loader import LiveDataLoader
    from strategy_engine import StrategyEngine

    loader = LiveDataLoader("MGC")
    engine_with_ml = StrategyEngine(loader, ml_engine=engine)

    if engine_with_ml.ml_engine:
        print(f"  [OK] Strategy engine has ML engine attached")
    else:
        print(f"  [ERROR] ML engine not attached to strategy engine")
except Exception as e:
    print(f"  [ERROR] Strategy engine integration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n[6/6] Checking database tables...")
try:
    import duckdb
    conn = duckdb.connect("gold.db")

    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]

    if 'ml_predictions' in table_names:
        print(f"  [OK] ml_predictions table exists")
        count = conn.execute("SELECT COUNT(*) FROM ml_predictions").fetchone()[0]
        print(f"  [OK] {count} predictions logged")
    else:
        print(f"  [WARNING] ml_predictions table not found (will be created on first use)")

    if 'ml_performance' in table_names:
        print(f"  [OK] ml_performance table exists")
    else:
        print(f"  [WARNING] ml_performance table not found (will be created on first use)")

    conn.close()
except Exception as e:
    print(f"  [WARNING] Database check failed: {e}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
print("\nSTATUS: [ALL SYSTEMS OPERATIONAL]")
print("\nML system is ready to use!")
print("\nNext steps:")
print("  1. Run: START_TRADING_APP_WITH_ML.bat")
print("  2. Open browser to: http://localhost:8501")
print("  3. Look for '🤖 ML Insights' panel")
print("\n" + "="*60)
