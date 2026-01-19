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

        # Check specific ORB configs (CROWN JEWELS)
        assert configs['1000']['rr'] == 8.0
        assert configs['1000']['sl_mode'] == 'FULL'

        assert configs['2300']['rr'] == 1.5
        assert configs['2300']['sl_mode'] == 'HALF'

        assert configs['0030']['rr'] == 3.0
        assert configs['0030']['sl_mode'] == 'HALF'

    def test_mgc_filters_load_correctly(self):
        """MGC filters should match database values."""
        configs, filters = load_instrument_configs('MGC')

        # Check filter values
        assert filters['0900'] is None  # No filter
        assert filters['1000'] is None  # No filter (CROWN JEWEL)
        assert filters['2300'] == pytest.approx(0.155, abs=0.001)
        assert filters['0030'] == pytest.approx(0.112, abs=0.001)

    def test_nq_configs_load(self):
        """NQ configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('NQ')

        # Should have 5 ORB configs
        assert len(configs) == 5

        # All NQ ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config in configs.items():
            assert config['rr'] == 1.0

    def test_mpl_configs_load(self):
        """MPL configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('MPL')

        # Should have 6 ORB configs
        assert len(configs) == 6

        # All MPL ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config in configs.items():
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
        """get_orb_config should return specific ORB config."""
        config = get_orb_config('MGC', '1000')

        assert config is not None
        assert config['rr'] == 8.0
        assert config['sl_mode'] == 'FULL'

    def test_get_orb_size_filter(self):
        """get_orb_size_filter should return specific filter value."""
        # ORB with filter
        filter_2300 = get_orb_size_filter('MGC', '2300')
        assert filter_2300 == pytest.approx(0.155, abs=0.001)

        # ORB without filter
        filter_1000 = get_orb_size_filter('MGC', '1000')
        assert filter_1000 is None

    def test_invalid_orb_time_returns_none(self):
        """Invalid ORB time should return None."""
        config = get_orb_config('MGC', '9999')
        assert config is None

        filter_val = get_orb_size_filter('MGC', '9999')
        assert filter_val is None


class TestDatabaseSync:
    """Test that configs match validated_setups database."""

    def test_mgc_1000_crown_jewel(self):
        """MGC 1000 ORB should be RR=8.0 FULL (CROWN JEWEL)."""
        config = get_orb_config('MGC', '1000')
        filter_val = get_orb_size_filter('MGC', '1000')

        assert config['rr'] == 8.0
        assert config['sl_mode'] == 'FULL'
        assert filter_val is None  # No filter on CROWN JEWEL

    def test_mgc_2300_best_overall(self):
        """MGC 2300 ORB should be RR=1.5 HALF with filter (BEST OVERALL)."""
        config = get_orb_config('MGC', '2300')
        filter_val = get_orb_size_filter('MGC', '2300')

        assert config['rr'] == 1.5
        assert config['sl_mode'] == 'HALF'
        assert filter_val == pytest.approx(0.155, abs=0.001)

    def test_all_mgc_orbs_have_valid_configs(self):
        """All 6 MGC ORBs should have valid configs."""
        expected_orbs = ['0900', '1000', '1100', '1800', '2300', '0030']
        configs, filters = load_instrument_configs('MGC')

        for orb_time in expected_orbs:
            assert orb_time in configs
            assert orb_time in filters

            config = configs[orb_time]
            assert 'rr' in config
            assert 'sl_mode' in config
            assert config['rr'] > 0
            assert config['sl_mode'] in ['FULL', 'HALF']


if __name__ == "__main__":
    """Run tests with pytest."""
    pytest.main([__file__, "-v"])
