"""
SETUP DETECTOR

Queries validated_setups database to detect ALL profitable setups,
including rare high-probability ones like:
- 1100 ORB (90% WR, only 31 trades/year)
- 2300 ORB with filters (72% WR)
- 1000 RR=3.0 with 2 confirmations (29% WR but +0.158R)

PHASE 1B INTEGRATION:
Now supports conditional edges based on market state (asia_bias, etc.)
Returns both active setups (conditions met NOW) and potential setups
(conditions not yet met, but possible if market moves).

The trading app calls this to check if current market conditions
match ANY validated setup criteria.
"""

import duckdb
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import logging
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class SetupDetector:
    """Detects validated high-probability trading setups."""

    def __init__(self, db_path: Optional[str] = None):
        # Cloud-aware: db_path parameter is ignored in cloud mode
        # Connections handled by get_database_connection()
        self.db_path = db_path  # Legacy parameter, kept for compatibility

        # Lazy connection - only connect when needed
        self._con = None

    def _get_connection(self):
        """Get database connection, creating it if needed (cloud-aware)"""
        if self._con is None:
            try:
                # Use cloud-aware connection
                from cloud_mode import get_database_connection
                self._con = get_database_connection()

                if self._con is None:
                    logger.warning("Database connection unavailable. Setup detection disabled.")
                    return None

                logger.info("Connected to database for setup detection")
            except Exception as e:
                logger.error(f"Error connecting to database: {e}")
                return None

        return self._con

    def get_all_validated_setups(self, instrument: str = "MGC") -> List[Dict]:
        """Get all validated setups for an instrument."""
        try:
            con = self._get_connection()
            if con is None:
                return []

            result = con.execute("""
                SELECT
                    instrument,
                    setup_id,
                    orb_time,
                    rr,
                    sl_mode,
                    close_confirmations,
                    buffer_ticks,
                    orb_size_filter,
                    atr_filter,
                    trades,
                    win_rate,
                    avg_r,
                    annual_trades,
                    tier,
                    notes
                FROM validated_setups
                WHERE instrument = ?
                ORDER BY
                    CASE tier
                        WHEN 'S+' THEN 1
                        WHEN 'S' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'C' THEN 5
                        ELSE 6
                    END,
                    avg_r DESC
            """, [instrument]).df()

            return result.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting validated setups: {e}")
            return []

    def check_orb_setup(
        self,
        instrument: str,
        orb_time: str,
        orb_size: float,
        atr_20: float,
        current_time: datetime
    ) -> List[Dict]:
        """
        Check if current ORB matches any validated setup criteria.

        Returns list of matching setups, sorted by tier (best first).
        """
        try:
            con = self._get_connection()
            if con is None:
                return []

            # Calculate orb_size as % of ATR
            if atr_20 and atr_20 > 0:
                orb_size_pct = orb_size / atr_20
            else:
                orb_size_pct = None

            # Find matching setups
            query = """
                SELECT
                    setup_id,
                    orb_time,
                    rr,
                    sl_mode,
                    close_confirmations,
                    buffer_ticks,
                    orb_size_filter,
                    win_rate,
                    avg_r,
                    tier,
                    notes
                FROM validated_setups
                WHERE instrument = ?
                  AND orb_time = ?
                  AND (orb_size_filter IS NULL OR ? <= orb_size_filter)
                ORDER BY
                    CASE tier
                        WHEN 'S+' THEN 1
                        WHEN 'S' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'C' THEN 5
                        ELSE 6
                    END,
                    avg_r DESC
            """

            result = con.execute(query, [instrument, orb_time, orb_size_pct]).df()

            matches = result.to_dict('records')

            if matches:
                logger.info(f"Found {len(matches)} validated setups for {instrument} {orb_time} ORB")
                for match in matches:
                    logger.info(f"  -> {match['tier']} tier: {match['win_rate']:.1f}% WR, {match['avg_r']:+.3f}R avg")

            return matches
        except Exception as e:
            logger.error(f"Error checking ORB setup: {e}")
            return []

    def get_elite_setups(self, instrument: str = "MGC") -> List[Dict]:
        """Get only S+ and S tier setups (elite performers)."""
        try:
            con = self._get_connection()
            if con is None:
                return []

            result = con.execute("""
                SELECT
                    setup_id,
                    orb_time,
                    rr,
                    sl_mode,
                    win_rate,
                    avg_r,
                    annual_trades,
                    tier,
                    notes,
                    quality_multiplier,
                    condition_type,
                    condition_value
                FROM validated_setups
                WHERE instrument = ?
                  AND tier IN ('S+', 'S')
                ORDER BY avg_r DESC
            """, [instrument]).df()

            return result.to_dict('records')
        except Exception as e:
            logger.error(f"Error getting elite setups: {e}")
            return []

    def get_conditional_setups(
        self,
        instrument: str,
        market_state: Dict[str, str],
        orb_time: Optional[str] = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get setups matching current market conditions.

        Args:
            instrument: Instrument symbol (e.g., 'MGC')
            market_state: Current market state from market_state.py
                         e.g., {'asia_bias': 'ABOVE', 'asia_high': 2650.0, ...}
            orb_time: Optional ORB time filter (e.g., '1000')

        Returns:
            Tuple of (active_setups, baseline_setups)
            - active_setups: Conditional setups matching current state
            - baseline_setups: Baseline setups (always available as fallback)

        Example:
            >>> state = {'asia_bias': 'ABOVE'}
            >>> active, baseline = detector.get_conditional_setups('MGC', state, '1000')
            >>> print(f"Active: {len(active)}, Baseline: {len(baseline)}")
        """
        try:
            con = self._get_connection()
            if con is None:
                return [], []

            # Build WHERE clause for conditional setups
            where_conditions = ["instrument = ?"]
            params = [instrument]

            if orb_time:
                where_conditions.append("orb_time = ?")
                params.append(orb_time)

            # Match conditions
            condition_clauses = []
            for cond_type, cond_value in market_state.items():
                if cond_value and cond_value != 'UNKNOWN':
                    condition_clauses.append(
                        f"(condition_type = '{cond_type}' AND condition_value = '{cond_value}')"
                    )

            if condition_clauses:
                where_conditions.append(f"({' OR '.join(condition_clauses)})")

            # Query conditional setups
            conditional_query = f"""
                SELECT
                    setup_id,
                    orb_time,
                    rr,
                    sl_mode,
                    close_confirmations,
                    win_rate,
                    avg_r,
                    tier,
                    notes,
                    quality_multiplier,
                    condition_type,
                    condition_value,
                    trades,
                    annual_trades
                FROM validated_setups
                WHERE {' AND '.join(where_conditions)}
                  AND condition_type IS NOT NULL
                ORDER BY
                    CASE tier
                        WHEN 'S+' THEN 1
                        WHEN 'S' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'C' THEN 5
                        ELSE 6
                    END,
                    avg_r DESC
            """

            active_setups = con.execute(conditional_query, params).df().to_dict('records')

            # Query baseline setups (fallback)
            baseline_where = ["instrument = ?", "condition_type IS NULL"]
            baseline_params = [instrument]

            if orb_time:
                baseline_where.append("orb_time = ?")
                baseline_params.append(orb_time)

            baseline_query = f"""
                SELECT
                    setup_id,
                    orb_time,
                    rr,
                    sl_mode,
                    close_confirmations,
                    win_rate,
                    avg_r,
                    tier,
                    notes,
                    quality_multiplier,
                    trades,
                    annual_trades
                FROM validated_setups
                WHERE {' AND '.join(baseline_where)}
                ORDER BY
                    CASE tier
                        WHEN 'S+' THEN 1
                        WHEN 'S' THEN 2
                        WHEN 'A' THEN 3
                        WHEN 'B' THEN 4
                        WHEN 'C' THEN 5
                        ELSE 6
                    END,
                    avg_r DESC
            """

            baseline_setups = con.execute(baseline_query, baseline_params).df().to_dict('records')

            if active_setups:
                logger.info(f"Found {len(active_setups)} conditional setups matching market state")
            else:
                logger.info(f"No conditional setups match current state, using {len(baseline_setups)} baseline setups")

            return active_setups, baseline_setups

        except Exception as e:
            logger.error(f"Error getting conditional setups: {e}")
            return [], []

    def get_active_and_potential_setups(
        self,
        instrument: str,
        current_price: float,
        target_date: Optional[date] = None,
        orb_time: Optional[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        Get active setups (conditions met NOW) and potential setups (if market moves).

        Args:
            instrument: Instrument symbol
            current_price: Current market price
            target_date: Date to evaluate (default: today)
            orb_time: Optional ORB time filter

        Returns:
            Dict with keys:
            - 'active': Setups matching current conditions
            - 'baseline': Baseline setups (always available)
            - 'potential': Setups that would activate if conditions change
            - 'market_state': Current market state dict

        Example:
            >>> result = detector.get_active_and_potential_setups('MGC', 2650.5)
            >>> print(f"Active: {len(result['active'])}")
            >>> print(f"Market state: {result['market_state']['asia_bias']}")
        """
        try:
            # Import market_state (lazy import to avoid circular dependencies)
            from market_state import get_market_state, get_potential_states

            # Get current market state
            market_state = get_market_state(current_price, target_date=target_date)

            # Get active and baseline setups
            active_setups, baseline_setups = self.get_conditional_setups(
                instrument, market_state, orb_time
            )

            # Get potential setups (what becomes active if conditions change)
            potential_setups = []
            if market_state['asia_high'] is not None:
                potential_states = get_potential_states(
                    current_price,
                    market_state['asia_high'],
                    market_state['asia_low']
                )

                for potential_condition, potential_value in potential_states.items():
                    potential_market_state = {**market_state, 'asia_bias': potential_value}
                    potential, _ = self.get_conditional_setups(
                        instrument, potential_market_state, orb_time
                    )
                    for setup in potential:
                        setup['becomes_active_if'] = potential_condition
                        potential_setups.append(setup)

            return {
                'active': active_setups,
                'baseline': baseline_setups,
                'potential': potential_setups,
                'market_state': market_state
            }

        except Exception as e:
            logger.error(f"Error getting active/potential setups: {e}")
            return {
                'active': [],
                'baseline': [],
                'potential': [],
                'market_state': {'asia_bias': 'UNKNOWN'}
            }
        except Exception as e:
            logger.error(f"Error getting elite setups: {e}")
            return []

    def format_setup_alert(self, setup: Dict) -> str:
        """Format a validated setup as an alert message."""
        alert = f"[{setup['tier']} TIER SETUP DETECTED!]\n\n"
        alert += f"ORB: {setup['orb_time']}\n"
        alert += f"Win Rate: {setup['win_rate']:.1f}%\n"
        alert += f"Avg R: {setup['avg_r']:+.3f}R\n"
        alert += f"RR Target: {setup['rr']}R\n"
        alert += f"SL Mode: {setup['sl_mode']}\n"

        orb_filter = setup.get('orb_size_filter')
        if orb_filter and not (isinstance(orb_filter, float) and pd.isna(orb_filter)):
            alert += f"Filter: ORB < {orb_filter*100:.1f}% ATR\n"

        alert += f"\nNotes: {setup['notes']}"

        return alert


def get_best_setup_for_orb(instrument: str, orb_time: str, orb_size: float, atr_20: float) -> Optional[Dict]:
    """
    Quick helper: Get the single best validated setup for this ORB.
    Returns None if no validated setups match criteria.
    """
    detector = SetupDetector()
    matches = detector.check_orb_setup(instrument, orb_time, orb_size, atr_20, datetime.now())

    if matches:
        return matches[0]  # Best setup (sorted by tier then avg_r)

    return None


if __name__ == "__main__":
    # Test the detector
    detector = SetupDetector()

    print("="*80)
    print("ELITE SETUPS (S+ and S tier only)")
    print("="*80)

    elite = detector.get_elite_setups("MGC")
    for setup in elite:
        print(f"\n{setup['orb_time']} ORB [{setup['tier']} tier]:")
        print(f"  Win Rate: {setup['win_rate']:.1f}%")
        print(f"  Avg R: {setup['avg_r']:+.3f}R")
        print(f"  Frequency: ~{setup['annual_trades']} trades/year")
        print(f"  Notes: {setup['notes']}")

    print("\n" + "="*80)
    print("Testing ORB detection...")
    print("="*80)

    # Test: Small 1100 ORB (should trigger S+ tier setup)
    print("\nTest 1: 1100 ORB, size=3.0, ATR=40.0")
    matches = detector.check_orb_setup("MGC", "1100", 3.0, 40.0, datetime.now())
    if matches:
        print(detector.format_setup_alert(matches[0]))
    else:
        print("No validated setup found")

    # Test: Large 1100 ORB (should NOT trigger due to filter)
    print("\n" + "="*80)
    print("\nTest 2: 1100 ORB, size=6.0, ATR=40.0 (too large)")
    matches = detector.check_orb_setup("MGC", "1100", 6.0, 40.0, datetime.now())
    if matches:
        print(detector.format_setup_alert(matches[0]))
    else:
        print("No validated setup found - ORB too large vs ATR")
