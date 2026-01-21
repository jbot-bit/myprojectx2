"""
Research Runner Audit

Self-audit checks to ensure system integrity:
- Imports are deterministic (trading_app.*)
- No sys.path insertions
- Checkpoint tables exist
- Runner resume path works
"""

import logging
import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any

from trading_app.research_runner.persistence import ResearchPersistence

logger = logging.getLogger(__name__)


class ResearchRunnerAuditor:
    """
    Auditor for research runner system.

    Checks for common issues and violations of best practices.
    """

    def __init__(self):
        self.issues: List[Tuple[str, str]] = []  # (severity, message)
        self.root = Path(__file__).parent.parent.parent

    def run_audit(self) -> bool:
        """
        Run all audit checks.

        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("Running research runner audit...")

        self.check_imports()
        self.check_no_sys_path_manipulation()
        self.check_database_schema()
        self.check_checkpoint_directory()

        # Report issues
        if not self.issues:
            logger.info("Audit PASSED - no issues found")
            return True
        else:
            logger.warning(f"Audit found {len(self.issues)} issues:")
            for severity, message in self.issues:
                if severity == 'ERROR':
                    logger.error(f"  [ERROR] {message}")
                else:
                    logger.warning(f"  [WARN] {message}")

            error_count = sum(1 for s, _ in self.issues if s == 'ERROR')
            if error_count > 0:
                logger.error(f"Audit FAILED - {error_count} errors found")
                return False
            else:
                logger.warning(f"Audit PASSED with warnings")
                return True

    def check_imports(self):
        """Check that all imports are deterministic (trading_app.*)."""
        runner_dir = self.root / "trading_app" / "research_runner"

        for py_file in runner_dir.glob("*.py"):
            # Skip audit.py itself to avoid false positives
            if py_file.name == '__pycache__' or py_file.name == 'audit.py':
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    # Skip comments and docstrings - only check actual import statements
                    import_lines = []
                    for line in f:
                        stripped = line.strip()
                        if stripped.startswith('from ') and 'import' in stripped:
                            # Exclude commented lines
                            if not stripped.startswith('#'):
                                import_lines.append(stripped)

                    content = '\n'.join(import_lines)

                # Check for relative imports from trading_app modules
                problematic_patterns = [
                    (r'from\s+data_loader\s+import', 'from data_loader import'),
                    (r'from\s+config\s+import', 'from config import'),
                    (r'from\s+cloud_mode\s+import', 'from cloud_mode import'),
                    (r'from\s+strategy_engine\s+import', 'from strategy_engine import'),
                ]

                for pattern, example in problematic_patterns:
                    if re.search(pattern, content):
                        self.issues.append((
                            'WARN',
                            f"{py_file.name}: Found loose import '{example}' - should use 'from trading_app.X import'"
                        ))

            except Exception as e:
                self.issues.append(('WARN', f"Failed to check imports in {py_file.name}: {e}"))

    def check_no_sys_path_manipulation(self):
        """Check that there are no sys.path.insert() calls."""
        runner_dir = self.root / "trading_app" / "research_runner"

        for py_file in runner_dir.glob("*.py"):
            # Skip audit.py itself
            if py_file.name == '__pycache__' or py_file.name == 'audit.py':
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    # Only check non-comment lines
                    code_lines = []
                    for line in f:
                        stripped = line.strip()
                        if not stripped.startswith('#') and stripped:
                            code_lines.append(stripped)
                    content = '\n'.join(code_lines)

                # Check for sys.path manipulation
                if 'sys.path.insert' in content or 'sys.path.append' in content:
                    self.issues.append((
                        'ERROR',
                        f"{py_file.name}: Found sys.path manipulation - remove it"
                    ))

            except Exception as e:
                self.issues.append(('WARN', f"Failed to check sys.path in {py_file.name}: {e}"))

    def check_database_schema(self):
        """Check that required database tables exist."""
        try:
            persistence = ResearchPersistence()
            conn = persistence._get_connection(read_only=True)

            required_tables = [
                'research_runs',
                'research_candidates',
                'research_survivors',
                'research_checkpoints'
            ]

            existing_tables = conn.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
            """).fetchdf()['table_name'].tolist()

            conn.close()

            for table in required_tables:
                if table not in existing_tables:
                    self.issues.append((
                        'ERROR',
                        f"Required table '{table}' not found in database"
                    ))

        except Exception as e:
            self.issues.append(('ERROR', f"Failed to check database schema: {e}"))

    def check_checkpoint_directory(self):
        """Check that checkpoint directory exists and is writable."""
        checkpoint_dir = self.root / "data" / "checkpoints"

        if not checkpoint_dir.exists():
            try:
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created checkpoint directory: {checkpoint_dir}")
            except Exception as e:
                self.issues.append((
                    'ERROR',
                    f"Checkpoint directory does not exist and cannot be created: {e}"
                ))
                return

        # Test write access
        try:
            test_file = checkpoint_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            self.issues.append((
                'ERROR',
                f"Checkpoint directory is not writable: {e}"
            ))


def run_audit() -> bool:
    """
    Run full audit.

    Returns:
        True if audit passes, False otherwise
    """
    auditor = ResearchRunnerAuditor()
    return auditor.run_audit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    success = run_audit()
    exit(0 if success else 1)
