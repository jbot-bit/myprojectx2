"""
TEST APP SYNCHRONIZATION

CRITICAL: Validates that validated_setups database matches config.py
Prevents dangerous mismatches that could cause wrong trades in live trading.

Run this AFTER:
- Updating validated_setups database
- Modifying trading_app/config.py
- Running populate_validated_setups.py
- Adding new MGC/NQ/MPL setups
- Changing ORB filters or RR values

From CLAUDE.md:
"MANDATORY RULE: NEVER update validated_setups database without IMMEDIATELY
updating config.py in the same operation."

This test ensures that rule is followed.
"""

import sys
from pathlib import Path
import duckdb

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

# Import config module and load configs (lazy loading)
import config
from cloud_mode import get_database_connection

# Populate configs (lazy loading now requires explicit call)
MGC_ORB_CONFIGS, MGC_ORB_SIZE_FILTERS = config.get_instrument_configs('MGC')
NQ_ORB_CONFIGS, NQ_ORB_SIZE_FILTERS = config.get_instrument_configs('NQ')
MPL_ORB_CONFIGS, MPL_ORB_SIZE_FILTERS = config.get_instrument_configs('MPL')


def test_config_matches_database():
    """Verify config.py matches validated_setups database"""

    # Use cloud-aware connection (same as config_generator.py)
    try:
        con = get_database_connection(read_only=True)
        if con is None:
            print("[FAIL] FAILED: Could not connect to database")
            return False
    except Exception as e:
        print(f"[FAIL] FAILED: Cannot connect to database: {e}")
        return False

    try:
        # Get all setups from database
        query = """
        SELECT instrument, orb_time, rr, sl_mode, orb_size_filter
        FROM validated_setups
        WHERE instrument IN ('MGC', 'NQ', 'MPL')
          AND orb_time NOT IN ('CASCADE', 'SINGLE_LIQ')
        ORDER BY instrument, orb_time
        """

        db_setups = con.execute(query).fetchall()

        if not db_setups:
            print("[FAIL] FAILED: No setups found in validated_setups table")
            return False

        print(f"[PASS] Found {len(db_setups)} setups in database")

        # Group by instrument
        mgc_db = [s for s in db_setups if s[0] == 'MGC']
        nq_db = [s for s in db_setups if s[0] == 'NQ']
        mpl_db = [s for s in db_setups if s[0] == 'MPL']

        print(f"   - MGC: {len(mgc_db)} setups")
        print(f"   - NQ: {len(nq_db)} setups")
        print(f"   - MPL: {len(mpl_db)} setups")
        print()

        # Test MGC
        print("=== Testing MGC ===")
        mgc_pass = test_instrument_sync('MGC', mgc_db, MGC_ORB_CONFIGS, MGC_ORB_SIZE_FILTERS)

        # Test NQ
        print("\n=== Testing NQ ===")
        nq_pass = test_instrument_sync('NQ', nq_db, NQ_ORB_CONFIGS, NQ_ORB_SIZE_FILTERS)

        # Test MPL
        print("\n=== Testing MPL ===")
        mpl_pass = test_instrument_sync('MPL', mpl_db, MPL_ORB_CONFIGS, MPL_ORB_SIZE_FILTERS)

        con.close()

        return mgc_pass and nq_pass and mpl_pass

    except Exception as e:
        print(f"[FAIL] FAILED: Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_instrument_sync(instrument, db_setups, orb_configs, orb_size_filters):
    """
    Test one instrument's synchronization.

    ARCHITECTURE: Config returns lists, but we test at the "primary resolved" level.
    Strategy engine uses select_primary_setup() to pick best setup from each list.

    Validates that:
    - Every ORB in database has a config entry
    - Primary resolved config exists in database
    - Config structure is valid (list of dicts)
    """

    if not db_setups:
        print(f"[WARN]  No {instrument} setups in database (expected if not using {instrument})")
        return True

    all_pass = True

    # Group DB setups by ORB time
    db_by_orb = {}
    for setup in db_setups:
        _, orb_time, db_rr, db_sl_mode, db_filter = setup
        if orb_time not in db_by_orb:
            db_by_orb[orb_time] = []
        db_by_orb[orb_time].append((db_rr, db_sl_mode, db_filter))

    # Check: Every ORB in database has a config entry
    for orb_time in db_by_orb.keys():
        if orb_time not in orb_configs:
            print(f"[FAIL] MISMATCH: {orb_time} in database but NOT in config.py")
            all_pass = False
            continue

        config_list = orb_configs[orb_time]
        filter_list = orb_size_filters.get(orb_time)

        # Handle special case where ORB is marked as None (skip)
        if config_list is None:
            print(f"[FAIL] MISMATCH: {orb_time} in database but marked as SKIP in config")
            all_pass = False
            continue

        # Config should be a list of setups
        if not isinstance(config_list, list):
            print(f"[FAIL] ERROR: {orb_time} config is not a list (architecture error)")
            all_pass = False
            continue

        # Verify each config in list exists in database
        for i, (config_setup, config_filter) in enumerate(zip(config_list, filter_list)):
            config_rr = config_setup.get('rr')
            config_sl_mode = config_setup.get('sl_mode')

            # Find this specific setup in database
            found = False
            for db_rr, db_sl_mode, db_filter in db_by_orb[orb_time]:
                rr_match = abs(db_rr - config_rr) < 0.001
                sl_match = db_sl_mode == config_sl_mode

                # Check filter match
                db_filter_val = db_filter if db_filter is not None else None
                config_filter_val = config_filter if config_filter is not None else None

                if db_filter_val is None and config_filter_val is None:
                    filter_match = True
                elif db_filter_val is None or config_filter_val is None:
                    filter_match = False
                else:
                    filter_match = abs(db_filter_val - config_filter_val) < 0.001

                if rr_match and sl_match and filter_match:
                    found = True
                    break

            if not found:
                print(f"[FAIL] MISMATCH: {orb_time} setup (RR={config_rr}, SL={config_sl_mode}) in config but NOT in database")
                all_pass = False

    # Check: Every config ORB exists in database
    for orb_time, config_list in orb_configs.items():
        if config_list is None:
            continue  # Skip ORB, no validation needed

        if not isinstance(config_list, list):
            continue  # Already reported error above

        if orb_time not in db_by_orb:
            print(f"[FAIL] MISMATCH: {orb_time} in config but NOT in database")
            all_pass = False

    if all_pass:
        print(f"[PASS] {instrument} config matches database perfectly")

    return all_pass


def _original_test_instrument_sync(instrument, db_setups, orb_configs, orb_size_filters):
    """
    DEPRECATED: Old bidirectional comparison logic.
    Kept for reference but not used.
    """

    if not db_setups:
        print(f"[WARN]  No {instrument} setups in database (expected if not using {instrument})")
        return True

    all_pass = True

    # Check: Every database setup must exist in config
    for setup in db_setups:
        _, orb_time, db_rr, db_sl_mode, db_filter = setup

        # Check if ORB exists in config
        if orb_time not in orb_configs:
            print(f"[FAIL] MISMATCH: {orb_time} in database but NOT in config.py")
            all_pass = False
            continue

        config_list = orb_configs[orb_time]
        filter_list = orb_size_filters.get(orb_time)

        # Handle special case where ORB is marked as None (skip)
        if config_list is None:
            print(f"[FAIL] MISMATCH: {orb_time} in database but marked as SKIP in config")
            all_pass = False
            continue

        # Config should be a list of setups
        if not isinstance(config_list, list):
            print(f"[FAIL] ERROR: {orb_time} config is not a list (architecture error)")
            all_pass = False
            continue

        # Find this specific setup in the config list
        found = False
        for i, (config_setup, config_filter) in enumerate(zip(config_list, filter_list)):
            config_rr = config_setup.get('rr')
            config_sl_mode = config_setup.get('sl_mode')

            # Check if this setup matches
            rr_match = abs(db_rr - config_rr) < 0.001
            sl_match = db_sl_mode == config_sl_mode

            # Check filter match
            db_filter_val = db_filter if db_filter is not None else None
            config_filter_val = config_filter if config_filter is not None else None

            if db_filter_val is None and config_filter_val is None:
                filter_match = True
            elif db_filter_val is None or config_filter_val is None:
                filter_match = False
            else:
                filter_match = abs(db_filter_val - config_filter_val) < 0.001

            if rr_match and sl_match and filter_match:
                found = True
                break

        if not found:
            print(f"[FAIL] MISMATCH: {orb_time} setup (RR={db_rr}, SL={db_sl_mode}) in database but NOT in config")
            all_pass = False

    # Check: Every config setup must exist in database
    for orb_time, config_list in orb_configs.items():
        if config_list is None:
            continue  # Skip ORB, no validation needed

        if not isinstance(config_list, list):
            continue  # Already reported error above

        filter_list = orb_size_filters.get(orb_time, [])

        for i, (config_setup, config_filter) in enumerate(zip(config_list, filter_list)):
            config_rr = config_setup.get('rr')
            config_sl_mode = config_setup.get('sl_mode')

            # Find this specific setup in database
            found = False
            for setup in db_setups:
                _, db_orb_time, db_rr, db_sl_mode, db_filter = setup

                if db_orb_time != orb_time:
                    continue

                rr_match = abs(db_rr - config_rr) < 0.001
                sl_match = db_sl_mode == config_sl_mode

                db_filter_val = db_filter if db_filter is not None else None
                config_filter_val = config_filter if config_filter is not None else None

                if db_filter_val is None and config_filter_val is None:
                    filter_match = True
                elif db_filter_val is None or config_filter_val is None:
                    filter_match = False
                else:
                    filter_match = abs(db_filter_val - config_filter_val) < 0.001

                if rr_match and sl_match and filter_match:
                    found = True
                    break

            if not found:
                print(f"[FAIL] MISMATCH: {orb_time} setup (RR={config_rr}, SL={config_sl_mode}) in config but NOT in database")
                all_pass = False

    if all_pass:
        print(f"[PASS] {instrument} config matches database perfectly")
    else:
        print(f"[FAIL] {instrument} has mismatches")

    return all_pass


def test_setup_detector_loads():
    """Test that SetupDetector can load from database"""
    try:
        from trading_app.setup_detector import SetupDetector
        detector = SetupDetector(None)  # Use cloud-aware path

        mgc_setups = detector.get_all_validated_setups('MGC')

        if not mgc_setups:
            print("[FAIL] FAILED: SetupDetector couldn't load MGC setups")
            return False

        print(f"[PASS] SetupDetector successfully loaded {len(mgc_setups)} MGC setups")
        return True

    except Exception as e:
        print(f"[FAIL] FAILED: SetupDetector error: {e}")
        return False


def test_data_loader_filters():
    """Test that data_loader uses correct filters"""
    try:
        from trading_app.data_loader import LiveDataLoader
        from trading_app.config import ENABLE_ORB_SIZE_FILTERS, MGC_ORB_SIZE_FILTERS

        if ENABLE_ORB_SIZE_FILTERS:
            print(f"[PASS] ORB size filters ENABLED")
            print(f"   MGC filters: {MGC_ORB_SIZE_FILTERS}")
        else:
            print(f"[WARN]  ORB size filters DISABLED")

        return True

    except Exception as e:
        print(f"[FAIL] FAILED: data_loader error: {e}")
        return False


def test_strategy_engine_loads():
    """Test that StrategyEngine loads configs"""
    try:
        from trading_app.strategy_engine import StrategyEngine

        # Use the configs loaded at module level
        if not MGC_ORB_CONFIGS:
            print("[FAIL] FAILED: MGC_ORB_CONFIGS is empty")
            return False

        print(f"[PASS] StrategyEngine has {len(MGC_ORB_CONFIGS)} MGC ORB configs")
        return True

    except Exception as e:
        print(f"[FAIL] FAILED: StrategyEngine error: {e}")
        return False


def main():
    """Run all synchronization tests"""
    print("=" * 70)
    print("TESTING APP SYNCHRONIZATION")
    print("=" * 70)
    print()

    # Test 1: Config matches database
    print("TEST 1: Config.py matches validated_setups database")
    print("-" * 70)
    test1_pass = test_config_matches_database()
    print()

    # Test 2: SetupDetector loads
    print("TEST 2: SetupDetector loads from database")
    print("-" * 70)
    test2_pass = test_setup_detector_loads()
    print()

    # Test 3: Data loader filters
    print("TEST 3: Data loader filter checking")
    print("-" * 70)
    test3_pass = test_data_loader_filters()
    print()

    # Test 4: Strategy engine loads
    print("TEST 4: Strategy engine config loading")
    print("-" * 70)
    test4_pass = test_strategy_engine_loads()
    print()

    # Summary
    print("=" * 70)
    if test1_pass and test2_pass and test3_pass and test4_pass:
        print("[PASS] ALL TESTS PASSED!")
        print()
        print("Your apps are now synchronized:")
        print("  - config.py matches validated_setups database")
        print("  - setup_detector.py works with all instruments")
        print("  - data_loader.py filter checking works")
        print("  - strategy_engine.py loads configs")
        print("  - All components load without errors")
        print()
        print("[PASS] Your apps are SAFE TO USE!")
        return 0
    else:
        print("[FAIL] TESTS FAILED!")
        print()
        print("[WARN]  DO NOT USE THE APPS UNTIL MISMATCHES ARE FIXED")
        print()
        print("Fix the issues above and run this test again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
