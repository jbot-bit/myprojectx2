"""
Strategy Advisor AI - Conversational strategy discovery with execution

Enhances the AI assistant with strategy discovery capabilities:
- Natural conversation about strategy ideas
- Extract strategy parameters from chat
- Execute backtests automatically
- Create edge candidates
- Present results in conversation
"""

import os
import logging
import re
import json
from typing import Optional, Dict, List, Tuple
from datetime import date

from strategy_discovery import StrategyDiscovery, DiscoveryConfig
from discovery_ui import create_edge_candidate_from_backtest

logger = logging.getLogger(__name__)


class StrategyAdvisor:
    """AI-powered strategy advisor with discovery execution"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self.discovery_engine = StrategyDiscovery()

    def extract_strategy_params(self, conversation: str) -> Optional[Dict]:
        """
        Extract strategy parameters from conversation using Claude.

        Returns dict with:
            - instrument: str
            - orb_time: str
            - rr: float
            - sl_mode: str
            - orb_size_filter: Optional[float]
            - test_start: str (YYYY-MM-DD)
            - test_end: str (YYYY-MM-DD)
            - hypothesis: str
        """
        if not self.api_key:
            return None

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)

            extraction_prompt = f"""Analyze this trading strategy conversation and extract the key parameters if present.

Conversation:
{conversation}

Extract these parameters if mentioned:
- instrument (MGC, NQ, or MPL)
- orb_time (0900, 1000, 1100, 1800, 2300, 0030)
- rr (risk:reward ratio, e.g., 1.5, 3.0, 8.0)
- sl_mode (FULL or HALF stop)
- orb_size_filter (percentage of ATR, e.g., 0.155 for 15.5%, or null if none)
- test_start (start date YYYY-MM-DD, default to 2024-01-01 if not mentioned)
- test_end (end date YYYY-MM-DD, default to 2026-01-10 if not mentioned)
- hypothesis (brief description of the strategy idea)

Return ONLY a valid JSON object with these fields, or null if not enough information is present.
Example: {{"instrument": "MGC", "orb_time": "2300", "rr": 1.5, "sl_mode": "HALF", "orb_size_filter": 0.155, "test_start": "2024-01-01", "test_end": "2026-01-10", "hypothesis": "Testing 2300 ORB with tight filter"}}

If the user hasn't specified enough parameters yet, return null.
"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": extraction_prompt}]
            )

            content = response.content[0].text.strip()

            # Try to parse JSON
            if content.lower() == "null" or not content:
                return None

            params = json.loads(content)

            # Validate required fields
            required = ["instrument", "orb_time", "rr", "sl_mode"]
            if not all(key in params for key in required):
                return None

            return params

        except Exception as e:
            logger.error(f"Error extracting strategy params: {e}")
            return None

    def organize_strategy_plan(self, conversation: str) -> Optional[str]:
        """
        Organize the conversation into a clear strategy plan using Claude.

        Returns markdown summary of the strategy with all parameters.
        """
        if not self.api_key:
            return None

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)

            organize_prompt = f"""The user and I have been discussing a trading strategy idea. Please organize our conversation into a clear, structured plan.

Conversation:
{conversation}

Create a clear markdown summary with these sections:
1. **Strategy Hypothesis** - What are we testing and why?
2. **Parameters** - All config details (instrument, ORB time, RR, stop mode, filters)
3. **Test Window** - Date range for backtesting
4. **Expected Outcome** - What would make this successful?

Keep it concise and actionable. Use bullet points."""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": organize_prompt}]
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Error organizing plan: {e}")
            return None

    def execute_discovery(self, params: Dict) -> Tuple[bool, str, Optional[int]]:
        """
        Execute the discovery pipeline with extracted parameters.

        Args:
            params: Strategy parameters dict

        Returns:
            (success: bool, message: str, candidate_id: Optional[int])
        """
        try:
            # Create discovery config
            config = DiscoveryConfig(
                instrument=params["instrument"],
                orb_time=params["orb_time"],
                rr=float(params["rr"]),
                sl_mode=params["sl_mode"],
                orb_size_filter=float(params["orb_size_filter"]) if params.get("orb_size_filter") else None
            )

            # Run backtest
            logger.info(f"Running backtest for: {config}")
            result = self.discovery_engine.backtest_config(config)

            if result is None:
                return False, "❌ Backtest failed - no data found for this configuration", None

            # Format results
            results_msg = f"""
✅ **Backtest Complete!**

**Results:**
- Total Trades: {result.total_trades}
- Win Rate: {result.win_rate:.1f}%
- Avg R: {result.avg_r:+.3f}R
- Annual Trades: {result.annual_trades}
- Tier: {result.tier}
- Total R: {result.total_r:+.1f}R
"""

            # Check if profitable
            is_profitable = result.avg_r > 0 and result.total_trades >= 10

            if is_profitable:
                # Create edge candidate
                candidate_id = create_edge_candidate_from_backtest(
                    instrument=params["instrument"],
                    orb_time=params["orb_time"],
                    rr=params["rr"],
                    sl_mode=params["sl_mode"],
                    orb_size_filter=params.get("orb_size_filter"),
                    backtest_result={
                        "win_rate": result.win_rate,
                        "avg_r": result.avg_r,
                        "annual_trades": result.annual_trades,
                        "tier": result.tier,
                        "total_r": result.total_r,
                        "total_trades": result.total_trades
                    },
                    hypothesis=params.get("hypothesis", "AI-discovered strategy"),
                    test_window_start=params.get("test_start", "2024-01-01"),
                    test_window_end=params.get("test_end", "2026-01-10")
                )

                results_msg += f"""
🎯 **Edge Candidate Created!**
- Candidate ID: #{candidate_id}
- This strategy is PROFITABLE and ready for review
- Go to "Edge Candidates" panel to approve and promote to production
"""
                return True, results_msg, candidate_id

            else:
                results_msg += """
⚠️ **Not Profitable**
This configuration didn't meet profitability criteria (avg R ≤ 0 or < 10 trades).
Try adjusting parameters:
- Different RR multiple
- Add/remove ORB size filter
- Try HALF vs FULL stop
"""
                return True, results_msg, None

        except Exception as e:
            logger.error(f"Error executing discovery: {e}", exc_info=True)
            return False, f"❌ Discovery execution error: {str(e)}", None

    def chat_with_execution(
        self,
        user_message: str,
        conversation_history: List[Dict],
        auto_execute: bool = True
    ) -> Tuple[str, Optional[Dict]]:
        """
        Chat with strategy advisor and optionally execute discovery.

        Args:
            user_message: User's message
            conversation_history: Previous messages
            auto_execute: If True, auto-execute when strategy is ready

        Returns:
            (assistant_response: str, execution_result: Optional[Dict])
        """
        if not self.api_key:
            return "AI assistant not configured. Add ANTHROPIC_API_KEY to .env", None

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)

            # Build conversation context
            full_conversation = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}"
                for msg in conversation_history[-10:]  # Last 10 messages
            ])
            full_conversation += f"\nUSER: {user_message}"

            # Check if user wants to execute
            execute_keywords = ["test this", "run it", "backtest", "let's try", "execute", "test it", "run backtest"]
            wants_to_execute = any(keyword in user_message.lower() for keyword in execute_keywords)

            # System prompt for strategy advisor
            system_prompt = """You are a professional trading strategy advisor specializing in ORB (Opening Range Breakout) strategies for futures trading.

Your role:
1. Discuss strategy ideas naturally with the trader
2. Help refine parameters: instrument (MGC/NQ/MPL), ORB time, RR ratio, stop mode, filters
3. When the trader is ready to test, you'll organize the plan and execute the backtest
4. Present results clearly and suggest improvements

Available instruments:
- MGC (Micro Gold): Best for ORB strategies, RR 1.5-8.0 works well
- NQ (Micro Nasdaq): Tight moves, RR 1.0 only practical
- MPL (Micro Platinum): Similar to NQ, tight moves

Available ORB times:
- 0900, 1000, 1100 (Day ORBs)
- 1800, 2300, 0030 (Night ORBs)

Stop modes:
- FULL: Stop at ORB low/high (wider)
- HALF: Stop at ORB mid (tighter, better for narrow ORBs)

ORB size filters: % of ATR (e.g., 0.155 = ORB must be < 15.5% of ATR)

Be concise, practical, and helpful. When discussing backtests, mention you can execute them immediately."""

            # Add execution hint if user wants to execute
            if wants_to_execute:
                system_prompt += "\n\nThe user wants to execute a backtest. Extract parameters and confirm before execution."

            # Call Claude
            messages = [{"role": "user", "content": system_prompt + "\n\n" + full_conversation}]

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=messages
            )

            assistant_response = response.content[0].text.strip()

            # Check if we should auto-execute
            execution_result = None
            if wants_to_execute and auto_execute:
                # Extract parameters
                params = self.extract_strategy_params(full_conversation)

                if params:
                    # Execute discovery
                    success, exec_msg, candidate_id = self.execute_discovery(params)

                    execution_result = {
                        "success": success,
                        "message": exec_msg,
                        "candidate_id": candidate_id,
                        "params": params
                    }

                    # Append execution results to response
                    assistant_response += "\n\n" + exec_msg

            return assistant_response, execution_result

        except Exception as e:
            logger.error(f"Error in chat_with_execution: {e}", exc_info=True)
            return f"Error: {str(e)}", None
