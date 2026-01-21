"""
Research Runner - Main execution engine

Resumable backtest runner that:
- Generates strategy candidates
- Runs backtests using existing engine
- Saves checkpoints frequently
- Resumes from last checkpoint after crash
- Persists results to DB
"""

import logging
import time
import signal
import sys
from typing import List, Optional, Generator
from datetime import datetime
from pathlib import Path

from trading_app.backtest import (
    backtest_candidate,
    calculate_metrics,
    CandidateSpec as BacktestCandidateSpec
)
from trading_app.research_runner.contracts import (
    StrategySpec,
    RunConfig,
    ResultRow,
    CheckpointState,
    generate_run_id,
    generate_checkpoint_id,
    generate_spec_id
)
from trading_app.research_runner.checkpoint import CheckpointManager
from trading_app.research_runner.persistence import ResearchPersistence

logger = logging.getLogger(__name__)


class ResearchRunner:
    """
    Main research runner with checkpoint/resume support.

    Workflow:
    1. Check for existing checkpoint
    2. If found, resume from checkpoint
    3. Generate strategy candidates
    4. Backtest each candidate
    5. Save checkpoint every N candidates or M minutes
    6. Store results in DB
    7. Exit cleanly on CTRL+C (save checkpoint)
    """

    def __init__(self, config: RunConfig):
        """
        Initialize research runner.

        Args:
            config: Run configuration
        """
        self.config = config
        self.persistence = ResearchPersistence()
        self.checkpoint_manager = CheckpointManager(config.run_id)

        # State
        self.checkpoint: Optional[CheckpointState] = None
        self.start_time: float = 0.0
        self.last_checkpoint_time: float = 0.0
        self.should_stop = False

        # Setup signal handlers for clean exit
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle CTRL+C and SIGTERM gracefully."""
        logger.warning(f"Received signal {signum}, saving checkpoint and exiting...")
        self.should_stop = True

    def run(self, resume: bool = True) -> bool:
        """
        Run the research workflow.

        Args:
            resume: Whether to resume from checkpoint if exists

        Returns:
            True if successful, False otherwise
        """
        try:
            # Acquire lock
            with self.checkpoint_manager:

                # Try to resume
                if resume and self.checkpoint_manager.checkpoint_exists():
                    logger.info("Found existing checkpoint, resuming...")
                    self.checkpoint = self.checkpoint_manager.load_checkpoint()

                    if not self.checkpoint:
                        logger.error("Failed to load checkpoint")
                        return False

                    # Update run status
                    self.persistence.update_run_status(self.config.run_id, 'running')

                else:
                    logger.info("Starting new research run...")

                    # Create new run in DB
                    if not self.persistence.create_run(self.config):
                        logger.error("Failed to create run in database")
                        return False

                    # Initialize checkpoint
                    self.checkpoint = self._create_initial_checkpoint()

                # Start timer
                self.start_time = time.time()
                self.last_checkpoint_time = self.start_time

                # Run backtest loop
                success = self._run_backtest_loop()

                # Final checkpoint and status update
                if success:
                    self.checkpoint.status = 'completed'
                    self.checkpoint_manager.save_checkpoint(self.checkpoint)
                    self.persistence.update_run_status(
                        self.config.run_id,
                        'completed',
                        datetime.now().isoformat()
                    )
                    logger.info(f"Research run completed: {self.config.run_id}")
                    logger.info(f"  Total candidates: {self.checkpoint.candidates_completed}")
                    logger.info(f"  Passed gates: {self.checkpoint.candidates_passed}")
                    logger.info(f"  Best expectancy: {self.checkpoint.best_expectancy_r:.3f}R")

                    # Cleanup checkpoint file after successful completion
                    self.checkpoint_manager.delete_checkpoint()

                else:
                    self.checkpoint.status = 'failed' if not self.should_stop else 'paused'
                    self.checkpoint_manager.save_checkpoint(self.checkpoint)
                    self.persistence.update_run_status(self.config.run_id, self.checkpoint.status)

                    if self.should_stop:
                        logger.info("Run paused - resume with --resume flag")
                    else:
                        logger.error("Run failed - check logs")

                return success

        except Exception as e:
            logger.error(f"Research run failed: {e}", exc_info=True)
            return False

    def _create_initial_checkpoint(self) -> CheckpointState:
        """Create initial checkpoint state."""
        return CheckpointState(
            run_id=self.config.run_id,
            checkpoint_id=generate_checkpoint_id(self.config.run_id, 0),
            created_at=datetime.now().isoformat(),
            total_candidates_planned=self.config.max_iters,
            candidates_completed=0,
            candidates_passed=0,
            last_completed_spec_id=None,
            search_cursor={},
            rng_state=None,
            best_expectancy_r=0.0,
            best_spec_id=None,
            elapsed_seconds=0.0,
            status='running',
            last_checkpoint_at=datetime.now().isoformat(),
            checkpoint_count=0
        )

    def _run_backtest_loop(self) -> bool:
        """
        Main backtest loop.

        Returns:
            True if completed successfully, False otherwise
        """
        # Generate strategy candidates
        candidates_gen = self._generate_candidates()

        # Skip to resume point if resuming
        if self.checkpoint.candidates_completed > 0:
            logger.info(f"Skipping to candidate {self.checkpoint.candidates_completed + 1}...")
            for _ in range(self.checkpoint.candidates_completed):
                try:
                    next(candidates_gen)
                except StopIteration:
                    break

        # Backtest each candidate
        for spec in candidates_gen:
            if self.should_stop:
                logger.info("Stop requested, saving checkpoint...")
                return False

            # Check runtime limit
            if self.config.max_runtime_hours:
                elapsed_hours = (time.time() - self.start_time) / 3600
                if elapsed_hours >= self.config.max_runtime_hours:
                    logger.warning(f"Runtime limit reached ({self.config.max_runtime_hours}h)")
                    return False

            # Backtest this candidate
            logger.info(f"[{self.checkpoint.candidates_completed + 1}/{self.checkpoint.total_candidates_planned}] "
                       f"Testing {spec.spec_id}...")

            result = self._backtest_strategy(spec)

            # Save result
            self.persistence.save_candidate(self.config.run_id, spec, result)

            # Update checkpoint
            self.checkpoint.candidates_completed += 1
            self.checkpoint.last_completed_spec_id = spec.spec_id
            self.checkpoint.elapsed_seconds = time.time() - self.start_time

            # Check if survivor
            if result and result.passes_gates(self.config):
                self.checkpoint.candidates_passed += 1

                # Save as survivor
                survival_score = self._calculate_survival_score(result)
                confidence = self._determine_confidence(result)

                self.persistence.save_survivor(
                    self.config.run_id,
                    spec,
                    result,
                    survival_score,
                    confidence
                )

                # Update best
                if result.expectancy_r > self.checkpoint.best_expectancy_r:
                    self.checkpoint.best_expectancy_r = result.expectancy_r
                    self.checkpoint.best_spec_id = spec.spec_id

                logger.info(f"  SURVIVOR! Exp: {result.expectancy_r:.3f}R, Score: {survival_score:.1f}, "
                           f"Confidence: {confidence}")
            else:
                if result:
                    logger.info(f"  Failed gates: {result.total_trades} trades, {result.expectancy_r:.3f}R exp")
                else:
                    logger.info(f"  No trades generated")

            # Save checkpoint if needed
            if self._should_save_checkpoint():
                self._save_checkpoint()

        # Completed all candidates
        return True

    def _generate_candidates(self) -> Generator[StrategySpec, None, None]:
        """
        Generate strategy candidates based on search mode.

        Yields:
            StrategySpec for each candidate
        """
        if self.config.search_mode == 'grid':
            yield from self._generate_grid_candidates()
        elif self.config.search_mode == 'random':
            yield from self._generate_random_candidates()
        else:
            raise ValueError(f"Unknown search mode: {self.config.search_mode}")

    def _generate_grid_candidates(self) -> Generator[StrategySpec, None, None]:
        """
        Generate candidates using grid search.

        Simple implementation: vary RR and ORB time for MGC.

        Yields:
            StrategySpec for each grid point
        """
        instruments = ['MGC']  # Can expand to NQ, MPL
        orb_times = ['0900', '1000', '1100', '1800', '2300', '0030']
        rr_values = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 8.0]
        sl_modes = ['HALF', 'FULL']

        count = 0
        for instrument in instruments:
            for orb_time in orb_times:
                for rr in rr_values:
                    for sl_mode in sl_modes:
                        if count >= self.config.max_iters:
                            return

                        spec = StrategySpec(
                            spec_id=generate_spec_id(instrument, orb_time, count),
                            name=f"{instrument}_{orb_time}_RR{rr}_{sl_mode}",
                            instrument=instrument,
                            orb_time=orb_time,
                            orb_minutes=5,
                            entry_rule='breakout',
                            scan_start_local=f"{int(orb_time[:2]):02d}:05",
                            scan_end_local='17:00',
                            crosses_midnight=orb_time in ['2300', '0030'],
                            sl_mode=sl_mode,
                            rr=rr,
                            orb_size_filter=None,
                            directional_bias_required=False,
                            max_hold_end_local='17:00'
                        )

                        yield spec
                        count += 1

    def _generate_random_candidates(self) -> Generator[StrategySpec, None, None]:
        """
        Generate candidates using random search.

        Currently uses grid search as base. For true random search, implement:
        - Random sampling from continuous RR range (1.0-10.0)
        - Random ORB times selection
        - Random filter combinations

        Yields:
            StrategySpec for each random point
        """
        import random
        if self.config.seed:
            random.seed(self.config.seed)

        # For now, use grid search with deterministic seed
        # Future: Implement true random sampling
        yield from self._generate_grid_candidates()

    def _backtest_strategy(self, spec: StrategySpec) -> Optional[ResultRow]:
        """
        Backtest a strategy spec.

        Args:
            spec: Strategy specification

        Returns:
            ResultRow with backtest results or None if failed
        """
        try:
            start_time = time.time()

            # Convert StrategySpec to candidate dict format expected by backtest engine
            candidate_dict = self._spec_to_candidate_dict(spec)

            # Run backtest using existing engine
            trades = backtest_candidate(
                candidate_dict,
                start_date=self.config.start_date,
                end_date=self.config.end_date
            )

            duration = time.time() - start_time

            if not trades:
                return ResultRow(
                    run_id=self.config.run_id,
                    spec_id=spec.spec_id,
                    tested_at=datetime.now().isoformat(),
                    total_trades=0,
                    wins=0,
                    losses=0,
                    time_exits=0,
                    win_rate=0.0,
                    avg_r=0.0,
                    expectancy_r=0.0,
                    total_r=0.0,
                    max_drawdown_r=0.0,
                    largest_win_r=0.0,
                    largest_loss_r=0.0,
                    backtest_duration_seconds=duration,
                    status='completed'
                )

            # Calculate metrics
            metrics = calculate_metrics(trades)

            # Calculate max drawdown
            max_dd = self._calculate_max_drawdown(trades)

            # Calculate annual metrics
            days_in_period = (
                datetime.strptime(self.config.end_date, '%Y-%m-%d') -
                datetime.strptime(self.config.start_date, '%Y-%m-%d')
            ).days
            years = days_in_period / 365.25
            annual_trades = metrics['total_trades'] / years if years > 0 else 0
            annual_expectancy_r = metrics['avg_r'] * annual_trades

            return ResultRow(
                run_id=self.config.run_id,
                spec_id=spec.spec_id,
                tested_at=datetime.now().isoformat(),
                total_trades=metrics['total_trades'],
                wins=metrics['wins'],
                losses=metrics['losses'],
                time_exits=metrics.get('time_exits', 0),
                win_rate=metrics['win_rate'],
                avg_r=metrics['avg_r'],
                expectancy_r=metrics['avg_r'],  # Same as avg_r for our purposes
                total_r=metrics['total_r'],
                max_drawdown_r=max_dd,
                largest_win_r=metrics.get('avg_win_r', 0.0),
                largest_loss_r=abs(metrics.get('avg_loss_r', 0.0)),
                annual_trades=annual_trades,
                annual_expectancy_r=annual_expectancy_r,
                backtest_duration_seconds=duration,
                status='completed'
            )

        except Exception as e:
            logger.error(f"Backtest failed for {spec.spec_id}: {e}")
            return ResultRow(
                run_id=self.config.run_id,
                spec_id=spec.spec_id,
                tested_at=datetime.now().isoformat(),
                total_trades=0,
                wins=0,
                losses=0,
                time_exits=0,
                win_rate=0.0,
                avg_r=0.0,
                expectancy_r=0.0,
                total_r=0.0,
                max_drawdown_r=0.0,
                largest_win_r=0.0,
                largest_loss_r=0.0,
                backtest_duration_seconds=0.0,
                status='failed',
                failure_reason=str(e)
            )

    def _spec_to_candidate_dict(self, spec: StrategySpec) -> dict:
        """Convert StrategySpec to candidate dict for backtest engine."""
        from datetime import time as dt_time

        # Parse scan times
        scan_start_h, scan_start_m = map(int, spec.scan_start_local.split(':'))
        scan_end_h, scan_end_m = map(int, spec.scan_end_local.split(':'))

        return {
            'candidate_id': 0,  # Not used
            'name': spec.name,
            'instrument': spec.instrument,
            'test_config_json': {
                'orb_time': spec.orb_time,
                'target_rule': f"{spec.rr}R",
                'stop_rule': f"ORB {'midpoint (HALF mode)' if spec.sl_mode == 'HALF' else 'opposite (FULL mode)'}",
                'scan_window': f"{spec.scan_start_local} → {spec.scan_end_local}",
                'entry_rule': spec.entry_rule
            },
            'filter_spec_json': {
                'description': '',
                'type': ''
            }
        }

    def _calculate_survival_score(self, result: ResultRow) -> float:
        """Calculate survival score (0-100)."""
        score = 0.0

        # Expectancy component (0-50 points)
        if result.expectancy_r > 0.5:
            score += 50
        elif result.expectancy_r > 0.3:
            score += 40
        elif result.expectancy_r > 0.2:
            score += 30
        elif result.expectancy_r > 0.15:
            score += 20
        elif result.expectancy_r > 0:
            score += 10

        # Sample size component (0-30 points)
        if result.total_trades >= 200:
            score += 30
        elif result.total_trades >= 100:
            score += 25
        elif result.total_trades >= 50:
            score += 20
        elif result.total_trades >= 30:
            score += 10

        # Win rate component (0-20 points)
        if result.win_rate >= 60:
            score += 20
        elif result.win_rate >= 50:
            score += 15
        elif result.win_rate >= 40:
            score += 10
        elif result.win_rate >= 30:
            score += 5

        return min(100.0, score)

    def _determine_confidence(self, result: ResultRow) -> str:
        """Determine confidence level."""
        if result.total_trades >= 200 and result.expectancy_r >= 0.3:
            return 'VERY_HIGH'
        elif result.total_trades >= 100 and result.expectancy_r >= 0.2:
            return 'HIGH'
        elif result.total_trades >= 50 and result.expectancy_r >= 0.15:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _calculate_max_drawdown(self, trades: List) -> float:
        """
        Calculate maximum drawdown in R multiples.

        Args:
            trades: List of Trade objects

        Returns:
            Maximum drawdown in R (positive number)
        """
        if not trades:
            return 0.0

        # Build equity curve
        cumulative_r = 0.0
        peak_r = 0.0
        max_dd = 0.0

        for trade in trades:
            cumulative_r += trade.r_multiple
            peak_r = max(peak_r, cumulative_r)
            drawdown = peak_r - cumulative_r
            max_dd = max(max_dd, drawdown)

        return max_dd

    def _should_save_checkpoint(self) -> bool:
        """Check if checkpoint should be saved."""
        # Save every N candidates
        if self.checkpoint.candidates_completed % self.config.checkpoint_every_n == 0:
            return True

        # Save every M minutes
        elapsed_minutes = (time.time() - self.last_checkpoint_time) / 60
        if elapsed_minutes >= self.config.checkpoint_every_minutes:
            return True

        return False

    def _save_checkpoint(self):
        """Save checkpoint."""
        self.checkpoint.checkpoint_count += 1
        self.checkpoint.checkpoint_id = generate_checkpoint_id(
            self.config.run_id,
            self.checkpoint.checkpoint_count
        )
        self.checkpoint.last_checkpoint_at = datetime.now().isoformat()

        self.checkpoint_manager.save_checkpoint(self.checkpoint)
        self.last_checkpoint_time = time.time()
