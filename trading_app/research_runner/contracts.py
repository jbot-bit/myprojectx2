"""
Research Runner Contracts

Data structures for the resumable research runner system.
All structures are JSON-serializable for checkpoint persistence.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


@dataclass
class StrategySpec:
    """
    Strategy specification for backtesting.

    Defines all parameters needed to run a backtest:
    - Instrument and timeframe
    - Entry/exit rules
    - Risk management
    - Filters
    """
    # Identification
    spec_id: str  # Unique identifier for this spec
    name: str  # Human-readable name

    # Instrument
    instrument: str  # 'MGC', 'MNQ', 'MPL'

    # ORB parameters
    orb_time: str  # '0900', '1000', '1100', '1800', '2300', '0030'
    orb_minutes: int = 5  # ORB window size

    # Entry rule
    entry_rule: str = 'breakout'  # 'breakout', 'rejection', 'fade'
    scan_start_local: str = '09:05'  # HH:MM format
    scan_end_local: str = '17:00'  # HH:MM format
    crosses_midnight: bool = False  # Scan window crosses midnight

    # Risk management
    sl_mode: str = 'HALF'  # 'HALF' or 'FULL'
    rr: float = 2.0  # Risk/reward ratio

    # Filters
    orb_size_filter: Optional[float] = None  # Min ORB size as % of ATR
    directional_bias_required: bool = False
    session_dependency: Optional[str] = None  # 'compression', 'alignment', etc.

    # Additional params
    max_hold_end_local: str = '17:00'  # Max hold until time
    additional_filters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StrategySpec':
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'StrategySpec':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class RunConfig:
    """
    Configuration for a research run.

    Defines the search space, date range, and execution parameters.
    """
    # Identification
    run_id: str  # Unique run identifier
    created_at: str  # ISO timestamp

    # Date range
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD

    # Search space
    search_mode: str = 'grid'  # 'grid', 'random', 'latin_hypercube'
    max_iters: int = 1000  # Max candidates to test
    seed: Optional[int] = None  # RNG seed for reproducibility

    # Execution limits
    max_runtime_hours: Optional[float] = None  # Max runtime before forced stop
    max_concurrent: int = 1  # Parallel execution (future)

    # Checkpoint config
    checkpoint_every_n: int = 50  # Save checkpoint every N strategies
    checkpoint_every_minutes: int = 15  # Save checkpoint every M minutes

    # Survivor gates
    min_trades: int = 50  # Minimum trades required
    min_expectancy_r: float = 0.15  # Minimum expectancy
    max_drawdown_r: float = 50.0  # Maximum drawdown

    # Validation stages
    enable_oos_validation: bool = True  # Run out-of-sample validation
    enable_stress_tests: bool = True  # Run stress tests

    # Additional metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RunConfig':
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'RunConfig':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ResultRow:
    """
    Single strategy backtest result.

    Contains all performance metrics for a tested strategy.
    """
    # Identification
    run_id: str
    spec_id: str
    tested_at: str  # ISO timestamp

    # Basic metrics
    total_trades: int
    wins: int
    losses: int
    time_exits: int

    # Performance
    win_rate: float  # Percentage
    avg_r: float  # Average R-multiple
    expectancy_r: float  # Expected R per trade
    total_r: float  # Cumulative R

    # Risk metrics
    max_drawdown_r: float  # Max drawdown in R
    largest_win_r: float
    largest_loss_r: float

    # Distribution
    profit_factor: Optional[float] = None  # Gross profit / gross loss
    sharpe_ratio: Optional[float] = None  # Risk-adjusted return

    # Trade quality
    mae_avg_r: float = 0.0  # Average max adverse excursion
    mfe_avg_r: float = 0.0  # Average max favorable excursion
    avg_time_to_resolution_minutes: float = 0.0

    # Annual metrics
    annual_trades: float = 0.0  # Trades per year
    annual_expectancy_r: float = 0.0  # Expected R per year

    # Metadata
    backtest_duration_seconds: float = 0.0
    status: str = 'completed'  # 'completed', 'failed', 'skipped'
    failure_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResultRow':
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'ResultRow':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def passes_gates(self, config: RunConfig) -> bool:
        """Check if this result passes the survivor gates."""
        if self.status != 'completed':
            return False

        if self.total_trades < config.min_trades:
            return False

        if self.expectancy_r < config.min_expectancy_r:
            return False

        if abs(self.max_drawdown_r) > config.max_drawdown_r:
            return False

        return True


@dataclass
class CheckpointState:
    """
    Checkpoint state for resumable execution.

    Contains everything needed to resume a research run from where it left off.
    """
    # Run identification
    run_id: str
    checkpoint_id: str  # Unique checkpoint ID
    created_at: str  # ISO timestamp

    # Progress tracking
    total_candidates_planned: int  # Total candidates in search space
    candidates_completed: int  # Number completed so far
    candidates_passed: int  # Number that passed gates
    last_completed_spec_id: Optional[str] = None  # Last spec tested

    # Search space cursor
    search_cursor: Dict[str, Any] = field(default_factory=dict)  # Current position in search space
    rng_state: Optional[str] = None  # Serialized RNG state for reproducibility

    # Results summary
    best_expectancy_r: float = 0.0
    best_spec_id: Optional[str] = None

    # Timing
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None

    # Status
    status: str = 'running'  # 'running', 'paused', 'completed', 'failed'
    error_message: Optional[str] = None

    # Metadata
    last_checkpoint_at: str = ""  # ISO timestamp of last checkpoint
    checkpoint_count: int = 0  # Number of checkpoints saved

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckpointState':
        """Create from dictionary."""
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'CheckpointState':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.total_candidates_planned == 0:
            return 0.0
        return (self.candidates_completed / self.total_candidates_planned) * 100


# Helper functions
def generate_run_id() -> str:
    """Generate unique run ID."""
    return f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_checkpoint_id(run_id: str, checkpoint_num: int) -> str:
    """Generate unique checkpoint ID."""
    return f"{run_id}_ckpt_{checkpoint_num:04d}"


def generate_spec_id(instrument: str, orb_time: str, variation: int = 0) -> str:
    """Generate unique strategy spec ID."""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    return f"spec_{instrument}_{orb_time}_{variation:03d}_{timestamp}"
