"""
test_config_generator.py

Unit tests for config_generator.py - validates dynamic config loading.

Tests:
- Loading configs from database
- Correct RR/SL values
- Filter values match database
- Handles missing database gracefully
"""

import pytest
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config_generator import (
    load_instrument_configs,
    load_all_instrument_configs,
    get_orb_config,
    get_orb_size_filter
)


class TestConfigLoading:
    """Test configuration loading from database."""

    def test_mgc_configs_load_correctly(self):
        """MGC configs should load all 6 ORBs with correct values."""
        configs, filters = load_instrument_configs('MGC')

        # Should have 6 ORB configs
        assert len(configs) == 6

        # NEW ARCHITECTURE: configs[orb_time] is a LIST of setups
        # MGC 1000 has 2 setups (candidates 47 and 48)
        assert isinstance(configs['1000'], list)
        assert len(configs['1000']) == 2
        # Verify both candidates present
        rr_values = sorted([c['rr'] for c in configs['1000']])
        assert rr_values == [1.0, 2.0]

        # MGC 2300 has 1 setup
        assert isinstance(configs['2300'], list)
        assert len(configs['2300']) == 1
        assert configs['2300'][0]['rr'] == 1.5
        assert configs['2300'][0]['sl_mode'] == 'HALF'

        # MGC 0030 has 1 setup
        assert isinstance(configs['0030'], list)
        assert len(configs['0030']) == 1
        assert configs['0030'][0]['rr'] == 3.0
        assert configs['0030'][0]['sl_mode'] == 'HALF'

    def test_mgc_filters_load_correctly(self):
        """MGC filters should match database values."""
        configs, filters = load_instrument_configs('MGC')

        # NEW ARCHITECTURE: filters[orb_time] is a LIST aligned by index with configs
        # Check filter values (lists)
        assert isinstance(filters['0900'], list)
        assert len(filters['0900']) == 1
        assert filters['0900'][0] is None  # No filter

        assert isinstance(filters['1000'], list)
        assert len(filters['1000']) == 2  # 2 setups
        assert all(f is None for f in filters['1000'])  # Both have no filter

        assert isinstance(filters['2300'], list)
        assert len(filters['2300']) == 1
        assert filters['2300'][0] == pytest.approx(0.155, abs=0.001)

        assert isinstance(filters['0030'], list)
        assert len(filters['0030']) == 1
        assert filters['0030'][0] == pytest.approx(0.112, abs=0.001)

    def test_nq_configs_load(self):
        """NQ configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('NQ')

        # Should have 5 ORB configs
        assert len(configs) == 5

        # NEW ARCHITECTURE: each config is a LIST
        # All NQ ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config_list in configs.items():
            assert isinstance(config_list, list)
            # Each setup in the list should have RR=1.0
            for config in config_list:
                assert config['rr'] == 1.0

    def test_mpl_configs_load(self):
        """MPL configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('MPL')

        # Should have 6 ORB configs
        assert len(configs) == 6

        # NEW ARCHITECTURE: each config is a LIST
        # All MPL ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config_list in configs.items():
            assert isinstance(config_list, list)
            # Each setup in the list should have RR=1.0
            for config in config_list:
                assert config['rr'] == 1.0

    def test_all_instruments_load(self):
        """All instruments should load successfully."""
        all_configs = load_all_instrument_configs()

        # Should have MGC, NQ, MPL
        assert 'MGC' in all_configs
        assert 'NQ' in all_configs
        assert 'MPL' in all_configs

        # Each instrument should have configs and filters
        for instrument, (configs, filters) in all_configs.items():
            assert isinstance(configs, dict)
            assert isinstance(filters, dict)
            assert len(configs) > 0


class TestOrbLookup:
    """Test individual ORB config/filter lookup."""

    def test_get_orb_config(self):
        """get_orb_config should return specific ORB config list."""
        config_list = get_orb_config('MGC', '1000')

        # NEW ARCHITECTURE: returns LIST of setups
        assert config_list is not None
        assert isinstance(config_list, list)
        assert len(config_list) == 2  # MGC 1000 has 2 setups (candidates 47+48)

        # Check that both RR values are present
        rr_values = sorted([c['rr'] for c in config_list])
        assert rr_values == [1.0, 2.0]

    def test_get_orb_size_filter(self):
        """get_orb_size_filter should return specific filter list."""
        # NEW ARCHITECTURE: returns LIST of filter values

        # ORB with filter (2300 has 1 setup)
        filter_2300 = get_orb_size_filter('MGC', '2300')
        assert isinstance(filter_2300, list)
        assert len(filter_2300) == 1
        assert filter_2300[0] == pytest.approx(0.155, abs=0.001)

        # ORB without filter (1000 has 2 setups, both None)
        filter_1000 = get_orb_size_filter('MGC', '1000')
        assert isinstance(filter_1000, list)
        assert len(filter_1000) == 2
        assert all(f is None for f in filter_1000)

    def test_invalid_orb_time_returns_none(self):
        """Invalid ORB time should return None."""
        config = get_orb_config('MGC', '9999')
        assert config is None

        filter_val = get_orb_size_filter('MGC', '9999')
        assert filter_val is None


class TestDatabaseSync:
    """Test that configs match validated_setups database."""

    def test_mgc_1000_crown_jewel(self):
        """MGC 1000 ORB has multiple setups including Asia candidates."""
        config_list = get_orb_config('MGC', '1000')
        filter_list = get_orb_size_filter('MGC', '1000')

        # NEW ARCHITECTURE: MGC 1000 has 2 setups (candidates 47+48)
        assert isinstance(config_list, list)
        assert len(config_list) == 2

        # Verify both RR values present
        rr_values = sorted([c['rr'] for c in config_list])
        assert rr_values == [1.0, 2.0]

        # All filters should be None
        assert all(f is None for f in filter_list)

    def test_mgc_2300_best_overall(self):
        """MGC 2300 ORB should be RR=1.5 HALF with filter (BEST OVERALL)."""
        config_list = get_orb_config('MGC', '2300')
        filter_list = get_orb_size_filter('MGC', '2300')

        # NEW ARCHITECTURE: returns lists (2300 has 1 setup)
        assert isinstance(config_list, list)
        assert len(config_list) == 1

        config = config_list[0]
        assert config['rr'] == 1.5
        assert config['sl_mode'] == 'HALF'

        assert len(filter_list) == 1
        assert filter_list[0] == pytest.approx(0.155, abs=0.001)

    def test_all_mgc_orbs_have_valid_configs(self):
        """All 6 MGC ORBs should have valid configs."""
        expected_orbs = ['0900', '1000', '1100', '1800', '2300', '0030']
        configs, filters = load_instrument_configs('MGC')

        for orb_time in expected_orbs:
            assert orb_time in configs
            assert orb_time in filters

            # NEW ARCHITECTURE: each ORB time has a LIST of setups
            config_list = configs[orb_time]
            assert isinstance(config_list, list)
            assert len(config_list) > 0

            # Check each setup in the list
            for config in config_list:
                assert 'rr' in config
                assert 'sl_mode' in config
                assert config['rr'] > 0
                assert config['sl_mode'] in ['FULL', 'HALF']


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v"])
