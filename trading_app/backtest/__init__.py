"""
Backtest Engine Package

Zero-lookahead compliant backtesting for candidate strategies.

CANONICAL ENGINE: trading_app/backtest/engine.py
This is the ONE source of truth for ORB calculation, entry/exit simulation, and metrics.
"""

from trading_app.backtest.engine import (
    CandidateSpec,
    Trade,
    backtest_candidate,
    calculate_metrics,
    parse_candidate_spec
)

__all__ = [
    'CandidateSpec',
    'Trade',
    'backtest_candidate',
    'calculate_metrics',
    'parse_candidate_spec'
]
