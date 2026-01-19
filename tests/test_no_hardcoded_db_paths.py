"""
Test for hardcoded database connections.

Uses AST scanning to find files that call duckdb.connect() without routing through
the canonical connection module (trading_app/cloud_mode.py).

Allowed exceptions:
- cloud_mode.py itself (the canonical module)
- Data pipeline scripts (backfill, feature building)
- Test files
- Archived code

Run:
    pytest tests/test_no_hardcoded_db_paths.py -v
"""

import pytest
import ast
from pathlib import Path
from typing import List, Tuple
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class DuckDBConnectFinder(ast.NodeVisitor):
    """AST visitor to find duckdb.connect() calls."""

    def __init__(self):
        self.violations = []
        self.has_duckdb_import = False

    def visit_Import(self, node):
        """Check for 'import duckdb'."""
        for alias in node.names:
            if alias.name == "duckdb":
                self.has_duckdb_import = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Check for 'from duckdb import ...'."""
        if node.module == "duckdb":
            self.has_duckdb_import = True
        self.generic_visit(node)

    def visit_Call(self, node):
        """Check for duckdb.connect() calls."""
        # Check for duckdb.connect()
        if isinstance(node.func, ast.Attribute):
            if (
                isinstance(node.func.value, ast.Name)
                and node.func.value.id == "duckdb"
                and node.func.attr == "connect"
            ):
                self.violations.append({
                    "lineno": node.lineno,
                    "col_offset": node.col_offset,
                    "type": "duckdb.connect() call"
                })

        self.generic_visit(node)


def is_allowed_exception(file_path: Path, repo_root: Path) -> Tuple[bool, str]:
    """
    Check if file is an allowed exception for hardcoded connections.

    Returns:
        (is_allowed, reason)
    """
    rel_path = file_path.relative_to(repo_root)
    rel_path_str = str(rel_path).replace("\\", "/")

    # Exception 1: Canonical connection module itself
    if rel_path_str == "trading_app/cloud_mode.py":
        return True, "Canonical connection module"

    # Exception 2: Archived code
    if rel_path_str.startswith("_archive/") or rel_path_str.startswith("_INVALID_SCRIPTS_ARCHIVE/"):
        return True, "Archived code"

    # Exception 3: Backfill scripts
    backfill_patterns = ["backfill_", "ingest_", "migrate_"]
    if any(pattern in file_path.name for pattern in backfill_patterns):
        return True, "Data pipeline script (backfill/ingest/migrate)"

    # Exception 4: Feature building scripts
    if "build_daily_features" in file_path.name or "build_5m" in file_path.name:
        return True, "Feature building script"

    # Exception 5: Test and admin scripts
    admin_patterns = ["test_", "check_", "audit_", "validate_", "diagnose_", "populate_", "init_db"]
    if any(pattern in file_path.name for pattern in admin_patterns):
        return True, "Test/admin script"

    # Exception 6: Scripts directory (data pipeline)
    if rel_path_str.startswith("scripts/"):
        return True, "Data pipeline script (scripts/)"

    # Exception 7: EDE (Edge Discovery Engine) and audits
    if rel_path_str.startswith("ede/") or rel_path_str.startswith("audits/"):
        return True, "EDE or audit infrastructure"

    # Exception 8: ML training/monitoring
    if rel_path_str.startswith("ml_training/") or rel_path_str.startswith("ml_monitoring/"):
        return True, "ML infrastructure"

    # Exception 9: Standalone query/analysis tools
    analysis_files = ["query_engine.py", "analyze_orb_v2.py", "export_v2_edges.py", "ai_query.py"]
    if file_path.name in analysis_files:
        return True, "Standalone analysis tool"

    return False, ""


def scan_file_for_hardcoded_connections(file_path: Path, repo_root: Path) -> List[dict]:
    """
    Scan a Python file for hardcoded duckdb.connect() calls.

    Returns:
        List of violations with file path, line number, and details
    """
    # Check if allowed exception
    is_allowed, reason = is_allowed_exception(file_path, repo_root)
    if is_allowed:
        return []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        finder = DuckDBConnectFinder()
        finder.visit(tree)

        # Only report if file has duckdb import AND violations
        if finder.has_duckdb_import and finder.violations:
            rel_path = file_path.relative_to(repo_root)
            return [
                {
                    "file": str(rel_path).replace("\\", "/"),
                    "line": v["lineno"],
                    "type": v["type"]
                }
                for v in finder.violations
            ]

    except (SyntaxError, UnicodeDecodeError):
        # Skip files with syntax errors or encoding issues
        pass

    return []


def test_no_hardcoded_db_paths_in_trading_app():
    """Test that trading_app/ has no hardcoded database connections."""
    repo_root = Path(__file__).parent.parent
    trading_app_dir = repo_root / "trading_app"

    if not trading_app_dir.exists():
        pytest.skip("trading_app/ directory not found")

    violations = []

    # Scan all Python files in trading_app/
    for py_file in trading_app_dir.rglob("*.py"):
        file_violations = scan_file_for_hardcoded_connections(py_file, repo_root)
        violations.extend(file_violations)

    if violations:
        violation_report = "\n".join(
            f"  - {v['file']}:{v['line']} - {v['type']}"
            for v in violations
        )
        pytest.fail(
            f"Found {len(violations)} hardcoded database connection(s) in trading_app/:\n"
            f"{violation_report}\n\n"
            f"All database connections must route through:\n"
            f"  from trading_app.cloud_mode import get_database_connection\n"
            f"  conn = get_database_connection()"
        )


def test_no_hardcoded_db_paths_in_root():
    """Test that root-level Python files have no hardcoded connections."""
    repo_root = Path(__file__).parent.parent

    violations = []

    # Scan Python files in root directory
    for py_file in repo_root.glob("*.py"):
        file_violations = scan_file_for_hardcoded_connections(py_file, repo_root)
        violations.extend(file_violations)

    if violations:
        violation_report = "\n".join(
            f"  - {v['file']}:{v['line']} - {v['type']}"
            for v in violations
        )
        pytest.fail(
            f"Found {len(violations)} hardcoded database connection(s) in root:\n"
            f"{violation_report}\n\n"
            f"Use canonical connection module:\n"
            f"  from trading_app.cloud_mode import get_database_connection"
        )


def test_cloud_mode_is_sole_connection_provider():
    """Test that cloud_mode.py exists and has connection functions."""
    repo_root = Path(__file__).parent.parent
    cloud_mode_file = repo_root / "trading_app" / "cloud_mode.py"

    assert cloud_mode_file.exists(), "Canonical connection module (cloud_mode.py) not found"

    # Check that it has the required functions
    with open(cloud_mode_file, 'r') as f:
        content = f.read()

    required_functions = [
        "get_database_connection",
        "get_motherduck_connection",
        "is_cloud_deployment"
    ]

    missing_functions = []
    for func in required_functions:
        if f"def {func}" not in content:
            missing_functions.append(func)

    assert len(missing_functions) == 0, (
        f"cloud_mode.py missing required functions: {', '.join(missing_functions)}"
    )


def test_all_active_imports_use_cloud_mode():
    """Test that all active code imports from cloud_mode, not db_router."""
    repo_root = Path(__file__).parent.parent

    # Search for db_router imports in active code (not _archive)
    db_router_imports = []

    for py_file in repo_root.rglob("*.py"):
        rel_path = py_file.relative_to(repo_root)
        rel_path_str = str(rel_path).replace("\\", "/")

        # Skip archived code
        if rel_path_str.startswith("_archive/") or rel_path_str.startswith("_INVALID_SCRIPTS_ARCHIVE/"):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            if "from db_router import" in content or "import db_router" in content:
                db_router_imports.append(rel_path_str)

        except (UnicodeDecodeError, PermissionError):
            pass

    assert len(db_router_imports) == 0, (
        f"Found {len(db_router_imports)} file(s) importing from db_router (should use cloud_mode):\n" +
        "\n".join(f"  - {f}" for f in db_router_imports) +
        "\n\ndb_router.py is deprecated. Use cloud_mode.py instead."
    )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
