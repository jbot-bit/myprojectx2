"""
Research Runner - Long-run resumable backtesting system

Provides:
- Resumable search over strategy parameter space
- Checkpoint/restore functionality
- Zero-lookahead compliance
- Deterministic results
- DB persistence
"""

from trading_app.research_runner.contracts import (
    StrategySpec,
    RunConfig,
    ResultRow,
    CheckpointState
)

__all__ = [
    'StrategySpec',
    'RunConfig',
    'ResultRow',
    'CheckpointState'
]
