"""
Research Runner Checkpoint Manager

Handles checkpoint save/load with atomic writes and file locking.
Ensures crash-safe checkpoint persistence.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from trading_app.research_runner.contracts import CheckpointState, generate_checkpoint_id
from trading_app.research_runner.persistence import ResearchPersistence

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints for resumable execution.

    Features:
    - Atomic file writes (write temp, then rename)
    - File locking to prevent concurrent runs
    - Both file-based and DB-based checkpoints
    - Automatic cleanup of old checkpoints
    """

    def __init__(self, run_id: str, checkpoint_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager.

        Args:
            run_id: Run ID
            checkpoint_dir: Directory for checkpoint files (default: data/checkpoints/)
        """
        self.run_id = run_id
        self.persistence = ResearchPersistence()

        # Checkpoint directory
        if checkpoint_dir is None:
            self.checkpoint_dir = Path(__file__).parent.parent.parent / "data" / "checkpoints"
        else:
            self.checkpoint_dir = checkpoint_dir

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Lock file for this run
        self.lock_file = self.checkpoint_dir / f"{run_id}.lock"
        self.lock_fd = None

    def acquire_lock(self) -> bool:
        """
        Acquire exclusive lock for this run.

        Prevents multiple instances of the same run from running concurrently.

        Returns:
            True if lock acquired, False if already locked
        """
        try:
            self.lock_fd = open(self.lock_file, 'w')

            # Try to acquire exclusive lock (non-blocking)
            if os.name == 'nt':  # Windows
                import msvcrt
                try:
                    msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
                except IOError:
                    return False
            else:  # Unix
                import fcntl
                try:
                    fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    return False

            # Write PID
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()

            logger.info(f"Acquired lock for run {self.run_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False

    def release_lock(self):
        """Release run lock."""
        if self.lock_fd:
            try:
                if os.name == 'nt':  # Windows
                    import msvcrt
                    msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # Unix
                    import fcntl
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)

                self.lock_fd.close()
                self.lock_file.unlink(missing_ok=True)

                logger.info(f"Released lock for run {self.run_id}")

            except Exception as e:
                logger.warning(f"Error releasing lock: {e}")

            finally:
                self.lock_fd = None

    def save_checkpoint(self, checkpoint: CheckpointState) -> bool:
        """
        Save checkpoint atomically (both file and DB).

        Args:
            checkpoint: Checkpoint state to save

        Returns:
            True if successful
        """
        try:
            # 1. Save to file (atomic write: temp file + rename)
            file_saved = self._save_checkpoint_file(checkpoint)

            # 2. Save to database
            db_saved = self.persistence.save_checkpoint(checkpoint)

            if file_saved and db_saved:
                logger.info(f"Checkpoint saved: {checkpoint.checkpoint_id} "
                           f"({checkpoint.candidates_completed}/{checkpoint.total_candidates_planned} completed, "
                           f"{checkpoint.progress_pct():.1f}%)")
                return True
            else:
                logger.warning(f"Partial checkpoint save (file: {file_saved}, db: {db_saved})")
                return file_saved  # File is primary, DB is backup

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    def _save_checkpoint_file(self, checkpoint: CheckpointState) -> bool:
        """
        Save checkpoint to file atomically.

        Uses temp file + rename pattern for atomic write.

        Args:
            checkpoint: Checkpoint state

        Returns:
            True if successful
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{self.run_id}_latest.json"

            # Write to temp file first
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.checkpoint_dir,
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(checkpoint.to_dict(), tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())  # Force flush to disk
                tmp_path = tmp_file.name

            # Atomic rename
            if os.name == 'nt':  # Windows
                # On Windows, need to remove target first
                if checkpoint_file.exists():
                    checkpoint_file.unlink()
            os.rename(tmp_path, checkpoint_file)

            return True

        except Exception as e:
            logger.error(f"Failed to save checkpoint file: {e}")
            # Clean up temp file if it exists
            try:
                if 'tmp_path' in locals():
                    Path(tmp_path).unlink(missing_ok=True)
            except:
                pass
            return False

    def load_checkpoint(self) -> Optional[CheckpointState]:
        """
        Load latest checkpoint (tries file first, then DB).

        Returns:
            CheckpointState if found, None otherwise
        """
        # Try file first (faster)
        checkpoint = self._load_checkpoint_file()
        if checkpoint:
            logger.info(f"Loaded checkpoint from file: {checkpoint.checkpoint_id}")
            return checkpoint

        # Fallback to DB
        checkpoint = self.persistence.load_latest_checkpoint(self.run_id)
        if checkpoint:
            logger.info(f"Loaded checkpoint from DB: {checkpoint.checkpoint_id}")
            return checkpoint

        logger.info(f"No checkpoint found for run {self.run_id}")
        return None

    def _load_checkpoint_file(self) -> Optional[CheckpointState]:
        """
        Load checkpoint from file.

        Returns:
            CheckpointState if found and valid, None otherwise
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{self.run_id}_latest.json"

            if not checkpoint_file.exists():
                return None

            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
                return CheckpointState.from_dict(data)

        except Exception as e:
            logger.warning(f"Failed to load checkpoint file: {e}")
            return None

    def checkpoint_exists(self) -> bool:
        """
        Check if checkpoint exists for this run.

        Returns:
            True if checkpoint exists
        """
        checkpoint_file = self.checkpoint_dir / f"{self.run_id}_latest.json"
        return checkpoint_file.exists()

    def delete_checkpoint(self) -> bool:
        """
        Delete checkpoint (used after successful completion).

        Returns:
            True if successful
        """
        try:
            checkpoint_file = self.checkpoint_dir / f"{self.run_id}_latest.json"
            checkpoint_file.unlink(missing_ok=True)

            logger.info(f"Deleted checkpoint for run {self.run_id}")
            return True

        except Exception as e:
            logger.warning(f"Failed to delete checkpoint: {e}")
            return False

    def cleanup_old_checkpoints(self, keep_last_n: int = 10):
        """
        Clean up old checkpoint files.

        Keeps only the N most recent checkpoints.

        Args:
            keep_last_n: Number of recent checkpoints to keep
        """
        try:
            checkpoint_files = sorted(
                self.checkpoint_dir.glob("run_*_latest.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Keep only last N
            for old_file in checkpoint_files[keep_last_n:]:
                try:
                    old_file.unlink()
                    logger.debug(f"Cleaned up old checkpoint: {old_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete {old_file}: {e}")

        except Exception as e:
            logger.warning(f"Checkpoint cleanup failed: {e}")

    def __enter__(self):
        """Context manager entry - acquire lock."""
        if not self.acquire_lock():
            raise RuntimeError(f"Failed to acquire lock for run {self.run_id} - another instance may be running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        self.release_lock()
