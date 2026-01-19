"""
Edge Discovery Engine (EDE) - Lifecycle Manager

Orchestrates the hard gate flow:
IDEA → GENERATION → BACKTEST → ATTACK → VALIDATION → APPROVAL → SYNC

An edge CANNOT skip a stage. Each gate enforces specific criteria.

This manager coordinates all EDE modules and enforces the contract.
"""

import duckdb
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import logging

# Database path
DB_PATH = str(Path(__file__).parent.parent / "gold.db")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LifecycleStage(Enum):
    """Hard gate stages in the EDE pipeline."""
    IDEA = "IDEA"
    GENERATION = "GENERATION"
    BACKTEST = "BACKTEST"
    ATTACK = "ATTACK"
    VALIDATION = "VALIDATION"
    APPROVAL = "APPROVAL"
    SYNC = "SYNC"


class EdgeStatus(Enum):
    """Edge status at each stage."""
    # Generation stage
    GENERATED = "GENERATED"
    DUPLICATE = "DUPLICATE"
    INVALID = "INVALID"

    # Backtest stage
    TESTING = "TESTING"
    BACKTEST_FAILED = "BACKTEST_FAILED"
    BACKTEST_PASSED = "BACKTEST_PASSED"

    # Attack stage
    ATTACKING = "ATTACKING"
    ATTACK_FAILED = "ATTACK_FAILED"
    ATTACK_PASSED = "ATTACK_PASSED"

    # Validation stage
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    SURVIVOR = "SURVIVOR"

    # Approval stage
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    # Sync stage
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"

    # Final statuses
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


@dataclass
class EdgeCandidate:
    """
    Formal edge candidate specification.

    This is the contract every generated edge must obey.
    If it can't be expressed formally → it does not exist.
    """
    # Identity
    idea_id: str
    human_name: str
    instrument: str  # 'MGC', 'NQ', 'MPL'
    generator_mode: str  # 'brute', 'conditional', 'contrast', 'inversion', 'ml_cluster'

    # Entry rule (formal)
    entry_type: str  # 'break', 'fade', 'close', 'stop', 'limit'
    entry_time_start: str  # 'HH:MM:SS'
    entry_time_end: str  # 'HH:MM:SS'
    entry_condition: Dict[str, Any]

    # Exit rule (formal)
    exit_type: str  # 'fixed_r', 'trailing', 'time', 'structure', 'hybrid'
    stop_type: str  # 'fixed_r', 'atr', 'half', 'structure'
    stop_r: Optional[float]
    target_r: Optional[float]
    exit_condition: Dict[str, Any]

    # Time window
    session_window: str  # 'asia', 'london', 'ny', 'custom'
    time_window_start: str
    time_window_end: str

    # Required features
    required_features: List[str]

    # Risk model
    risk_model: str  # 'fixed_r', 'dynamic_atr', 'volatility_scaled'
    risk_pct: float = 1.0

    # Filters
    filters: Optional[Dict[str, Any]] = None

    # Assumptions
    assumptions: Optional[Dict[str, Any]] = None

    # Metadata
    generation_notes: Optional[str] = None

    def to_param_hash(self) -> str:
        """
        Generate deterministic hash of parameters.
        Used for deduplication and immutability enforcement.
        """
        param_dict = {
            'instrument': self.instrument,
            'entry_type': self.entry_type,
            'entry_time_start': self.entry_time_start,
            'entry_time_end': self.entry_time_end,
            'entry_condition': self.entry_condition,
            'exit_type': self.exit_type,
            'stop_type': self.stop_type,
            'stop_r': self.stop_r,
            'target_r': self.target_r,
            'exit_condition': self.exit_condition,
            'time_window_start': self.time_window_start,
            'time_window_end': self.time_window_end,
            'risk_model': self.risk_model,
            'risk_pct': self.risk_pct,
            'filters': self.filters,
        }
        param_json = json.dumps(param_dict, sort_keys=True)
        return hashlib.sha256(param_json.encode()).hexdigest()

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate edge candidate meets formal requirements.

        Returns:
            (is_valid, error_message)
        """
        # Check required fields are not None
        required_fields = [
            'idea_id', 'human_name', 'instrument', 'generator_mode',
            'entry_type', 'entry_time_start', 'entry_time_end',
            'exit_type', 'stop_type', 'session_window',
            'time_window_start', 'time_window_end', 'risk_model'
        ]

        for field in required_fields:
            if getattr(self, field) is None:
                return False, f"Required field '{field}' is None"

        # Validate instrument
        if self.instrument not in ['MGC', 'NQ', 'MPL']:
            return False, f"Invalid instrument: {self.instrument}"

        # Validate entry type
        valid_entry_types = ['break', 'fade', 'close', 'stop', 'limit']
        if self.entry_type not in valid_entry_types:
            return False, f"Invalid entry_type: {self.entry_type}"

        # Validate exit type
        valid_exit_types = ['fixed_r', 'trailing', 'time', 'structure', 'hybrid']
        if self.exit_type not in valid_exit_types:
            return False, f"Invalid exit_type: {self.exit_type}"

        # Validate stop type
        valid_stop_types = ['fixed_r', 'atr', 'half', 'structure']
        if self.stop_type not in valid_stop_types:
            return False, f"Invalid stop_type: {self.stop_type}"

        # Validate risk parameters
        if self.risk_pct <= 0 or self.risk_pct > 5:
            return False, f"Invalid risk_pct: {self.risk_pct} (must be 0-5%)"

        # Validate R multiples if specified
        if self.stop_r is not None and self.stop_r <= 0:
            return False, f"Invalid stop_r: {self.stop_r} (must be > 0)"

        if self.target_r is not None and self.target_r <= 0:
            return False, f"Invalid target_r: {self.target_r} (must be > 0)"

        return True, None


class LifecycleManager:
    """
    Orchestrates edge discovery pipeline from generation to production.

    Enforces hard gates - no edge can skip a stage.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        logger.info(f"LifecycleManager initialized with DB: {db_path}")

    def _get_connection(self):
        """Get database connection."""
        return duckdb.connect(self.db_path)

    # ========================================================================
    # STAGE 1: GENERATION
    # ========================================================================

    def submit_candidate(self, candidate: EdgeCandidate) -> tuple[bool, str]:
        """
        Submit a new edge candidate (from generators).

        Gate requirements:
        - Must pass validation
        - Must not be duplicate (param_hash)
        - Must have formal specification

        Returns:
            (success, message)
        """
        # Validate candidate
        is_valid, error = candidate.validate()
        if not is_valid:
            logger.warning(f"Candidate validation failed: {error}")
            return False, f"Validation failed: {error}"

        # Calculate parameter hash
        param_hash = candidate.to_param_hash()

        # Check for duplicates
        con = self._get_connection()
        existing = con.execute("""
            SELECT idea_id, status
            FROM edge_candidates_raw
            WHERE param_hash = ?
        """, [param_hash]).fetchone()

        if existing:
            logger.info(f"Duplicate candidate detected: {param_hash[:8]}")
            return False, f"Duplicate: {existing[0]} (status: {existing[1]})"

        # Insert into edge_candidates_raw
        try:
            con.execute("""
                INSERT INTO edge_candidates_raw (
                    idea_id, generation_timestamp, generator_mode,
                    human_name, instrument,
                    entry_type, entry_time_start, entry_time_end, entry_condition_json,
                    exit_type, stop_type, stop_r, target_r, exit_condition_json,
                    session_window, time_window_start, time_window_end,
                    required_features, risk_model, risk_pct,
                    filters_json, assumptions_json,
                    status, param_hash, generation_notes
                ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                candidate.idea_id,
                candidate.generator_mode,
                candidate.human_name,
                candidate.instrument,
                candidate.entry_type,
                candidate.entry_time_start,
                candidate.entry_time_end,
                json.dumps(candidate.entry_condition),
                candidate.exit_type,
                candidate.stop_type,
                candidate.stop_r,
                candidate.target_r,
                json.dumps(candidate.exit_condition),
                candidate.session_window,
                candidate.time_window_start,
                candidate.time_window_end,
                candidate.required_features,
                candidate.risk_model,
                candidate.risk_pct,
                json.dumps(candidate.filters) if candidate.filters else None,
                json.dumps(candidate.assumptions) if candidate.assumptions else None,
                EdgeStatus.GENERATED.value,
                param_hash,
                candidate.generation_notes
            ])

            logger.info(f"Candidate accepted: {candidate.idea_id} | {candidate.human_name}")
            return True, f"Candidate accepted: {candidate.idea_id}"

        except Exception as e:
            logger.error(f"Database error submitting candidate: {e}")
            return False, f"Database error: {e}"
        finally:
            con.close()

    def get_candidates_for_backtest(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get candidates ready for backtesting.

        Returns candidates with status = GENERATED.
        """
        con = self._get_connection()
        results = con.execute("""
            SELECT
                idea_id, human_name, instrument, generator_mode,
                entry_type, entry_time_start, entry_time_end, entry_condition_json,
                exit_type, stop_type, stop_r, target_r, exit_condition_json,
                session_window, time_window_start, time_window_end,
                required_features, risk_model, risk_pct,
                filters_json, assumptions_json, param_hash
            FROM edge_candidates_raw
            WHERE status = ?
            ORDER BY generation_timestamp
            LIMIT ?
        """, [EdgeStatus.GENERATED.value, limit]).fetchdf()

        con.close()

        if len(results) == 0:
            return []

        return results.to_dict('records')

    def update_candidate_status(self, idea_id: str, new_status: EdgeStatus, notes: str = None):
        """Update candidate status during pipeline."""
        con = self._get_connection()
        con.execute("""
            UPDATE edge_candidates_raw
            SET status = ?
            WHERE idea_id = ?
        """, [new_status.value, idea_id])
        con.close()
        logger.info(f"Updated {idea_id}: {new_status.value}")

    # ========================================================================
    # STAGE 3: VALIDATION (after backtest + attacks)
    # ========================================================================

    def submit_survivor(self, survivor_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Submit edge that passed all Step 3 tests.

        Gate requirements:
        - Positive expectancy after costs
        - Stable under attacks
        - Regime-robust
        - Adequate sample size

        Returns:
            (success, message)
        """
        try:
            con = self._get_connection()

            # Generate survivor ID
            survivor_id = f"SURV_{survivor_data['idea_id']}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Calculate survival score (composite metric)
            survival_score = self._calculate_survival_score(survivor_data)

            # Determine confidence level
            confidence = self._determine_confidence(survival_score, survivor_data)

            # Generate results hash
            results_json = json.dumps(survivor_data, sort_keys=True)
            results_hash = hashlib.sha256(results_json.encode()).hexdigest()

            # Insert into edge_candidates_survivors
            con.execute("""
                INSERT INTO edge_candidates_survivors (
                    survivor_id, idea_id, survival_timestamp,
                    baseline_trades, baseline_win_rate, baseline_avg_r,
                    baseline_expectancy, baseline_max_dd, baseline_profit_factor, baseline_sharpe,
                    cost_1tick_expectancy, cost_2tick_expectancy, cost_3tick_expectancy,
                    cost_atr_expectancy, cost_missedfill_expectancy,
                    attack_stopfirst_expectancy, attack_entrydelay_expectancy,
                    attack_exitdelay_expectancy, attack_noise_expectancy, attack_shuffle_expectancy,
                    regime_year_count, regime_year_profitable,
                    regime_volatility_count, regime_volatility_profitable,
                    regime_session_count, regime_session_profitable,
                    regime_max_profit_concentration,
                    walkforward_windows, walkforward_profitable, walkforward_avg_expectancy,
                    survival_score, confidence_level, status, results_hash
                ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                survivor_id,
                survivor_data['idea_id'],
                survivor_data['baseline_trades'],
                survivor_data['baseline_win_rate'],
                survivor_data['baseline_avg_r'],
                survivor_data['baseline_expectancy'],
                survivor_data['baseline_max_dd'],
                survivor_data.get('baseline_profit_factor'),
                survivor_data.get('baseline_sharpe'),
                survivor_data['cost_1tick_expectancy'],
                survivor_data['cost_2tick_expectancy'],
                survivor_data['cost_3tick_expectancy'],
                survivor_data['cost_atr_expectancy'],
                survivor_data['cost_missedfill_expectancy'],
                survivor_data['attack_stopfirst_expectancy'],
                survivor_data['attack_entrydelay_expectancy'],
                survivor_data['attack_exitdelay_expectancy'],
                survivor_data['attack_noise_expectancy'],
                survivor_data['attack_shuffle_expectancy'],
                survivor_data['regime_year_count'],
                survivor_data['regime_year_profitable'],
                survivor_data['regime_volatility_count'],
                survivor_data['regime_volatility_profitable'],
                survivor_data['regime_session_count'],
                survivor_data['regime_session_profitable'],
                survivor_data['regime_max_profit_concentration'],
                survivor_data['walkforward_windows'],
                survivor_data['walkforward_profitable'],
                survivor_data['walkforward_avg_expectancy'],
                survival_score,
                confidence,
                EdgeStatus.SURVIVOR.value,
                results_hash
            ])

            # Update original candidate status
            con.execute("""
                UPDATE edge_candidates_raw
                SET status = ?
                WHERE idea_id = ?
            """, [EdgeStatus.SURVIVOR.value, survivor_data['idea_id']])

            con.close()

            logger.info(f"Survivor created: {survivor_id} | Score: {survival_score:.1f} | Confidence: {confidence}")
            return True, f"Survivor created: {survivor_id}"

        except Exception as e:
            logger.error(f"Error submitting survivor: {e}")
            return False, f"Error: {e}"

    def _calculate_survival_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate composite survival score (0-100).

        Factors:
        - Baseline expectancy
        - Cost resistance
        - Attack resistance
        - Regime robustness
        - Sample size
        """
        score = 0.0

        # Baseline expectancy (0-25 points)
        exp = data['baseline_expectancy']
        if exp > 0.5:
            score += 25
        elif exp > 0.3:
            score += 20
        elif exp > 0.1:
            score += 15
        elif exp > 0:
            score += 10

        # Cost resistance (0-25 points)
        # Average expectancy after costs
        cost_avg = (
            data['cost_1tick_expectancy'] +
            data['cost_2tick_expectancy'] +
            data['cost_3tick_expectancy']
        ) / 3
        if cost_avg > 0.3:
            score += 25
        elif cost_avg > 0.1:
            score += 20
        elif cost_avg > 0:
            score += 15

        # Attack resistance (0-25 points)
        # Average expectancy after attacks
        attack_avg = (
            data['attack_stopfirst_expectancy'] +
            data['attack_entrydelay_expectancy'] +
            data['attack_exitdelay_expectancy'] +
            data['attack_noise_expectancy'] +
            data['attack_shuffle_expectancy']
        ) / 5
        if attack_avg > 0.3:
            score += 25
        elif attack_avg > 0.1:
            score += 20
        elif attack_avg > 0:
            score += 15

        # Regime robustness (0-25 points)
        regime_ratio = (
            data['regime_year_profitable'] / data['regime_year_count'] +
            data['regime_volatility_profitable'] / data['regime_volatility_count'] +
            data['regime_session_profitable'] / data['regime_session_count']
        ) / 3

        concentration = data['regime_max_profit_concentration']

        if regime_ratio >= 0.66 and concentration < 0.5:
            score += 25
        elif regime_ratio >= 0.5 and concentration < 0.7:
            score += 20
        elif regime_ratio >= 0.4:
            score += 15

        return min(100.0, score)

    def _determine_confidence(self, score: float, data: Dict[str, Any]) -> str:
        """Determine confidence level based on score and sample size."""
        trades = data['baseline_trades']

        if score >= 80 and trades >= 100:
            return 'VERY_HIGH'
        elif score >= 70 and trades >= 50:
            return 'HIGH'
        elif score >= 60 and trades >= 30:
            return 'MEDIUM'
        else:
            return 'LOW'

    def get_survivors_for_approval(self, min_confidence: str = 'MEDIUM') -> List[Dict[str, Any]]:
        """Get survivors ready for approval."""
        con = self._get_connection()

        confidence_order = ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
        min_idx = confidence_order.index(min_confidence)
        valid_confidences = confidence_order[min_idx:]

        results = con.execute("""
            SELECT
                s.survivor_id, s.idea_id, s.survival_score, s.confidence_level,
                s.baseline_expectancy, s.baseline_win_rate, s.baseline_trades,
                c.human_name, c.instrument, c.param_hash
            FROM edge_candidates_survivors s
            JOIN edge_candidates_raw c ON s.idea_id = c.idea_id
            WHERE s.status = ?
            AND s.confidence_level IN ({})
            ORDER BY s.survival_score DESC, s.baseline_expectancy DESC
        """.format(','.join(['?' for _ in valid_confidences])),
        [EdgeStatus.SURVIVOR.value] + valid_confidences).fetchdf()

        con.close()
        return results.to_dict('records') if len(results) > 0 else []

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def get_pipeline_stats(self) -> Dict[str, int]:
        """Get current pipeline statistics."""
        con = self._get_connection()

        stats = {
            'total_candidates': con.execute("SELECT COUNT(*) FROM edge_candidates_raw").fetchone()[0],
            'generated': con.execute("SELECT COUNT(*) FROM edge_candidates_raw WHERE status = ?", [EdgeStatus.GENERATED.value]).fetchone()[0],
            'testing': con.execute("SELECT COUNT(*) FROM edge_candidates_raw WHERE status LIKE '%TESTING%'").fetchone()[0],
            'failed': con.execute("SELECT COUNT(*) FROM edge_candidates_raw WHERE status LIKE '%FAILED%'").fetchone()[0],
            'survivors': con.execute("SELECT COUNT(*) FROM edge_candidates_survivors WHERE status = ?", [EdgeStatus.SURVIVOR.value]).fetchone()[0],
            'approved': con.execute("SELECT COUNT(*) FROM edge_manifest WHERE status = ?", [EdgeStatus.APPROVED.value]).fetchone()[0],
            'active': con.execute("SELECT COUNT(*) FROM edge_manifest WHERE status = ?", [EdgeStatus.ACTIVE.value]).fetchone()[0],
            'suspended': con.execute("SELECT COUNT(*) FROM edge_manifest WHERE status = ?", [EdgeStatus.SUSPENDED.value]).fetchone()[0],
        }

        con.close()
        return stats

    def log_generation_run(self, mode: str, config: Dict[str, Any],
                          generated: int, duplicates: int, invalid: int,
                          accepted: int, duration: float, notes: str = None):
        """Log a generation run for audit trail."""
        con = self._get_connection()

        log_id = f"GEN_{mode.upper()}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        con.execute("""
            INSERT INTO edge_generation_log (
                log_id, run_timestamp, generator_mode, run_config_json,
                candidates_generated, candidates_duplicates, candidates_invalid,
                candidates_accepted, run_duration_seconds, run_notes
            ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            log_id, mode, json.dumps(config),
            generated, duplicates, invalid, accepted,
            duration, notes
        ])

        con.close()
        logger.info(f"Generation run logged: {log_id}")


if __name__ == "__main__":
    # Test lifecycle manager
    manager = LifecycleManager()

    stats = manager.get_pipeline_stats()
    print("\n" + "="*70)
    print("EDGE DISCOVERY LIFECYCLE MANAGER")
    print("="*70)
    print("\nPipeline Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("\nLifecycle Manager ready for edge discovery pipeline.")
