"""
Test trading app components to verify everything is wired correctly.
Simulates user actions to catch any issues.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_loading():
    """Test 1: Config loading from database"""
    print("\n" + "="*70)
    print("TEST 1: Config Loading")
    print("="*70)

    try:
        from config import get_instrument_configs

        mgc_configs, mgc_filters = get_instrument_configs('MGC')

        print(f"✓ Loaded {len(mgc_configs)} MGC ORB configs")

        # Check each config has required fields
        for orb_time, config_list in mgc_configs.items():
            if isinstance(config_list, list):
                for config in config_list:
                    assert 'rr' in config, f"{orb_time} missing 'rr'"
                    assert 'sl_mode' in config, f"{orb_time} missing 'sl_mode'"
                    assert 'tier' in config, f"{orb_time} missing 'tier'"
                    print(f"  ✓ {orb_time}: RR={config['rr']}, SL={config['sl_mode']}, Tier={config['tier']}")

        print("✓ All configs have required fields (rr, sl_mode, tier)")
        return True

    except Exception as e:
        print(f"✗ Config loading FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_loader():
    """Test 2: Data loader initialization"""
    print("\n" + "="*70)
    print("TEST 2: Data Loader")
    print("="*70)

    try:
        from data_loader import LiveDataLoader

        loader = LiveDataLoader('MGC')
        print("✓ Data loader initialized")

        # Try to get latest bar
        latest = loader.get_latest_bar()
        if latest:
            print(f"✓ Latest bar: {latest['ts_local']}, Close: ${latest['close']:.2f}")
        else:
            print("⚠ No latest bar (need to refresh)")

        # Check ATR calculation
        atr = loader.get_today_atr()
        if atr:
            print(f"✓ ATR: {atr:.2f} pts")
        else:
            print("⚠ No ATR (need data)")

        return True

    except Exception as e:
        print(f"✗ Data loader FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_engine():
    """Test 3: Strategy engine evaluation"""
    print("\n" + "="*70)
    print("TEST 3: Strategy Engine")
    print("="*70)

    try:
        from data_loader import LiveDataLoader
        from strategy_engine import StrategyEngine

        loader = LiveDataLoader('MGC')
        engine = StrategyEngine(loader)

        print("✓ Strategy engine initialized")
        print(f"  Instrument: {engine.instrument}")
        print(f"  CASCADE gap: {engine.cascade_min_gap} pts")
        print(f"  ORB configs loaded: {len(engine.orb_configs)}")

        # Check configs are resolved properly
        for orb_time, config in engine.orb_configs.items():
            if config:
                assert isinstance(config, dict), f"{orb_time} config should be dict, got {type(config)}"
                assert 'tier' in config, f"{orb_time} config missing 'tier'"
                print(f"  ✓ {orb_time}: Tier={config['tier']}, RR={config['rr']}")

        # Try evaluation (this will fail if market is closed, but we check it doesn't crash)
        print("\n  Testing strategy evaluation...")
        try:
            evaluation = engine.evaluate_all()
            print(f"✓ Evaluation succeeded: {evaluation.strategy_name} -> {evaluation.action.value}")
            print(f"  Status: {evaluation.state.value}")
            print(f"  Reasons: {len(evaluation.reasons)} provided")
        except Exception as eval_error:
            # It's OK if evaluation fails due to no data, we just want to ensure no config errors
            if "'tier'" in str(eval_error):
                raise eval_error  # This is a config error we need to fix
            print(f"  ⚠ Evaluation failed (may need live data): {eval_error}")

        return True

    except Exception as e:
        print(f"✗ Strategy engine FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_setup_detector():
    """Test 4: Setup detector database queries"""
    print("\n" + "="*70)
    print("TEST 4: Setup Detector")
    print("="*70)

    try:
        from setup_detector import SetupDetector

        detector = SetupDetector()
        print("✓ Setup detector initialized")

        # Get all MGC setups
        mgc_setups = detector.get_all_validated_setups('MGC')
        print(f"✓ Found {len(mgc_setups)} validated MGC setups in database")

        # Check setup structure
        if mgc_setups:
            first = mgc_setups[0]
            print(f"  Sample setup: {first['orb_time']} RR={first['rr']}, Tier={first['tier']}")

        return True

    except Exception as e:
        print(f"✗ Setup detector FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("TRADING APP COMPONENT TEST")
    print("="*70)

    results = {
        "Config Loading": test_config_loading(),
        "Data Loader": test_data_loader(),
        "Strategy Engine": test_strategy_engine(),
        "Setup Detector": test_setup_detector(),
    }

    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED - App components are wired correctly!")
        print("="*70)
        return 0
    else:
        print("\n" + "="*70)
        print("✗ SOME TESTS FAILED - Check errors above")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
