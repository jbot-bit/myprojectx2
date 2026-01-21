"""
Guard Test: Ensure Only ONE Canonical Backtest Engine

This test prevents "multiple versions" by ensuring there is only ONE real engine
implementation in the codebase. All other files must be shims (re-exports only).

CANONICAL ENGINE: trading_app/backtest/engine.py

This test will FAIL if:
- Any file outside trading_app/backtest/engine.py contains real engine logic
- Multiple files define functions like: backtest_candidate, simulate_trade, calculate_orb

Shims (re-export only imports) are allowed for backward compatibility.

Run:
    pytest tests/test_single_engine_guard.py -v
"""

import pytest
import re
from pathlib import Path


def test_single_canonical_engine():
    """Guard test: Only ONE real engine implementation allowed."""

    # Canonical engine location
    CANONICAL_ENGINE = Path("trading_app/backtest/engine.py")

    # Key functions that define an engine
    ENGINE_FUNCTIONS = [
        "def backtest_candidate",
        "def simulate_trade",
        "def calculate_orb"
    ]

    # Files to scan (exclude test files, archive, venv)
    repo_root = Path(__file__).parent.parent
    py_files = []

    for pattern in ["**/*.py"]:
        for f in repo_root.glob(pattern):
            # Skip excluded directories
            parts = f.relative_to(repo_root).parts
            if any(excluded in parts for excluded in ['_archive', '.venv', 'venv', '__pycache__', '.git', 'tests', 'research']):
                continue
            py_files.append(f)

    # Find files with engine function definitions
    files_with_engine_logic = []

    for py_file in py_files:
        try:
            content = py_file.read_text(encoding='utf-8')

            # Check for engine function definitions
            has_engine_funcs = sum(1 for func in ENGINE_FUNCTIONS if re.search(r'^' + func, content, re.MULTILINE))

            # If file has at least 2 of the 3 key functions, it's an engine
            if has_engine_funcs >= 2:
                # Check if it's a shim (only imports, no real logic)
                # Shims have "from trading_app.backtest" imports and no real function bodies
                is_shim = (
                    'from trading_app.backtest.engine import' in content and
                    'DEPRECATED SHIM' in content
                )

                if not is_shim:
                    files_with_engine_logic.append(py_file.relative_to(repo_root))
        except Exception as e:
            # Skip files that can't be read
            continue

    # Verify only canonical engine exists
    expected_canonical = Path("trading_app/backtest/engine.py")

    # Remove canonical from list
    files_with_engine_logic = [f for f in files_with_engine_logic if f != expected_canonical]

    if files_with_engine_logic:
        error_msg = (
            f"\n\nMULTIPLE ENGINE IMPLEMENTATIONS DETECTED!\n\n"
            f"CANONICAL ENGINE: {expected_canonical}\n\n"
            f"Other files with engine logic (NOT shims):\n"
        )
        for f in files_with_engine_logic:
            error_msg += f"  - {f}\n"
        error_msg += (
            f"\nACTION REQUIRED:\n"
            f"1. Delete duplicate engines, OR\n"
            f"2. Convert them to shims (re-export only, add 'DEPRECATED SHIM' marker)\n\n"
            f"See: research/candidate_backtest_engine.py for shim example\n"
        )
        pytest.fail(error_msg)

    # Verify canonical engine exists
    assert (repo_root / expected_canonical).exists(), \
        f"Canonical engine not found: {expected_canonical}"


def test_canonical_engine_has_required_functions():
    """Verify canonical engine has all required functions."""

    canonical = Path(__file__).parent.parent / "trading_app" / "backtest" / "engine.py"

    assert canonical.exists(), f"Canonical engine not found: {canonical}"

    content = canonical.read_text(encoding='utf-8')

    required_functions = [
        'def backtest_candidate',
        'def simulate_trade',
        'def calculate_orb',
        'def calculate_metrics',
        'def detect_breakout_entry',
        'def apply_filters'
    ]

    missing = []
    for func in required_functions:
        if not re.search(r'^' + func, content, re.MULTILINE):
            missing.append(func.replace('def ', ''))

    assert not missing, f"Canonical engine missing functions: {', '.join(missing)}"


def test_shims_only_import_from_canonical():
    """Verify all shims import from canonical engine (no logic)."""

    # Find potential shim files
    repo_root = Path(__file__).parent.parent
    shim_files = []

    for py_file in repo_root.glob("**/*backtest*.py"):
        # Skip canonical, tests, archive, venv
        parts = py_file.relative_to(repo_root).parts
        if any(excluded in parts for excluded in ['_archive', '.venv', 'venv', '__pycache__', 'tests', 'trading_app/backtest']):
            continue

        try:
            content = py_file.read_text(encoding='utf-8')

            # If file has "DEPRECATED SHIM" marker, it's a shim
            if 'DEPRECATED SHIM' in content:
                shim_files.append(py_file)

                # Verify shim only imports (no function definitions)
                assert 'from trading_app.backtest.engine import' in content, \
                    f"Shim {py_file.name} must import from trading_app.backtest.engine"

                # Check for function definitions (excluding __all__ and imports)
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith('def ') and not line.strip().startswith('def _'):
                        pytest.fail(
                            f"Shim {py_file.name} contains function definition: {line.strip()}\n"
                            f"Shims must ONLY re-export imports (no logic)"
                        )
        except Exception:
            continue

    # Report shims found
    if shim_files:
        print(f"\nFound {len(shim_files)} shim(s):")
        for shim in shim_files:
            print(f"  - {shim.relative_to(repo_root)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
