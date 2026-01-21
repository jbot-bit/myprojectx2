"""
Research Runner Persistence

Handles database operations for research runs:
- Create/update research_runs table
- Store candidates and results
- Save/load checkpoints
- Append-only semantics (never overwrite previous runs)
"""

import duckdb
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from trading_app.research_runner.contracts import (
    StrategySpec,
    RunConfig,
    ResultRow,
    CheckpointState
)
from trading_app.cloud_mode import get_database_connection, get_database_path

logger = logging.getLogger(__name__)


class ResearchPersistence:
    """
    Handles all database operations for research runner.

    Uses append-only semantics - never overwrites previous run data.
    """

    def __init__(self):
        """Initialize persistence layer."""
        self.db_path = get_database_path()
        self._ensure_schema()

    def _get_connection(self, read_only: bool = False):
        """Get database connection (cloud-aware)."""
        return get_database_connection(read_only=read_only)

    def _ensure_schema(self):
        """Ensure research runner tables exist."""
        conn = self._get_connection(read_only=False)

        try:
            # research_runs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_runs (
                    run_id VARCHAR PRIMARY KEY,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    status VARCHAR NOT NULL,  -- 'running', 'completed', 'failed', 'paused'
                    code_sha VARCHAR,
                    config_json JSON NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # research_candidates table (all tested candidates)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_candidates (
                    run_id VARCHAR NOT NULL,
                    spec_id VARCHAR NOT NULL,
                    spec_json JSON NOT NULL,
                    metrics_json JSON,
                    tested_at TIMESTAMPTZ,
                    status VARCHAR NOT NULL,  -- 'pending', 'completed', 'failed', 'skipped'
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (run_id, spec_id)
                )
            """)

            # research_survivors table (candidates that passed gates)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_survivors (
                    run_id VARCHAR NOT NULL,
                    spec_id VARCHAR NOT NULL,
                    spec_json JSON NOT NULL,
                    metrics_json JSON NOT NULL,
                    promoted_at TIMESTAMPTZ NOT NULL,
                    survival_score DOUBLE,
                    confidence VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (run_id, spec_id)
                )
            """)

            # research_checkpoints table (for resume)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_checkpoints (
                    run_id VARCHAR NOT NULL,
                    checkpoint_id VARCHAR PRIMARY KEY,
                    checkpoint_json JSON NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

            logger.info("Research runner schema verified")

        finally:
            conn.close()

    def create_run(self, config: RunConfig) -> bool:
        """
        Create new research run.

        Args:
            config: RunConfig with run parameters

        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection(read_only=False)

        try:
            # Get git commit SHA if available
            import subprocess
            try:
                code_sha = subprocess.check_output(
                    ['git', 'rev-parse', '--short', 'HEAD'],
                    cwd=Path(__file__).parent.parent.parent,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except:
                code_sha = 'unknown'

            conn.execute("""
                INSERT INTO research_runs (run_id, started_at, status, code_sha, config_json)
                VALUES (?, ?, ?, ?, ?::JSON)
            """, [
                config.run_id,
                datetime.now().isoformat(),
                'running',
                code_sha,
                config.to_json()
            ])

            logger.info(f"Created research run: {config.run_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to create run: {e}")
            return False

        finally:
            conn.close()

    def update_run_status(self, run_id: str, status: str, finished_at: Optional[str] = None) -> bool:
        """
        Update run status.

        Args:
            run_id: Run ID
            status: New status
            finished_at: Optional finish timestamp

        Returns:
            True if successful
        """
        conn = self._get_connection(read_only=False)

        try:
            if finished_at:
                conn.execute("""
                    UPDATE research_runs
                    SET status = ?, finished_at = ?
                    WHERE run_id = ?
                """, [status, finished_at, run_id])
            else:
                conn.execute("""
                    UPDATE research_runs
                    SET status = ?
                    WHERE run_id = ?
                """, [status, run_id])

            logger.info(f"Updated run {run_id} status to {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to update run status: {e}")
            return False

        finally:
            conn.close()

    def save_candidate(self, run_id: str, spec: StrategySpec, result: Optional[ResultRow] = None) -> bool:
        """
        Save candidate result (append-only).

        Args:
            run_id: Run ID
            spec: Strategy specification
            result: Optional backtest result

        Returns:
            True if successful
        """
        conn = self._get_connection(read_only=False)

        try:
            if result:
                conn.execute("""
                    INSERT INTO research_candidates (run_id, spec_id, spec_json, metrics_json, tested_at, status)
                    VALUES (?, ?, ?::JSON, ?::JSON, ?, ?)
                    ON CONFLICT (run_id, spec_id) DO UPDATE
                    SET metrics_json = EXCLUDED.metrics_json,
                        tested_at = EXCLUDED.tested_at,
                        status = EXCLUDED.status
                """, [
                    run_id,
                    spec.spec_id,
                    spec.to_json(),
                    result.to_json(),
                    result.tested_at,
                    result.status
                ])
            else:
                # Pending candidate
                conn.execute("""
                    INSERT INTO research_candidates (run_id, spec_id, spec_json, status)
                    VALUES (?, ?, ?::JSON, ?)
                    ON CONFLICT (run_id, spec_id) DO NOTHING
                """, [
                    run_id,
                    spec.spec_id,
                    spec.to_json(),
                    'pending'
                ])

            return True

        except Exception as e:
            logger.error(f"Failed to save candidate: {e}")
            return False

        finally:
            conn.close()

    def save_survivor(
        self,
        run_id: str,
        spec: StrategySpec,
        result: ResultRow,
        survival_score: float,
        confidence: str
    ) -> bool:
        """
        Save survivor (passed all gates).

        Args:
            run_id: Run ID
            spec: Strategy specification
            result: Backtest result
            survival_score: Survival score
            confidence: Confidence level

        Returns:
            True if successful
        """
        conn = self._get_connection(read_only=False)

        try:
            conn.execute("""
                INSERT INTO research_survivors (run_id, spec_id, spec_json, metrics_json, promoted_at, survival_score, confidence)
                VALUES (?, ?, ?::JSON, ?::JSON, ?, ?, ?)
                ON CONFLICT (run_id, spec_id) DO NOTHING
            """, [
                run_id,
                spec.spec_id,
                spec.to_json(),
                result.to_json(),
                datetime.now().isoformat(),
                survival_score,
                confidence
            ])

            logger.info(f"Saved survivor: {spec.spec_id} (score: {survival_score:.1f}, confidence: {confidence})")
            return True

        except Exception as e:
            logger.error(f"Failed to save survivor: {e}")
            return False

        finally:
            conn.close()

    def save_checkpoint(self, checkpoint: CheckpointState) -> bool:
        """
        Save checkpoint (atomic write).

        Args:
            checkpoint: Checkpoint state

        Returns:
            True if successful
        """
        conn = self._get_connection(read_only=False)

        try:
            conn.execute("""
                INSERT INTO research_checkpoints (run_id, checkpoint_id, checkpoint_json, updated_at)
                VALUES (?, ?, ?::JSON, ?)
                ON CONFLICT (checkpoint_id) DO UPDATE
                SET checkpoint_json = EXCLUDED.checkpoint_json,
                    updated_at = EXCLUDED.updated_at
            """, [
                checkpoint.run_id,
                checkpoint.checkpoint_id,
                checkpoint.to_json(),
                datetime.now().isoformat()
            ])

            logger.debug(f"Saved checkpoint: {checkpoint.checkpoint_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

        finally:
            conn.close()

    def load_latest_checkpoint(self, run_id: str) -> Optional[CheckpointState]:
        """
        Load latest checkpoint for a run.

        Args:
            run_id: Run ID

        Returns:
            CheckpointState if found, None otherwise
        """
        conn = self._get_connection(read_only=True)

        try:
            result = conn.execute("""
                SELECT checkpoint_json
                FROM research_checkpoints
                WHERE run_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
            """, [run_id]).fetchone()

            if result:
                checkpoint_json = result[0]
                return CheckpointState.from_json(checkpoint_json)

            return None

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

        finally:
            conn.close()

    def get_run_progress(self, run_id: str) -> Dict[str, Any]:
        """
        Get run progress summary.

        Args:
            run_id: Run ID

        Returns:
            Dictionary with progress metrics
        """
        conn = self._get_connection(read_only=True)

        try:
            # Count candidates by status
            counts = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM research_candidates
                WHERE run_id = ?
                GROUP BY status
            """, [run_id]).fetchdf()

            # Count survivors
            survivor_count = conn.execute("""
                SELECT COUNT(*) as count
                FROM research_survivors
                WHERE run_id = ?
            """, [run_id]).fetchone()[0]

            # Get run info
            run_info = conn.execute("""
                SELECT started_at, status, config_json
                FROM research_runs
                WHERE run_id = ?
            """, [run_id]).fetchone()

            if not run_info:
                return {}

            started_at, status, config_json = run_info
            config = RunConfig.from_json(config_json)

            return {
                'run_id': run_id,
                'status': status,
                'started_at': started_at,
                'candidates_by_status': counts.to_dict('records'),
                'survivors': survivor_count,
                'max_iters': config.max_iters
            }

        except Exception as e:
            logger.error(f"Failed to get run progress: {e}")
            return {}

        finally:
            conn.close()

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        List recent research runs.

        Args:
            limit: Max runs to return

        Returns:
            List of run summaries
        """
        conn = self._get_connection(read_only=True)

        try:
            runs = conn.execute("""
                SELECT
                    run_id,
                    started_at,
                    finished_at,
                    status,
                    code_sha,
                    config_json
                FROM research_runs
                ORDER BY started_at DESC
                LIMIT ?
            """, [limit]).fetchdf()

            return runs.to_dict('records')

        except Exception as e:
            logger.error(f"Failed to list runs: {e}")
            return []

        finally:
            conn.close()
