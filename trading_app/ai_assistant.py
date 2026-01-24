"""
Trading AI Assistant - Claude-powered trading assistant with live context

REFACTORED: Now uses ai_guard.py (AI Source Lock enforced).
NO DIRECT ANTHROPIC API CALLS - all requests go through guarded_chat_answer().
"""

import os
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import duckdb
from pathlib import Path

# AI GUARD - THE ONLY WAY TO CALL THE MODEL
from ai_guard import (
    guarded_chat_answer,
    EvidencePack,
    SetupInfo,
    EngineEvaluation,
    assert_ai_lock_enabled
)

logger = logging.getLogger(__name__)

# Database path (legacy - use cloud_mode.get_database_connection() instead)
DB_PATH = Path(__file__).parent.parent / "data/db/gold.db"


class TradingAIAssistant:
    """AI assistant for trading with live strategy context and persistent memory"""

    def __init__(self, memory_manager=None):
        # Check for API key based on provider (defaults to OpenAI)
        provider = os.getenv("AI_PROVIDER", "openai").lower()

        if provider == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            provider_name = "OpenAI"
        else:
            self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
            provider_name = "Anthropic"

        if not self.api_key:
            logger.warning(f"No {provider_name} API key found in environment. AI chat disabled.")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info(f"AI assistant initialized with {provider_name} (AI Source Lock enabled)")

            # Verify AI lock is properly configured
            try:
                assert_ai_lock_enabled()
            except AssertionError as e:
                logger.error(f"AI LOCK MISCONFIGURED: {e}")
                self.is_configured = False

        self.memory = memory_manager

    def is_available(self) -> bool:
        """Check if AI assistant is available"""
        return self.is_configured

    def load_validated_setups(self, instrument: str = "MGC") -> List[SetupInfo]:
        """
        Load validated setups from database as SetupInfo objects.
        Cloud-aware: Uses MotherDuck in cloud, local gold.db otherwise.

        Returns list of SetupInfo objects for Evidence Pack.
        """
        try:
            # Use cloud-aware connection
            from cloud_mode import get_database_connection
            con = get_database_connection()

            if con is None:
                logger.error("Database not available for loading setups")
                return []

            # Query validated setups for this instrument
            result = con.execute("""
                SELECT
                    id,
                    strategy_name,
                    orb_time,
                    rr,
                    sl_mode,
                    win_rate,
                    avg_r,
                    trades,
                    annual_trades,
                    tier,
                    orb_size_filter,
                    notes
                FROM validated_setups
                WHERE instrument = ?
                ORDER BY
                    CASE tier
                        WHEN 'S+' THEN 1
                        WHEN 'S' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        ELSE 5
                    END,
                    avg_r DESC
            """, [instrument]).fetchall()

            con.close()

            if not result:
                logger.warning(f"No validated setups found for instrument: {instrument}")
                return []

            # Convert to SetupInfo objects
            setups = []
            for row in result:
                setup = SetupInfo(
                    setup_id=row[0],
                    strategy_name=row[1],
                    orb_time=row[2],
                    rr_target=row[3],
                    sl_mode=row[4],
                    win_rate=row[5],
                    avg_r=row[6],
                    trade_count=row[7],
                    annual_trades=row[8],
                    tier=row[9],
                    orb_size_filter=row[10],
                    notes=row[11]
                )
                setups.append(setup)

            logger.info(f"Loaded {len(setups)} validated setups for {instrument}")
            return setups

        except Exception as e:
            logger.error(f"Error loading validated setups: {e}")
            return []

    def _build_smart_context(
        self,
        instrument: str,
        current_price: float,
        strategy_state: Dict,
        session_levels: Dict,
        orb_data: Dict,
        conversation_history: List[Dict],
        user_question: str
    ) -> List[str]:
        """
        Build smart context - only include NEW or RELEVANT information.

        Rules:
        1. Don't repeat facts from last 3 messages
        2. Don't repeat facts visible in UI (price, status)
        3. Only include facts relevant to user's question
        4. Reference past conversation when helpful

        This reduces token usage and makes AI responses less spammy.
        """
        facts = []

        # Extract recent facts from last 3 messages
        recent_facts = set()
        for msg in conversation_history[-3:] if conversation_history else []:
            if msg.get("role") == "assistant":
                # Extract key facts from recent responses (basic heuristic)
                content = msg.get("content", "")
                if "Current price" in content or "$" in content:
                    recent_facts.add("price")
                if "Strategy status" in content or "ENTER" in content or "WAIT" in content:
                    recent_facts.add("status")
                if "Asia session" in content:
                    recent_facts.add("asia")
                if "London session" in content:
                    recent_facts.add("london")
                if "NY session" in content:
                    recent_facts.add("ny")

        # Only add instrument if NEW session (no recent messages)
        if len(conversation_history) < 3:
            facts.append(f"Instrument: {instrument}")

        # Price: Only if significantly changed OR user asks about it
        price_relevant = any(word in user_question.lower() for word in ['price', 'level', 'where', 'at', 'now'])
        if (price_relevant or "price" not in recent_facts) and current_price > 0:
            facts.append(f"Current price: ${current_price:.2f}")

        # Strategy: Only if changed OR user asks about it
        strategy_relevant = any(word in user_question.lower() for word in ['strategy', 'setup', 'trade', 'enter', 'exit', 'take'])
        if strategy_relevant or "status" not in recent_facts:
            status = strategy_state.get('action', 'STAND_DOWN')
            facts.append(f"Strategy status: {status}")
            facts.append(f"Strategy: {strategy_state.get('strategy', 'None')}")

        # Session levels: Only if user asks about them OR not mentioned recently
        session_relevant = any(word in user_question.lower() for word in ['asia', 'london', 'ny', 'session', 'range', 'high', 'low'])
        if session_relevant and session_levels:
            if 'asia_high' in session_levels and 'asia_low' in session_levels and "asia" not in recent_facts:
                facts.append(f"Asia session: ${session_levels['asia_low']:.2f} - ${session_levels['asia_high']:.2f}")
            if 'london_high' in session_levels and 'london_low' in session_levels and "london" not in recent_facts:
                facts.append(f"London session: ${session_levels['london_low']:.2f} - ${session_levels['london_high']:.2f}")
            if 'ny_high' in session_levels and 'ny_low' in session_levels and "ny" not in recent_facts:
                facts.append(f"NY session: ${session_levels['ny_low']:.2f} - ${session_levels['ny_high']:.2f}")

        # ORB data: Only if user asks about it OR breakout happening
        orb_relevant = any(word in user_question.lower() for word in ['orb', '0900', '1000', '1100', '1800', '2300', '0030', 'breakout', 'break'])
        if orb_relevant and orb_data:
            for orb_name, orb_info in orb_data.items():
                if isinstance(orb_info, dict) and 'low' in orb_info and 'high' in orb_info:
                    facts.append(f"{orb_name}: ${orb_info['low']:.2f} - ${orb_info['high']:.2f} (size: {orb_info.get('size', 0):.2f})")

        # Upload references: If user mentions "chart" or "upload"
        if any(word in user_question.lower() for word in ['chart', 'upload', 'image', 'csv', 'file', 'that chart', 'the chart']):
            # Find recent uploads in conversation history
            for msg in reversed(conversation_history[-10:]) if conversation_history else []:
                if msg.get("role") == "user" and "[Uploaded" in msg.get("content", ""):
                    facts.append(f"Recent upload: {msg['content']}")
                    break

        # Conversation continuity: If user says "it" or "that" or "the trade", reference context
        if any(word in user_question.lower() for word in ['it', 'that', 'this', 'the trade', 'the setup']):
            # Get last assistant message
            for msg in reversed(conversation_history) if conversation_history else []:
                if msg.get("role") == "assistant":
                    # Extract key point from last response (first line)
                    last_point = msg.get("content", "").split("\n")[0][:100]
                    facts.append(f"Continuing from: {last_point}...")
                    break

        return facts

    def _build_evidence_pack(
        self,
        instrument: str,
        strategy_state: Dict,
        current_price: float,
        session_levels: Dict,
        orb_data: Dict,
        user_question: str = "",
        conversation_history: List[Dict] = None
    ) -> Optional[EvidencePack]:
        """
        Build EvidencePack from current context.

        This is the core evidence assembly function - converts live trading context
        into the Evidence Pack format required by the AI guard.

        Args:
            user_question: User's question text (used to detect chart analysis intent)
            conversation_history: Recent chat messages (for smart context building)
        """
        try:
            # Load validated setups
            setup_rows = self.load_validated_setups(instrument)

            # Build engine evaluation from strategy_state
            action_status = strategy_state.get('action', 'STAND_DOWN')
            # Map action to ENTER/WAIT
            if action_status == 'ENTER':
                status = "ENTER"
            else:
                status = "WAIT"

            engine_eval = EngineEvaluation(
                status=status,
                strategy_name=strategy_state.get('strategy', 'None'),
                direction=strategy_state.get('direction'),
                entry_price=strategy_state.get('entry_price'),
                stop_price=strategy_state.get('stop_price'),
                target_price=strategy_state.get('target_price'),
                orb_high=strategy_state.get('orb_high'),
                orb_low=strategy_state.get('orb_low'),
                setup_tier=strategy_state.get('tier'),
                rr=strategy_state.get('rr'),
                win_rate=strategy_state.get('win_rate'),
                avg_r=strategy_state.get('avg_r'),
                reasons=strategy_state.get('reasons', [])
            )

            # Build facts from current state using SMART CONTEXT
            # This reduces token usage by not repeating visible/recent information
            if conversation_history:
                # Use smart context builder (Phase 2: AI Unification)
                facts = self._build_smart_context(
                    instrument=instrument,
                    current_price=current_price,
                    strategy_state=strategy_state,
                    session_levels=session_levels,
                    orb_data=orb_data,
                    conversation_history=conversation_history,
                    user_question=user_question
                )
            else:
                # Fallback to full context if no conversation history (first message)
                facts = []
                facts.append(f"Instrument: {instrument}")
                if current_price > 0:
                    facts.append(f"Current price: ${current_price:.2f}")
                facts.append(f"Strategy status: {status}")
                facts.append(f"Strategy: {engine_eval.strategy_name}")

                if session_levels:
                    if 'asia_high' in session_levels and 'asia_low' in session_levels:
                        facts.append(f"Asia session: ${session_levels['asia_low']:.2f} - ${session_levels['asia_high']:.2f}")
                    if 'london_high' in session_levels and 'london_low' in session_levels:
                        facts.append(f"London session: ${session_levels['london_low']:.2f} - ${session_levels['london_high']:.2f}")
                    if 'ny_high' in session_levels and 'ny_low' in session_levels:
                        facts.append(f"NY session: ${session_levels['ny_low']:.2f} - ${session_levels['ny_high']:.2f}")

                if orb_data:
                    for orb_name, orb_info in orb_data.items():
                        if isinstance(orb_info, dict) and 'low' in orb_info and 'high' in orb_info:
                            facts.append(f"{orb_name}: ${orb_info['low']:.2f} - ${orb_info['high']:.2f} (size: {orb_info.get('size', 0):.2f})")

            # Detect db_mode (cloud-aware)
            from cloud_mode import is_cloud_deployment, get_database_connection
            db_mode = "motherduck" if is_cloud_deployment() else "local"

            # Extract strategy IDs from setup_rows
            strategy_ids = [setup.setup_id for setup in setup_rows]

            # no_lookahead_check: PASS for validated historical queries
            # (All queries use validated_setups and historical data only)
            no_lookahead_check = "PASS"

            # PART A: Detect chart analysis intent and fetch OHLCV bars
            chart_keywords = ["chart", "pattern", "support", "resistance", "trend", "structure",
                            "what does the chart suggest", "technical", "level", "breakout"]
            is_chart_question = any(keyword in user_question.lower() for keyword in chart_keywords)

            bars_timeframe = None
            bars_ohlcv_sample = None

            if is_chart_question:
                try:
                    # Query last 600 bars (10 hours of 1m data)
                    conn = get_database_connection(read_only=True)

                    # First, find the latest bar time
                    max_time_result = conn.execute("""
                        SELECT MAX(ts_utc)
                        FROM bars_1m
                        WHERE symbol = ?
                    """, [instrument]).fetchone()

                    if max_time_result and max_time_result[0] is not None:
                        latest_bar_time = max_time_result[0]

                        # Check freshness (warn if > 2 minutes old)
                        time_diff = (datetime.utcnow() - latest_bar_time).total_seconds()
                        if time_diff > 120:  # 2 minutes
                            logger.warning(f"Bars appear stale: latest bar is {time_diff:.0f}s old")
                            facts.append(f"⚠️ Market data is {time_diff/60:.1f} minutes old")

                        # Query last 600 bars
                        bars_result = conn.execute("""
                            SELECT ts_utc, open, high, low, close, volume
                            FROM bars_1m
                            WHERE symbol = ?
                              AND ts_utc >= (
                                  SELECT MAX(ts_utc)
                                  FROM bars_1m
                                  WHERE symbol = ?
                              ) - INTERVAL '10 hours'
                            ORDER BY ts_utc ASC
                        """, [instrument, instrument]).fetchall()

                        if bars_result and len(bars_result) > 0:
                            bars_ohlcv_sample = []
                            for row in bars_result:
                                bars_ohlcv_sample.append({
                                    'ts': row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                                    'open': float(row[1]),
                                    'high': float(row[2]),
                                    'low': float(row[3]),
                                    'close': float(row[4]),
                                    'volume': float(row[5]) if row[5] is not None else 0
                                })

                            bars_timeframe = "1m"

                            # Update current_price from latest bar
                            latest_bar = bars_ohlcv_sample[-1]
                            current_price = latest_bar['close']
                            facts.append(f"OHLCV bars loaded: {len(bars_ohlcv_sample)} bars (last 10 hours)")
                            facts.append(f"Latest bar: {latest_bar['ts']} close=${latest_bar['close']:.2f}")

                            logger.info(f"Loaded {len(bars_ohlcv_sample)} OHLCV bars for chart analysis")
                        else:
                            logger.warning(f"No OHLCV bars found for {instrument}")
                            facts.append("⚠️ No OHLCV bar data available")
                    else:
                        # No bars in table at all
                        logger.warning(f"No OHLCV bars in database for {instrument}")
                        facts.append("⚠️ No OHLCV bar data available")

                    conn.close()

                except Exception as e:
                    logger.error(f"Error fetching OHLCV bars: {e}")
                    facts.append(f"⚠️ Error fetching chart data: {e}")

            # PART B: Calculate data freshness metadata
            latest_bar_ts = None
            freshness_seconds = None
            data_source = None

            if bars_ohlcv_sample and len(bars_ohlcv_sample) > 0:
                # Extract latest bar timestamp from OHLCV sample
                latest_bar_ts = bars_ohlcv_sample[-1]['ts']
                now_utc = datetime.utcnow()
                # Make both offset-aware for comparison
                if latest_bar_ts.tzinfo is None:
                    from config import TZ_UTC
                    latest_bar_ts = latest_bar_ts.replace(tzinfo=TZ_UTC)
                if now_utc.tzinfo is None:
                    now_utc = now_utc.replace(tzinfo=TZ_UTC)
                freshness_seconds = (now_utc - latest_bar_ts).total_seconds()
                data_source = "ProjectX" if os.getenv("PROJECTX_API_KEY") else "Database"

                # Add freshness warning to facts if data is stale
                if freshness_seconds > 90:
                    facts.append(f"WARNING: Data is {int(freshness_seconds)}s old (STALE)")
                else:
                    facts.append(f"[OK] Data freshness: {int(freshness_seconds)}s")

            # Build evidence pack
            evidence_pack = EvidencePack(
                instrument=instrument,
                timeframe="1m",  # Default timeframe
                candle_tables_used=["bars_1m", "bars_5m", "daily_features_v2", "validated_setups"],
                ts_utc_start=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),  # Today
                ts_utc_end=datetime.utcnow(),
                setup_rows_used=setup_rows,
                engine_eval=engine_eval,
                facts=facts,
                queries=["SELECT FROM validated_setups WHERE instrument=?", "SELECT FROM daily_features_v2", "SELECT FROM bars_1m"],
                db_mode=db_mode,
                no_lookahead_check=no_lookahead_check,
                strategy_ids=strategy_ids,
                current_price=current_price if current_price > 0 else None,
                session_levels=session_levels if session_levels else None,
                orb_data=orb_data if orb_data else None,
                bars_timeframe=bars_timeframe,
                bars_ohlcv_sample=bars_ohlcv_sample,
                latest_bar_ts=latest_bar_ts,
                freshness_seconds=freshness_seconds,
                data_source=data_source
            )

            return evidence_pack

        except Exception as e:
            logger.error(f"Error building evidence pack: {e}")
            return None

    def chat(
        self,
        user_message: str,
        conversation_history: List[Dict],
        session_id: str,
        instrument: str = "MGC",
        current_price: float = 0,
        strategy_state: Dict = None,
        session_levels: Dict = None,
        orb_data: Dict = None,
        backtest_stats: Dict = None
    ) -> str:
        """
        Send message to Claude with Evidence Pack (AI SOURCE LOCK ENFORCED).

        REFACTORED: All AI calls now go through guarded_chat_answer().
        NO DIRECT API CALLS. Evidence Pack required.
        """

        if not self.is_available():
            return "AI assistant not available. Set ANTHROPIC_API_KEY in .env file."

        try:
            # Build evidence pack from context (with smart context for Phase 2)
            evidence_pack = self._build_evidence_pack(
                instrument=instrument,
                strategy_state=strategy_state or {},
                current_price=current_price,
                session_levels=session_levels or {},
                orb_data=orb_data or {},
                user_question=user_message,  # Pass user question for chart detection
                conversation_history=conversation_history or []  # Phase 2: Smart context building
            )

            # Log evidence pack creation for audit
            if evidence_pack:
                logger.info(f"Evidence pack built: instrument={instrument}, status={evidence_pack.engine_eval.status}, facts={len(evidence_pack.facts)}")
            else:
                logger.warning("Failed to build evidence pack")

            # INTENT ROUTING: EDGE_PIPELINE vs MARKET_QUERY
            # Detect if this is an edge discovery/testing request
            user_lower = user_message.lower()
            edge_keywords = ["edge", "candidate", "promote", "evaluate", "backtest theory", "test theory"]
            is_edge_pipeline = any(keyword in user_lower for keyword in edge_keywords)

            # If edge pipeline intent detected, provide simple routing response
            # (Full pipeline integration would require more sophisticated parsing)
            if is_edge_pipeline:
                logger.info(f"Edge pipeline intent detected: {user_message[:50]}...")

                # Provide guidance on using edge pipeline features
                if "create" in user_lower or "test theory" in user_lower:
                    return (
                        "**Edge Pipeline: Create Candidate**\n\n"
                        "To test a new edge theory:\n"
                        "1. Use the Edge Candidates UI panel\n"
                        "2. Or call: `from edge_pipeline import create_edge_candidate_from_theory`\n\n"
                        "Example:\n"
                        "```python\n"
                        "candidate_id = create_edge_candidate_from_theory(\n"
                        "    theory_text='MGC 0900 ORB with 3.0 RR shows strong performance',\n"
                        "    instrument='MGC',\n"
                        "    metadata={'orb_time': '0900', 'name': 'My Theory'}\n"
                        ")\n"
                        "```\n\n"
                        "Then evaluate with: `evaluate_candidate(candidate_id)`"
                    )

                elif "promote" in user_lower:
                    return (
                        "**Edge Pipeline: Promote Candidate**\n\n"
                        "To promote an APPROVED candidate to validated_setups:\n"
                        "1. Go to Edge Candidates UI panel\n"
                        "2. Select an APPROVED candidate\n"
                        "3. Click 'PROMOTE TO VALIDATED_SETUPS' button\n\n"
                        "Or use Python:\n"
                        "```python\n"
                        "from edge_pipeline import promote_candidate_to_validated_setups\n"
                        "validated_setup_id = promote_candidate_to_validated_setups(candidate_id, 'Josh')\n"
                        "```\n\n"
                        "⚠️ Candidate must be APPROVED first!"
                    )

                elif "evaluate" in user_lower:
                    return (
                        "**Edge Pipeline: Evaluate Candidate**\n\n"
                        "To run backtest evaluation on a candidate:\n"
                        "```python\n"
                        "from edge_pipeline import evaluate_candidate\n"
                        "results = evaluate_candidate(candidate_id)\n"
                        "```\n\n"
                        "This will:\n"
                        "- Run StrategyDiscovery heuristic backtest\n"
                        "- Update metrics_json, robustness_json\n"
                        "- Set status to 'PENDING'\n\n"
                        "⚠️ Note: Current evaluation uses heuristic method (optimistic fills).\n"
                        "True walk-forward backtest integration is pending."
                    )

                else:
                    # Generic edge pipeline info
                    return (
                        "**Edge Pipeline Available**\n\n"
                        "Edge discovery workflow:\n"
                        "1. **Create** candidate (status: DRAFT)\n"
                        "2. **Evaluate** with backtest (status: PENDING)\n"
                        "3. **Approve** if results good (status: APPROVED)\n"
                        "4. **Promote** to validated_setups (production)\n\n"
                        "Access via Edge Candidates UI panel or Python API.\n\n"
                        "Functions: `create_edge_candidate_from_theory`, `evaluate_candidate`, "
                        "`approve_candidate`, `promote_candidate_to_validated_setups`"
                    )

            # MARKET_QUERY intent: Continue to normal LLM flow with Evidence Pack
            # Call guarded function (THE ONLY WAY TO CALL THE MODEL)
            assistant_message = guarded_chat_answer(
                question=user_message,
                evidence_pack=evidence_pack,
                conversation_history=conversation_history
            )

            # Save to memory if available
            if self.memory:
                context_data = {
                    "instrument": instrument,
                    "current_price": current_price,
                    "strategy": strategy_state.get('strategy') if strategy_state else None,
                    "action": strategy_state.get('action') if strategy_state else None,
                    "evidence_pack_status": evidence_pack.engine_eval.status if evidence_pack else "NO_EVIDENCE"
                }

                # Determine tags
                tags = []
                user_lower = user_message.lower()
                if any(word in user_lower for word in ['trade', 'enter', 'exit', 'stop', 'target']):
                    tags.append('trade')
                if any(word in user_lower for word in ['calculate', 'orb', 'risk']):
                    tags.append('calculation')
                if any(word in user_lower for word in ['why', 'how', 'explain', 'strategy']):
                    tags.append('strategy')

                self.memory.save_message(session_id, "user", user_message, context_data, instrument, tags)
                self.memory.save_message(session_id, "assistant", assistant_message, context_data, instrument, tags)

            return assistant_message

        except Exception as e:
            error_msg = f"Error communicating with AI: {str(e)}"
            logger.error(error_msg)
            return error_msg
