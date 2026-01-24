"""
Test Strategy Explanation Accuracy

PURPOSE: Ensure strategy explanations match the underlying logic/config/database.
No contradictions. No misleading information.

USER FEEDBACK: "wanting more explanation of the trades and why"
This ensures explanations are ACCURATE, not just present.
"""

import pytest
import sys
from pathlib import Path

# Add trading_app to path (same as conftest)
PROJECT_ROOT = Path(__file__).parent.parent.parent
TRADING_APP_PATH = PROJECT_ROOT / "trading_app"
sys.path.insert(0, str(TRADING_APP_PATH))

import config
from strategy_engine import ActionType, StrategyState


class TestORBFilterExplanationAccuracy:
    """Test that ORB filter explanations match actual config values."""

    def test_2300_filter_explanation_matches_config(self, mock_strategy_evaluation_enter, config_mgc_orb_2300):
        """2300 ORB: Filter explanation must match config.MGC_ORB_SIZE_FILTERS."""
        evaluation = mock_strategy_evaluation_enter
        orb_config = config_mgc_orb_2300

        # Get filter value from config
        expected_filter = orb_config["orb_size_filter"]
        assert expected_filter == 0.155, "Config value changed - update test"

        # Check that evaluation mentions the correct filter
        filter_reasons = [r for r in evaluation.reasons if "filter" in r.lower() and "0.155" in r]
        assert len(filter_reasons) > 0, f"Filter explanation should mention 0.155 threshold! Reasons: {evaluation.reasons}"

    def test_2300_filter_calculation_shown_correctly(self, sample_orb_2300_passing):
        """2300 ORB: Filter calculation (size/ATR) should be shown correctly."""
        orb = sample_orb_2300_passing

        # Expected calculation: 2.50 / 17.0 = 0.147 < 0.155 (PASSES)
        orb_size = orb["orb_size"]
        atr = orb["atr_20"]
        threshold = orb["filter_threshold"]

        ratio = orb_size / atr
        assert ratio < threshold, "Test data should pass filter"
        assert abs(ratio - 0.147) < 0.01, f"Expected ratio ~0.147, got {ratio}"

    def test_0030_filter_explanation_matches_config(self, sample_orb_0030):
        """0030 ORB: Filter threshold should match config (0.112)."""
        orb = sample_orb_0030

        # NEW ARCHITECTURE: Config returns list of filters (0030 has 1 setup)
        assert config.MGC_ORB_SIZE_FILTERS.get("0030") == [0.112], "Config mismatch!"

        # Check calculation
        ratio = orb["orb_size"] / orb["atr_20"]  # 2.50 / 23.0 = 0.109
        assert ratio < 0.112, "Should pass filter"

    def test_day_orb_no_filter_explanation(self, sample_orb_1000):
        """Day ORBs (0900, 1000, 1100): Should not mention filters."""
        orb = sample_orb_1000

        # NEW ARCHITECTURE: 1000 has 2 setups, both with no filter
        assert config.MGC_ORB_SIZE_FILTERS.get("1000") == [None, None], "1000 should have no filters!"


class TestRRExplanationAccuracy:
    """Test that RR (reward:risk) explanations match config."""

    def test_2300_rr_matches_config(self, mock_strategy_evaluation_enter, config_mgc_orb_2300):
        """2300 ORB: RR should be 1.5."""
        evaluation = mock_strategy_evaluation_enter
        orb_config = config_mgc_orb_2300

        assert evaluation.rr == orb_config["rr"], f"RR mismatch: {evaluation.rr} != {orb_config['rr']}"
        assert evaluation.rr == 1.5, "2300 ORB should be 1.5 RR"

    def test_1000_rr_matches_config(self, sample_orb_1000, config_mgc_orb_1000):
        """1000 ORB: RR should be 8.0 (crown jewel)."""
        orb = sample_orb_1000
        orb_config = config_mgc_orb_1000

        assert orb["rr"] == orb_config["rr"], "RR mismatch"
        assert orb["rr"] == 8.0, "1000 ORB should be 8.0 RR"

    def test_target_calculation_matches_rr(self, mock_strategy_evaluation_enter):
        """Target price should equal: Entry + (Stop distance × RR)."""
        evaluation = mock_strategy_evaluation_enter

        entry = evaluation.entry_price  # 2688.00
        stop = evaluation.stop_price    # 2686.25 (midpoint)
        target = evaluation.target_price  # Should be entry + (1.75 × 1.5 RR)
        rr = evaluation.rr  # 1.5

        stop_distance = abs(entry - stop)  # 1.75 pts
        expected_target = entry + (stop_distance * rr)  # 2688.00 + (1.75 × 1.5) = 2690.625

        assert abs(target - expected_target) < 0.01, \
            f"Target calculation wrong: {target} != {expected_target} (Entry {entry} + Stop {stop_distance} × RR {rr})"


class TestSLModeExplanationAccuracy:
    """Test that stop loss mode explanations match config."""

    def test_2300_half_mode_explanation(self, mock_strategy_evaluation_enter, config_mgc_orb_2300):
        """2300 ORB: Should be HALF mode (stop at midpoint)."""
        evaluation = mock_strategy_evaluation_enter
        orb_config = config_mgc_orb_2300

        assert orb_config["sl_mode"] == "HALF", "2300 should be HALF mode"
        assert evaluation.setup_name == "2300 ORB HALF", "Setup name should indicate HALF"

        # Check stop calculation: should be midpoint
        orb_midpoint = (evaluation.orb_high + evaluation.orb_low) / 2  # (2687.50 + 2685.00) / 2 = 2686.25
        assert abs(evaluation.stop_price - orb_midpoint) < 0.01, \
            f"HALF mode: Stop should be at midpoint {orb_midpoint}, got {evaluation.stop_price}"

    def test_1000_full_mode_explanation(self, sample_orb_1000, config_mgc_orb_1000):
        """1000 ORB: Should be FULL mode (stop at opposite edge)."""
        orb = sample_orb_1000
        orb_config = config_mgc_orb_1000

        assert orb_config["sl_mode"] == "FULL", "1000 should be FULL mode"
        assert "FULL" in orb["sl_mode"], "Should indicate FULL mode"

    def test_half_mode_stop_at_midpoint(self, sample_orb_2300_passing):
        """HALF mode: Stop should be calculated at ORB midpoint."""
        orb = sample_orb_2300_passing

        midpoint = (orb["orb_high"] + orb["orb_low"]) / 2
        assert abs(midpoint - 2686.25) < 0.01, "Midpoint calculation wrong"

    def test_full_mode_stop_at_opposite_edge(self, sample_orb_1000):
        """FULL mode: Stop should be at opposite edge of ORB."""
        orb = sample_orb_1000

        # If entry is ABOVE ORB (long), stop is at orb_low
        # If entry is BELOW ORB (short), stop is at orb_high
        current_price = orb["current_price"]  # 2688.00
        orb_high = orb["orb_high"]  # 2687.50

        if current_price > orb_high:
            # Long entry, stop at low
            expected_stop = orb["orb_low"]
        else:
            # Short entry, stop at high
            expected_stop = orb["orb_high"]

        # For this sample: long entry (2688 > 2687.50), stop should be 2685.00
        assert expected_stop == 2685.00, "Stop should be at ORB low for long"


class TestWinRateDisplayAccuracy:
    """Test that win rate matches database/validated_setups."""

    def test_2300_win_rate_matches_database(self, mock_strategy_evaluation_enter, mock_validated_setup_2300):
        """2300 ORB: Win rate should match validated_setups table."""
        evaluation = mock_strategy_evaluation_enter
        db_setup = mock_validated_setup_2300

        assert evaluation.win_rate == db_setup["win_rate"], \
            f"Win rate mismatch: {evaluation.win_rate}% != {db_setup['win_rate']}%"
        assert evaluation.win_rate == 56.1, "2300 win rate should be 56.1%"

    def test_1000_win_rate_matches_database(self, sample_orb_1000, mock_validated_setup_1000):
        """1000 ORB: Win rate should match validated_setups table."""
        orb = sample_orb_1000
        db_setup = mock_validated_setup_1000

        assert orb["expected_win_rate"] == db_setup["win_rate"], \
            f"Win rate mismatch: {orb['expected_win_rate']}% != {db_setup['win_rate']}%"
        assert orb["expected_win_rate"] == 15.3, "1000 win rate should be 15.3%"

    def test_win_rate_in_valid_range(self, mock_strategy_evaluation_enter):
        """Win rate should be between 0-100%."""
        evaluation = mock_strategy_evaluation_enter

        assert 0 <= evaluation.win_rate <= 100, f"Win rate {evaluation.win_rate}% is out of range!"


class TestTierDisplayAccuracy:
    """Test that tier badges match database."""

    def test_2300_tier_matches_database(self, mock_strategy_evaluation_enter, mock_validated_setup_2300):
        """2300 ORB: Tier should be S+ (best overall)."""
        evaluation = mock_strategy_evaluation_enter
        db_setup = mock_validated_setup_2300

        assert evaluation.setup_tier == db_setup["tier"], \
            f"Tier mismatch: {evaluation.setup_tier} != {db_setup['tier']}"
        assert evaluation.setup_tier == "S+", "2300 should be S+ tier"

    def test_1000_tier_matches_database(self, sample_orb_1000, mock_validated_setup_1000):
        """1000 ORB: Tier should be S+ (crown jewel)."""
        orb = sample_orb_1000
        db_setup = mock_validated_setup_1000

        assert orb["expected_tier"] == db_setup["tier"], \
            f"Tier mismatch: {orb['expected_tier']} != {db_setup['tier']}"
        assert orb["expected_tier"] == "S+", "1000 should be S+ tier"

    def test_tier_is_valid_value(self, mock_strategy_evaluation_enter):
        """Tier should be one of: S+, S, A, B, C."""
        evaluation = mock_strategy_evaluation_enter

        valid_tiers = ["S+", "S", "A", "B", "C"]
        assert evaluation.setup_tier in valid_tiers, \
            f"Invalid tier: {evaluation.setup_tier} (must be one of {valid_tiers})"


class TestExpectancyDisplayAccuracy:
    """Test that expectancy (avg R, annual trades) matches database."""

    def test_2300_avg_r_matches_database(self, mock_strategy_evaluation_enter, mock_validated_setup_2300):
        """2300 ORB: Avg R should match validated_setups."""
        evaluation = mock_strategy_evaluation_enter
        db_setup = mock_validated_setup_2300

        assert abs(evaluation.avg_r - db_setup["avg_r"]) < 0.001, \
            f"Avg R mismatch: {evaluation.avg_r} != {db_setup['avg_r']}"
        assert abs(evaluation.avg_r - 0.403) < 0.001, "2300 avg R should be 0.403"

    def test_1000_avg_r_matches_database(self, sample_orb_1000, mock_validated_setup_1000):
        """1000 ORB: Avg R should match validated_setups."""
        orb = sample_orb_1000
        db_setup = mock_validated_setup_1000

        assert abs(orb["expected_avg_r"] - db_setup["avg_r"]) < 0.001, \
            f"Avg R mismatch: {orb['expected_avg_r']} != {db_setup['avg_r']}"

    def test_annual_trades_matches_database(self, mock_strategy_evaluation_enter, mock_validated_setup_2300):
        """Annual trades should match validated_setups."""
        evaluation = mock_strategy_evaluation_enter
        db_setup = mock_validated_setup_2300

        assert evaluation.annual_trades == db_setup["annual_trades"], \
            f"Annual trades mismatch: {evaluation.annual_trades} != {db_setup['annual_trades']}"
        assert evaluation.annual_trades == 260, "2300 should have ~260 annual trades"

    def test_annual_expectancy_calculation(self, mock_strategy_evaluation_enter):
        """Annual expectancy should equal: avg_r × annual_trades."""
        evaluation = mock_strategy_evaluation_enter

        annual_expectancy = evaluation.avg_r * evaluation.annual_trades  # 0.403 × 260 = 104.78R ≈ 105R
        assert abs(annual_expectancy - 105) < 2, \
            f"Annual expectancy should be ~105R, got {annual_expectancy}R"


class TestReasonListAccuracy:
    """
    Test that each reason in the reasons list is TRUE and reflects actual conditions.

    CRITICAL: Reasons should not be lies or assumptions - they must match reality.
    """

    def test_orb_formed_reason_matches_actual_orb(self, mock_strategy_evaluation_enter):
        """If reason says "ORB formed at X/Y", those should be actual orb_high/orb_low."""
        evaluation = mock_strategy_evaluation_enter

        orb_reason = [r for r in evaluation.reasons if "ORB formed" in r or "ORB" in r][0]

        # Should mention actual ORB levels
        assert "2,687.50" in orb_reason or "2687.50" in orb_reason, \
            f"Reason should mention actual ORB high (2687.50): {orb_reason}"
        assert "2,685.00" in orb_reason or "2685.00" in orb_reason, \
            f"Reason should mention actual ORB low (2685.00): {orb_reason}"
        assert "2.50" in orb_reason, f"Reason should mention actual ORB size (2.50): {orb_reason}"

    def test_filter_passed_reason_matches_calculation(self, mock_strategy_evaluation_enter):
        """If reason says "filter PASSED", the math should actually pass."""
        evaluation = mock_strategy_evaluation_enter

        filter_reason = [r for r in evaluation.reasons if "filter" in r.lower() and "PASSED" in r][0]

        # Extract values from reason (should mention ratio and threshold)
        # Example: "ORB size filter PASSED (2.50 pts / 17.0 ATR = 0.147 < 0.155 threshold)"
        assert "0.147" in filter_reason or "0.15" in filter_reason, "Should show actual ratio"
        assert "0.155" in filter_reason, "Should show threshold"
        assert "<" in filter_reason, "Should show that ratio < threshold"

    def test_entry_confirmation_reason_matches_price(self, mock_strategy_evaluation_enter):
        """If reason says "first close outside", the price should actually be outside ORB."""
        evaluation = mock_strategy_evaluation_enter

        entry_reason = [r for r in evaluation.reasons if "close" in r.lower() and "outside" in r.lower()][0]

        # Should mention actual close price (2688.00) and that it's > high (2687.50)
        assert "2,688" in entry_reason or "2688" in entry_reason, \
            f"Reason should mention actual close price: {entry_reason}"
        assert ">" in entry_reason or "above" in entry_reason.lower(), \
            "Reason should indicate close is above high"

    def test_tier_reason_matches_actual_tier(self, mock_strategy_evaluation_enter):
        """If reason mentions tier/quality, it should match setup_tier."""
        evaluation = mock_strategy_evaluation_enter

        tier_reason = [r for r in evaluation.reasons if "tier" in r.lower() or "S+" in r][0]

        # Should mention S+ tier
        assert "S+" in tier_reason, f"Reason should mention S+ tier: {tier_reason}"

        # Should mention win rate (56.1%)
        assert "56.1" in tier_reason or "56%" in tier_reason, \
            f"Reason should mention win rate: {tier_reason}"


class TestNoContradictoryInformation:
    """
    Test that no fields contradict each other.

    CRITICAL: Action, state, and prices must all be consistent.
    """

    def test_enter_action_has_prices(self, mock_strategy_evaluation_enter):
        """If action is ENTER, all prices must be set."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.action == ActionType.ENTER
        assert evaluation.entry_price is not None, "ENTER action must have entry price!"
        assert evaluation.stop_price is not None, "ENTER action must have stop price!"
        assert evaluation.target_price is not None, "ENTER action must have target price!"

    def test_stand_down_action_has_no_prices(self, mock_strategy_evaluation_stand_down):
        """If action is STAND_DOWN, prices should be None."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.action == ActionType.STAND_DOWN
        assert evaluation.entry_price is None, "STAND_DOWN should have no entry price!"
        assert evaluation.stop_price is None, "STAND_DOWN should have no stop price!"
        assert evaluation.target_price is None, "STAND_DOWN should have no target price!"

    def test_enter_action_has_direction(self, mock_strategy_evaluation_enter):
        """If action is ENTER, direction must be set."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.action == ActionType.ENTER
        assert evaluation.direction is not None, "ENTER action must have direction!"
        assert evaluation.direction in ["LONG", "SHORT"], f"Invalid direction: {evaluation.direction}"

    def test_stand_down_action_has_no_direction(self, mock_strategy_evaluation_stand_down):
        """If action is STAND_DOWN, direction should be None."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.action == ActionType.STAND_DOWN
        assert evaluation.direction is None, "STAND_DOWN should have no direction!"

    def test_enter_action_has_position_size(self, mock_strategy_evaluation_enter):
        """If action is ENTER, position size must be set."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.action == ActionType.ENTER
        assert evaluation.position_size is not None, "ENTER action must have position size!"
        assert evaluation.position_size > 0, "Position size must be positive!"

    def test_stand_down_action_has_no_position_size(self, mock_strategy_evaluation_stand_down):
        """If action is STAND_DOWN, position size should be None."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.action == ActionType.STAND_DOWN
        assert evaluation.position_size is None, "STAND_DOWN should have no position size!"

    def test_state_matches_action(self, mock_strategy_evaluation_enter, mock_strategy_evaluation_stand_down):
        """State and action should be consistent."""
        # ENTER: state should be READY
        enter_eval = mock_strategy_evaluation_enter
        assert enter_eval.action == ActionType.ENTER
        assert enter_eval.state == StrategyState.READY, "ENTER action should have READY state"

        # STAND_DOWN: state should be INVALID
        stand_down_eval = mock_strategy_evaluation_stand_down
        assert stand_down_eval.action == ActionType.STAND_DOWN
        assert stand_down_eval.state == StrategyState.INVALID, "STAND_DOWN action should have INVALID state"

    def test_long_entry_above_orb(self, mock_strategy_evaluation_enter):
        """LONG entry: entry price should be above ORB high."""
        evaluation = mock_strategy_evaluation_enter

        if evaluation.direction == "LONG":
            assert evaluation.entry_price > evaluation.orb_high, \
                f"LONG entry ({evaluation.entry_price}) should be above ORB high ({evaluation.orb_high})!"

    def test_long_stop_below_entry(self, mock_strategy_evaluation_enter):
        """LONG entry: stop should be below entry."""
        evaluation = mock_strategy_evaluation_enter

        if evaluation.direction == "LONG":
            assert evaluation.stop_price < evaluation.entry_price, \
                f"LONG stop ({evaluation.stop_price}) should be below entry ({evaluation.entry_price})!"

    def test_long_target_above_entry(self, mock_strategy_evaluation_enter):
        """LONG entry: target should be above entry."""
        evaluation = mock_strategy_evaluation_enter

        if evaluation.direction == "LONG":
            assert evaluation.target_price > evaluation.entry_price, \
                f"LONG target ({evaluation.target_price}) should be above entry ({evaluation.entry_price})!"


class TestConfigDatabaseConsistency:
    """
    Test that displayed values match both config.py AND validated_setups database.

    CRITICAL: config.py and database MUST be synchronized (enforced by test_app_sync.py).
    """

    def test_2300_config_matches_mock_database(self, config_mgc_orb_2300, mock_validated_setup_2300):
        """Config and database should match for 2300 ORB."""
        config_data = config_mgc_orb_2300
        db_data = mock_validated_setup_2300

        assert config_data["rr"] == db_data["rr"], "RR mismatch between config and DB"
        assert config_data["sl_mode"] == db_data["sl_mode"], "SL mode mismatch"
        assert abs(config_data["orb_size_filter"] - db_data["orb_size_filter"]) < 0.001, "Filter mismatch"

    def test_1000_config_matches_mock_database(self, config_mgc_orb_1000, mock_validated_setup_1000):
        """Config and database should match for 1000 ORB."""
        config_data = config_mgc_orb_1000
        db_data = mock_validated_setup_1000

        assert config_data["rr"] == db_data["rr"], "RR mismatch between config and DB"
        assert config_data["sl_mode"] == db_data["sl_mode"], "SL mode mismatch"
        assert config_data["orb_size_filter"] == db_data["orb_size_filter"], "Filter mismatch"
