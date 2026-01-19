"""
Test Strategy Display Completeness

PURPOSE: Ensure every strategy displays complete information including:
- What action to take (ENTER/MANAGE/EXIT/STAND_DOWN)
- What setup triggered (setup name, tier)
- WHY (list of reasons/conditions)
- Trade details (entry/stop/target prices)
- Next instruction (what to do next)

USER FEEDBACK: "wanting more explanation of the trades and why (and what setups etc)"
This test suite directly addresses that feedback.
"""

import pytest
import sys
from pathlib import Path

# Add trading_app to path (same as conftest)
PROJECT_ROOT = Path(__file__).parent.parent.parent
TRADING_APP_PATH = PROJECT_ROOT / "trading_app"
sys.path.insert(0, str(TRADING_APP_PATH))

from strategy_engine import StrategyEvaluation, ActionType, StrategyState


class TestActionDisplay:
    """Test that action type is always displayed."""

    def test_enter_action_is_displayed(self, mock_strategy_evaluation_enter):
        """ENTER action must be clearly shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.action is not None, "Action is None - user won't know what to do!"
        assert evaluation.action == ActionType.ENTER, "Wrong action type"
        assert evaluation.action.value in ["ENTER", "enter"], "Action value not displayable"

    def test_stand_down_action_is_displayed(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN action must be clearly shown."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.action is not None
        assert evaluation.action == ActionType.STAND_DOWN
        assert evaluation.action.value in ["STAND_DOWN", "stand_down"]

    def test_action_never_none(self, mock_strategy_evaluation_enter, mock_strategy_evaluation_stand_down):
        """Action must NEVER be None."""
        for evaluation in [mock_strategy_evaluation_enter, mock_strategy_evaluation_stand_down]:
            assert evaluation.action is not None, "Action cannot be None!"
            assert isinstance(evaluation.action, ActionType), "Action must be ActionType enum"


class TestSetupNameDisplay:
    """Test that setup name is always displayed."""

    def test_setup_name_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Setup name must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.setup_name is not None, "Setup name is None - user won't know WHAT setup!"
        assert len(evaluation.setup_name) > 0, "Setup name is empty"
        assert "2300" in evaluation.setup_name, "Setup name should include ORB time"
        assert "ORB" in evaluation.setup_name, "Setup name should indicate ORB"
        assert "HALF" in evaluation.setup_name or "FULL" in evaluation.setup_name, "Should indicate SL mode"

    def test_setup_name_format_is_clear(self, mock_strategy_evaluation_enter):
        """Setup name should be human-readable."""
        evaluation = mock_strategy_evaluation_enter

        # Expected format: "2300 ORB HALF" or similar
        assert evaluation.setup_name == "2300 ORB HALF", f"Unexpected format: {evaluation.setup_name}"

    def test_setup_name_shown_even_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Setup name still shown (user needs to know what failed)."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.setup_name is not None, "Setup name should be shown even when filter fails"
        assert len(evaluation.setup_name) > 0


class TestReasonsDisplay:
    """
    Test that WHY is explained with reasons list.

    CRITICAL: User feedback - "wanting more explanation of the trades and why"
    """

    def test_reasons_list_exists_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Reasons list must exist and be populated."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.reasons is not None, "Reasons is None - user won't know WHY!"
        assert isinstance(evaluation.reasons, list), "Reasons must be a list"
        assert len(evaluation.reasons) > 0, "Reasons list is empty - user won't know WHY!"

    def test_reasons_list_exists_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Reasons list must explain WHY no trade."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.reasons is not None, "Reasons is None - user won't know WHY no trade!"
        assert isinstance(evaluation.reasons, list), "Reasons must be a list"
        assert len(evaluation.reasons) > 0, "Must explain WHY standing down!"

    def test_reasons_list_has_multiple_items(self, mock_strategy_evaluation_enter):
        """Reasons should have multiple items (complete explanation)."""
        evaluation = mock_strategy_evaluation_enter

        assert len(evaluation.reasons) >= 3, f"Only {len(evaluation.reasons)} reasons - need more explanation!"
        # Expect: ORB formed, filter passed, entry confirmed, tier info

    def test_reasons_include_orb_formation(self, mock_strategy_evaluation_enter):
        """Reasons should mention ORB formation with levels."""
        evaluation = mock_strategy_evaluation_enter

        orb_reason = None
        for reason in evaluation.reasons:
            if "ORB formed" in reason or "ORB" in reason:
                orb_reason = reason
                break

        assert orb_reason is not None, "No reason mentions ORB formation!"
        assert "High" in orb_reason or "high" in orb_reason.lower(), "Should show ORB high"
        assert "Low" in orb_reason or "low" in orb_reason.lower(), "Should show ORB low"
        assert "Size" in orb_reason or "size" in orb_reason.lower(), "Should show ORB size"

    def test_reasons_include_filter_status(self, mock_strategy_evaluation_enter, mock_strategy_evaluation_stand_down):
        """Reasons should mention filter pass/fail."""
        # ENTER case: filter PASSED
        enter_eval = mock_strategy_evaluation_enter
        filter_reason = [r for r in enter_eval.reasons if "filter" in r.lower()]
        assert len(filter_reason) > 0, "Should mention filter status for ENTER"
        assert any("PASSED" in r or "passed" in r for r in filter_reason), "Should say filter PASSED"

        # STAND_DOWN case: filter FAILED
        stand_down_eval = mock_strategy_evaluation_stand_down
        filter_reason = [r for r in stand_down_eval.reasons if "filter" in r.lower()]
        assert len(filter_reason) > 0, "Should mention filter status for STAND_DOWN"
        assert any("FAILED" in r or "failed" in r for r in filter_reason), "Should say filter FAILED"

    def test_reasons_include_entry_confirmation(self, mock_strategy_evaluation_enter):
        """Reasons should mention entry confirmation (close outside)."""
        evaluation = mock_strategy_evaluation_enter

        entry_reason = [r for r in evaluation.reasons if "close" in r.lower() and "outside" in r.lower()]
        assert len(entry_reason) > 0, "Should mention close outside ORB!"

    def test_reasons_include_setup_quality(self, mock_strategy_evaluation_enter):
        """Reasons should mention setup tier/quality."""
        evaluation = mock_strategy_evaluation_enter

        tier_reason = [r for r in evaluation.reasons if "tier" in r.lower() or "S+" in r or "win rate" in r.lower()]
        assert len(tier_reason) > 0, "Should mention setup quality (tier, win rate, expectancy)"

    def test_reasons_are_human_readable(self, mock_strategy_evaluation_enter):
        """Reasons should be complete sentences, not codes."""
        evaluation = mock_strategy_evaluation_enter

        for reason in evaluation.reasons:
            assert isinstance(reason, str), f"Reason is not a string: {type(reason)}"
            assert len(reason) > 10, f"Reason too short: '{reason}'"
            # Should not be just codes like "ORB_PASSED" - should be explanatory


class TestSetupDetailsDisplay:
    """
    Test that setup details are displayed (tier, RR, win rate, expectancy).

    USER FEEDBACK: "what setups etc" - user needs to know setup characteristics.
    """

    def test_setup_tier_displayed(self, mock_strategy_evaluation_enter):
        """Setup tier must be shown (S+, S, A, B, C)."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.setup_tier is not None, "Setup tier is None - user won't know quality!"
        assert evaluation.setup_tier in ["S+", "S", "A", "B", "C"], f"Invalid tier: {evaluation.setup_tier}"

    def test_rr_displayed(self, mock_strategy_evaluation_enter):
        """RR (reward:risk) must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.rr is not None, "RR is None - user won't know target distance!"
        assert evaluation.rr > 0, "RR must be positive"
        assert isinstance(evaluation.rr, (int, float)), "RR must be numeric"

    def test_win_rate_displayed(self, mock_strategy_evaluation_enter):
        """Win rate percentage must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.win_rate is not None, "Win rate is None - user won't know probability!"
        assert 0 <= evaluation.win_rate <= 100, f"Win rate out of range: {evaluation.win_rate}%"
        assert isinstance(evaluation.win_rate, (int, float)), "Win rate must be numeric"

    def test_avg_r_displayed(self, mock_strategy_evaluation_enter):
        """Average R-multiple must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.avg_r is not None, "Avg R is None - user won't know expectancy!"
        assert isinstance(evaluation.avg_r, (int, float)), "Avg R must be numeric"

    def test_annual_trades_displayed(self, mock_strategy_evaluation_enter):
        """Annual trade frequency must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.annual_trades is not None, "Annual trades is None - user won't know frequency!"
        assert evaluation.annual_trades > 0, "Annual trades must be positive"
        assert isinstance(evaluation.annual_trades, (int, float)), "Annual trades must be numeric"

    def test_no_setup_details_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Setup details may be None (setup didn't qualify)."""
        evaluation = mock_strategy_evaluation_stand_down

        # These can be None when setup fails filter
        # But tier should still be None to indicate failure
        assert evaluation.setup_tier is None, "Tier should be None when setup fails"
        assert evaluation.rr is None, "RR should be None when setup fails"
        assert evaluation.win_rate is None, "Win rate should be None when setup fails"


class TestPriceDisplay:
    """Test that entry/stop/target prices are displayed."""

    def test_entry_price_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Entry price must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.entry_price is not None, "Entry price is None - user won't know where to enter!"
        assert evaluation.entry_price > 0, "Entry price must be positive"
        assert isinstance(evaluation.entry_price, (int, float)), "Entry price must be numeric"

    def test_stop_price_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Stop price must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.stop_price is not None, "Stop price is None - user won't know where to stop!"
        assert evaluation.stop_price > 0, "Stop price must be positive"
        assert isinstance(evaluation.stop_price, (int, float)), "Stop price must be numeric"

    def test_target_price_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Target price must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.target_price is not None, "Target price is None - user won't know where to exit!"
        assert evaluation.target_price > 0, "Target price must be positive"
        assert isinstance(evaluation.target_price, (int, float)), "Target price must be numeric"

    def test_prices_are_reasonable(self, mock_strategy_evaluation_enter):
        """Prices should be in reasonable range for gold."""
        evaluation = mock_strategy_evaluation_enter

        # Gold typically trades 2000-3000 range in 2025-2026
        for price in [evaluation.entry_price, evaluation.stop_price, evaluation.target_price]:
            assert 2000 < price < 3000, f"Price {price} seems unreasonable for gold"

    def test_no_prices_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Prices should be None (no trade)."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.entry_price is None, "Entry price should be None for STAND_DOWN"
        assert evaluation.stop_price is None, "Stop price should be None for STAND_DOWN"
        assert evaluation.target_price is None, "Target price should be None for STAND_DOWN"


class TestDirectionDisplay:
    """Test that trade direction is displayed."""

    def test_direction_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Direction (LONG/SHORT) must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.direction is not None, "Direction is None - user won't know which way to trade!"
        assert evaluation.direction in ["LONG", "SHORT"], f"Invalid direction: {evaluation.direction}"

    def test_no_direction_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Direction should be None."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.direction is None, "Direction should be None for STAND_DOWN"


class TestNextInstructionDisplay:
    """
    Test that next instruction is displayed.

    USER FEEDBACK: User needs to know "what to do next".
    """

    def test_next_instruction_exists_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Next instruction must tell user what to do."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.next_instruction is not None, "Next instruction is None - user won't know what to do!"
        assert len(evaluation.next_instruction) > 0, "Next instruction is empty!"
        assert isinstance(evaluation.next_instruction, str), "Next instruction must be a string"

    def test_next_instruction_exists_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Next instruction must tell user to wait or what to do."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.next_instruction is not None, "Next instruction is None!"
        assert len(evaluation.next_instruction) > 0, "Next instruction is empty!"

    def test_next_instruction_mentions_entry_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Instruction should mention entry."""
        evaluation = mock_strategy_evaluation_enter

        instruction_lower = evaluation.next_instruction.lower()
        assert "enter" in instruction_lower or "buy" in instruction_lower or "sell" in instruction_lower, \
            "Instruction should mention entry action"

    def test_next_instruction_mentions_stop_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Instruction should mention stop level."""
        evaluation = mock_strategy_evaluation_enter

        instruction_lower = evaluation.next_instruction.lower()
        assert "stop" in instruction_lower, "Instruction should mention stop level"

    def test_next_instruction_mentions_target_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Instruction should mention target level."""
        evaluation = mock_strategy_evaluation_enter

        instruction_lower = evaluation.next_instruction.lower()
        assert "target" in instruction_lower, "Instruction should mention target level"

    def test_next_instruction_is_human_readable(self, mock_strategy_evaluation_enter):
        """Next instruction should be a complete sentence."""
        evaluation = mock_strategy_evaluation_enter

        assert len(evaluation.next_instruction) > 20, "Instruction too short - should be complete sentence"
        # Should not be just "ENTER" - should be explanatory


class TestORBLevelsDisplay:
    """Test that ORB high/low are displayed."""

    def test_orb_high_displayed(self, mock_strategy_evaluation_enter):
        """ORB high must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.orb_high is not None, "ORB high is None - user won't know ORB range!"
        assert evaluation.orb_high > 0, "ORB high must be positive"
        assert isinstance(evaluation.orb_high, (int, float)), "ORB high must be numeric"

    def test_orb_low_displayed(self, mock_strategy_evaluation_enter):
        """ORB low must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.orb_low is not None, "ORB low is None - user won't know ORB range!"
        assert evaluation.orb_low > 0, "ORB low must be positive"
        assert isinstance(evaluation.orb_low, (int, float)), "ORB low must be numeric"

    def test_orb_high_above_low(self, mock_strategy_evaluation_enter):
        """ORB high must be above ORB low."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.orb_high > evaluation.orb_low, \
            f"ORB high ({evaluation.orb_high}) not above low ({evaluation.orb_low})!"


class TestPositionSizeDisplay:
    """Test that position size is displayed."""

    def test_position_size_displayed_for_enter(self, mock_strategy_evaluation_enter):
        """ENTER: Position size must be shown."""
        evaluation = mock_strategy_evaluation_enter

        assert evaluation.position_size is not None, "Position size is None - user won't know how many contracts!"
        assert evaluation.position_size > 0, "Position size must be positive"
        assert isinstance(evaluation.position_size, (int, float)), "Position size must be numeric"

    def test_no_position_size_for_stand_down(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Position size should be None."""
        evaluation = mock_strategy_evaluation_stand_down

        assert evaluation.position_size is None, "Position size should be None for STAND_DOWN"


class TestNoMissingFields:
    """
    Test that no critical fields are None/missing when they should have values.

    CRITICAL: User feedback - ensure complete information.
    """

    def test_enter_has_all_required_fields(self, mock_strategy_evaluation_enter):
        """ENTER: All required fields must be populated."""
        evaluation = mock_strategy_evaluation_enter

        # REQUIRED for ENTER
        assert evaluation.action is not None
        assert evaluation.setup_name is not None
        assert evaluation.reasons is not None and len(evaluation.reasons) > 0
        assert evaluation.entry_price is not None
        assert evaluation.stop_price is not None
        assert evaluation.target_price is not None
        assert evaluation.direction is not None
        assert evaluation.next_instruction is not None
        assert evaluation.orb_high is not None
        assert evaluation.orb_low is not None
        assert evaluation.position_size is not None
        assert evaluation.setup_tier is not None
        assert evaluation.rr is not None
        assert evaluation.win_rate is not None
        assert evaluation.avg_r is not None
        assert evaluation.annual_trades is not None

    def test_stand_down_has_required_fields(self, mock_strategy_evaluation_stand_down):
        """STAND_DOWN: Required fields must be populated."""
        evaluation = mock_strategy_evaluation_stand_down

        # REQUIRED for STAND_DOWN
        assert evaluation.action is not None
        assert evaluation.setup_name is not None  # Still show what was evaluated
        assert evaluation.reasons is not None and len(evaluation.reasons) > 0  # Must explain WHY
        assert evaluation.next_instruction is not None  # Tell user what to do

        # OPTIONAL/None for STAND_DOWN (no trade)
        assert evaluation.entry_price is None
        assert evaluation.stop_price is None
        assert evaluation.target_price is None
        assert evaluation.direction is None
        assert evaluation.position_size is None
        assert evaluation.setup_tier is None  # Failed filter, no tier
        assert evaluation.rr is None
        assert evaluation.win_rate is None
