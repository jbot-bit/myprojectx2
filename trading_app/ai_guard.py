"""
AI GUARD - SINGLE CHOKE POINT FOR ALL AI/LLM CALLS

This module enforces the "AI Source Lock" - ensuring the AI can ONLY answer
using our database + engine outputs, never general trading knowledge.

CRITICAL RULES:
1. NO other file may call the Anthropic API directly
2. ALL AI calls MUST go through guarded_chat_answer()
3. Evidence Pack is MANDATORY - no evidence = no answer
4. Trade recommendations ONLY if engine_eval.status == "ENTER"
5. Fail-closed: missing data = hard refusal (never infer/estimate)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# LOCKED SYSTEM PROMPT PATH (must exist)
LOCKED_PROMPT_PATH = Path(__file__).parent / "prompts" / "LOCKED_SYSTEM_PROMPT.txt"


@dataclass
class SetupInfo:
    """Validated setup information from database."""
    setup_id: int
    strategy_name: str
    orb_time: str
    rr_target: float
    sl_mode: str
    tier: str
    win_rate: float
    avg_r: float
    trade_count: int
    annual_trades: int
    orb_size_filter: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class EngineEvaluation:
    """Strategy engine evaluation output."""
    status: str  # "WAIT" or "ENTER" (from ActionType)
    strategy_name: str
    direction: Optional[str] = None  # "LONG" or "SHORT"
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    orb_high: Optional[float] = None
    orb_low: Optional[float] = None
    setup_tier: Optional[str] = None
    rr: Optional[float] = None
    win_rate: Optional[float] = None
    avg_r: Optional[float] = None
    reasons: List[str] = field(default_factory=list)


@dataclass
class EvidencePack:
    """
    MANDATORY input for all AI calls.
    Contains ONLY data from our DB + engines (no external knowledge).

    Missing fields = refusal (fail-closed).
    """
    # Core identifiers
    instrument: str
    timeframe: str  # e.g., "1m", "5m"

    # Data source info
    candle_tables_used: List[str]  # e.g., ["bars_1m", "bars_5m"]
    ts_utc_start: datetime
    ts_utc_end: datetime

    # Strategy data
    setup_rows_used: List[SetupInfo]  # From validated_setups table
    engine_eval: EngineEvaluation  # From strategy_engine

    # Facts derived from DB/code only
    facts: List[str]  # Atomic statements (no speculation)

    # Query audit trail
    queries: List[str]  # Sanitized SQL or query descriptors

    # Optional market data context
    current_price: Optional[float] = None
    session_levels: Optional[Dict[str, float]] = None  # Asia/London/NY highs/lows
    orb_data: Optional[Dict[str, Any]] = None  # Current ORB ranges

    def is_complete(self) -> bool:
        """Check if evidence pack has minimum required fields."""
        if not self.instrument or not self.timeframe:
            return False
        if not self.candle_tables_used or not self.ts_utc_start or not self.ts_utc_end:
            return False
        if not self.engine_eval:
            return False
        return True

    def missing_fields(self) -> List[str]:
        """Return list of missing/null required fields."""
        missing = []
        if not self.instrument:
            missing.append("instrument")
        if not self.timeframe:
            missing.append("timeframe")
        if not self.candle_tables_used:
            missing.append("candle_tables_used")
        if not self.ts_utc_start:
            missing.append("ts_utc_start")
        if not self.ts_utc_end:
            missing.append("ts_utc_end")
        if not self.engine_eval:
            missing.append("engine_eval")
        if not self.facts:
            missing.append("facts")
        return missing


def validate_evidence_pack(evidence_pack: Optional[EvidencePack], user_question: str) -> tuple[bool, Optional[str]]:
    """
    FAIL-CLOSED GATE: Validates evidence pack before allowing AI call.

    Returns:
        (is_valid, refusal_message)
        - If valid: (True, None)
        - If invalid: (False, "refusal message")

    REJECTION RULES:
    1. No evidence pack -> reject
    2. Missing required fields -> reject
    3. Trade question but engine_eval.status != "ENTER" -> reject (no trade)
    4. Missing critical data for user request -> reject
    """

    # Rule 1: No evidence pack
    if evidence_pack is None:
        return False, _format_refusal(
            "No Evidence Pack provided",
            ["evidence_pack"],
            [],
            "Load data from database and create Evidence Pack"
        )

    # Rule 2: Missing required fields
    if not evidence_pack.is_complete():
        missing = evidence_pack.missing_fields()
        return False, _format_refusal(
            "Evidence Pack incomplete (missing required fields)",
            missing,
            evidence_pack.candle_tables_used or [],
            f"Provide: {', '.join(missing)}"
        )

    # Rule 3: Trade recommendation only if ENTER signal
    user_lower = user_question.lower()
    is_trade_question = any(word in user_lower for word in [
        'should i trade', 'take this trade', 'enter', 'buy', 'sell', 'long', 'short',
        'recommend', 'trade this', 'good trade'
    ])

    if is_trade_question:
        if evidence_pack.engine_eval.status != "ENTER":
            # Build facts about why no trade
            facts = [
                f"Strategy: {evidence_pack.engine_eval.strategy_name}",
                f"Status: {evidence_pack.engine_eval.status} (not ENTER)",
            ]
            if evidence_pack.engine_eval.reasons:
                facts.extend(evidence_pack.engine_eval.reasons)

            return False, _format_no_trade_refusal(facts, evidence_pack.candle_tables_used)

    # Rule 4: Check for missing setup data if needed
    if is_trade_question and not evidence_pack.setup_rows_used:
        return False, _format_refusal(
            "No validated setups available for this instrument/strategy",
            ["setup_rows_used"],
            evidence_pack.candle_tables_used,
            "Query validated_setups table for strategy parameters"
        )

    # Rule 5: Missing entry/stop/target for ENTER signal
    if evidence_pack.engine_eval.status == "ENTER":
        missing_trade_fields = []
        if evidence_pack.engine_eval.entry_price is None:
            missing_trade_fields.append("entry_price")
        if evidence_pack.engine_eval.stop_price is None:
            missing_trade_fields.append("stop_price")
        if evidence_pack.engine_eval.target_price is None:
            missing_trade_fields.append("target_price")

        if missing_trade_fields:
            return False, _format_refusal(
                "ENTER signal but missing trade execution prices",
                missing_trade_fields,
                evidence_pack.candle_tables_used,
                "strategy_engine must provide entry/stop/target for ENTER signals"
            )

    # All validations passed
    return True, None


def _format_refusal(reason: str, missing: List[str], sources: List[str], next_action: str) -> str:
    """Format standardized refusal message (EXACT FORMAT)."""
    sources_str = ", ".join(sources) if sources else "none"
    missing_str = ", ".join(missing) if missing else "none"

    return f"""DECISION: NOT AVAILABLE
REASON: {reason}
MISSING: {missing_str}
SOURCES USED: {sources_str}
NEXT ACTION: {next_action}"""


def _format_no_trade_refusal(facts: List[str], sources: List[str]) -> str:
    """Format NO TRADE refusal when engine says WAIT."""
    sources_str = ", ".join(sources) if sources else "none"
    facts_str = "\n".join(f"  • {fact}" for fact in facts)

    return f"""DECISION: NO TRADE (WAIT)
REASON: Strategy engine status is not ENTER

FACTS FROM ENGINE:
{facts_str}

SOURCES USED: {sources_str}
NEXT ACTION: Wait for strategy conditions to align, or check different setup"""


def _load_locked_prompt() -> str:
    """Load the locked system prompt from file (MUST exist)."""
    if not LOCKED_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"LOCKED_SYSTEM_PROMPT.txt not found at {LOCKED_PROMPT_PATH}. "
            "AI Source Lock misconfigured!"
        )

    return LOCKED_PROMPT_PATH.read_text(encoding='utf-8')


def _format_evidence_for_prompt(evidence_pack: EvidencePack) -> str:
    """Format evidence pack into structured prompt section."""

    # Header
    output = ["=" * 60]
    output.append("EVIDENCE PACK (YOUR ONLY SOURCE OF TRUTH)")
    output.append("=" * 60)
    output.append("")

    # Basic info
    output.append(f"INSTRUMENT: {evidence_pack.instrument}")
    output.append(f"TIMEFRAME: {evidence_pack.timeframe}")
    output.append(f"DATA PERIOD: {evidence_pack.ts_utc_start} to {evidence_pack.ts_utc_end}")
    output.append(f"TABLES USED: {', '.join(evidence_pack.candle_tables_used)}")
    output.append("")

    # Current market data
    if evidence_pack.current_price:
        output.append(f"CURRENT PRICE: ${evidence_pack.current_price:.2f}")

    if evidence_pack.session_levels:
        output.append("\nSESSION LEVELS:")
        for session, value in evidence_pack.session_levels.items():
            output.append(f"  • {session}: ${value:.2f}")

    if evidence_pack.orb_data:
        output.append("\nORB DATA:")
        for orb_name, orb_info in evidence_pack.orb_data.items():
            if isinstance(orb_info, dict):
                output.append(f"  • {orb_name}: ${orb_info.get('low', 0):.2f} - ${orb_info.get('high', 0):.2f} (size: {orb_info.get('size', 0):.2f})")

    output.append("")

    # Strategy engine evaluation
    output.append("STRATEGY ENGINE EVALUATION:")
    output.append(f"  Status: {evidence_pack.engine_eval.status}")
    output.append(f"  Strategy: {evidence_pack.engine_eval.strategy_name}")

    if evidence_pack.engine_eval.status == "ENTER":
        output.append(f"  Direction: {evidence_pack.engine_eval.direction}")
        output.append(f"  Entry: ${evidence_pack.engine_eval.entry_price:.2f}")
        output.append(f"  Stop: ${evidence_pack.engine_eval.stop_price:.2f}")
        output.append(f"  Target: ${evidence_pack.engine_eval.target_price:.2f}")
        if evidence_pack.engine_eval.orb_high and evidence_pack.engine_eval.orb_low:
            output.append(f"  ORB Range: ${evidence_pack.engine_eval.orb_low:.2f} - ${evidence_pack.engine_eval.orb_high:.2f}")
        if evidence_pack.engine_eval.rr:
            output.append(f"  RR Target: {evidence_pack.engine_eval.rr:.1f}")
        if evidence_pack.engine_eval.win_rate:
            output.append(f"  Historical Win Rate: {evidence_pack.engine_eval.win_rate:.1f}%")
        if evidence_pack.engine_eval.avg_r:
            output.append(f"  Historical Avg R: {evidence_pack.engine_eval.avg_r:+.3f}R")

    if evidence_pack.engine_eval.reasons:
        output.append("  Reasons:")
        for reason in evidence_pack.engine_eval.reasons:
            output.append(f"    - {reason}")

    output.append("")

    # Validated setups
    if evidence_pack.setup_rows_used:
        output.append("VALIDATED SETUPS (FROM DATABASE):")
        for setup in evidence_pack.setup_rows_used:
            output.append(f"\n  Setup ID {setup.setup_id}: {setup.strategy_name}")
            output.append(f"    ORB Time: {setup.orb_time}")
            output.append(f"    Tier: {setup.tier} | RR: {setup.rr_target:.1f} | SL Mode: {setup.sl_mode}")
            output.append(f"    Win Rate: {setup.win_rate:.1f}% | Avg R: {setup.avg_r:+.3f}R")
            output.append(f"    Trade Count: {setup.trade_count} total (~{setup.annual_trades}/year)")
            if setup.orb_size_filter:
                output.append(f"    ORB Filter: <{setup.orb_size_filter:.3f}×ATR")
            if setup.notes:
                output.append(f"    Notes: {setup.notes}")

    output.append("")

    # Facts
    output.append("FACTS (DERIVED FROM DB/CODE):")
    for fact in evidence_pack.facts:
        output.append(f"  • {fact}")

    output.append("")

    # Query audit
    if evidence_pack.queries:
        output.append("QUERIES EXECUTED:")
        for query in evidence_pack.queries:
            output.append(f"  • {query}")

    output.append("")
    output.append("=" * 60)
    output.append("END EVIDENCE PACK")
    output.append("=" * 60)

    return "\n".join(output)


def guarded_chat_answer(
    question: str,
    evidence_pack: Optional[EvidencePack],
    conversation_history: List[Dict] = None
) -> str:
    """
    SINGLE CHOKE POINT for all AI/LLM calls.

    This function:
    1. Validates evidence pack (fail-closed gate)
    2. Loads locked system prompt
    3. Formats evidence pack into prompt
    4. Calls Claude API
    5. Returns response

    NO OTHER FILE MAY CALL THE ANTHROPIC API DIRECTLY.

    Args:
        question: User's question
        evidence_pack: Required evidence from DB + engines
        conversation_history: Previous messages (optional)

    Returns:
        AI response OR refusal message (if validation fails)
    """

    # GATE 1: Validate evidence pack (fail-closed)
    is_valid, refusal_msg = validate_evidence_pack(evidence_pack, question)
    if not is_valid:
        logger.warning(f"Evidence pack validation failed: {refusal_msg}")
        return refusal_msg

    # GATE 2: Load locked system prompt (must exist)
    try:
        locked_prompt = _load_locked_prompt()
    except FileNotFoundError as e:
        logger.error(f"AI Source Lock misconfigured: {e}")
        return "AI LOCK MISCONFIGURED: LOCKED_SYSTEM_PROMPT.txt not found. AI responses disabled."

    # GATE 3: Get API key and client
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not api_key:
        logger.error("No ANTHROPIC_API_KEY found in environment")
        return "AI assistant not available. Set ANTHROPIC_API_KEY in .env file."

    try:
        client = Anthropic(api_key=api_key)
    except Exception as e:
        logger.error(f"Error initializing Anthropic client: {e}")
        return f"Error initializing AI client: {e}"

    # Format evidence pack for prompt
    evidence_text = _format_evidence_for_prompt(evidence_pack)

    # Build system prompt: locked prompt + evidence pack
    system_prompt = f"""{locked_prompt}

{evidence_text}
"""

    # Build messages
    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": question})

    # Call Claude API (THE ONLY PLACE THIS HAPPENS)
    try:
        logger.info(f"Calling Claude API with evidence pack (instrument={evidence_pack.instrument}, status={evidence_pack.engine_eval.status})")

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        )

        assistant_message = response.content[0].text

        # Log for audit trail
        logger.info(f"AI response generated successfully (length={len(assistant_message)} chars)")

        return assistant_message

    except Exception as e:
        error_msg = f"Error communicating with AI: {str(e)}"
        logger.error(error_msg)
        return error_msg


def assert_ai_lock_enabled():
    """
    Runtime self-check: Verify AI Source Lock is properly configured.

    Call this on app startup to ensure:
    1. LOCKED_SYSTEM_PROMPT.txt exists
    2. No bypass patterns detected

    Raises:
        AssertionError: If AI lock is misconfigured
    """

    # Check 1: Locked prompt exists
    if not LOCKED_PROMPT_PATH.exists():
        raise AssertionError(
            f"AI LOCK MISCONFIGURED: LOCKED_SYSTEM_PROMPT.txt not found at {LOCKED_PROMPT_PATH}"
        )

    # Check 2: Locked prompt is not empty
    content = LOCKED_PROMPT_PATH.read_text(encoding='utf-8')
    if len(content.strip()) < 100:
        raise AssertionError(
            "AI LOCK MISCONFIGURED: LOCKED_SYSTEM_PROMPT.txt is too short or empty"
        )

    # Check 3: Locked prompt contains key enforcement phrases
    required_phrases = [
        "Evidence Pack",
        "ONLY use",
        "refuse",
        "NOT AVAILABLE"
    ]

    for phrase in required_phrases:
        if phrase not in content:
            raise AssertionError(
                f"AI LOCK MISCONFIGURED: LOCKED_SYSTEM_PROMPT.txt missing required phrase: '{phrase}'"
            )

    logger.info("✓ AI Source Lock verified: Locked prompt loaded and validated")
    return True
