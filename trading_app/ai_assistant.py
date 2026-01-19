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
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY found in environment. AI chat disabled.")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info("AI assistant initialized (AI Source Lock enabled)")

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

    def _build_evidence_pack(
        self,
        instrument: str,
        strategy_state: Dict,
        current_price: float,
        session_levels: Dict,
        orb_data: Dict
    ) -> Optional[EvidencePack]:
        """
        Build EvidencePack from current context.

        This is the core evidence assembly function - converts live trading context
        into the Evidence Pack format required by the AI guard.
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

            # Build facts from current state
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

            # Build evidence pack
            evidence_pack = EvidencePack(
                instrument=instrument,
                timeframe="1m",  # Default timeframe
                candle_tables_used=["bars_1m", "bars_5m", "daily_features", "validated_setups"],
                ts_utc_start=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),  # Today
                ts_utc_end=datetime.utcnow(),
                setup_rows_used=setup_rows,
                engine_eval=engine_eval,
                facts=facts,
                queries=["SELECT FROM validated_setups WHERE instrument=?", "SELECT FROM daily_features", "SELECT FROM bars_1m"],
                current_price=current_price if current_price > 0 else None,
                session_levels=session_levels if session_levels else None,
                orb_data=orb_data if orb_data else None
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
            # Build evidence pack from context
            evidence_pack = self._build_evidence_pack(
                instrument=instrument,
                strategy_state=strategy_state or {},
                current_price=current_price,
                session_levels=session_levels or {},
                orb_data=orb_data or {}
            )

            # Log evidence pack creation for audit
            if evidence_pack:
                logger.info(f"Evidence pack built: instrument={instrument}, status={evidence_pack.engine_eval.status}, facts={len(evidence_pack.facts)}")
            else:
                logger.warning("Failed to build evidence pack")

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
