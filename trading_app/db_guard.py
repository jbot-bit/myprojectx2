"""
Database Guard - Enforces daily_features_v2 as canonical

This module provides a wrapper around DuckDB connections that enforces
the canonical table name for daily features.

HARD FAIL POLICY:
- Any query mentioning "daily_features" (without "_v2") will immediately raise an error
- No warnings, no fallbacks, no silent behavior
- Correctness > convenience

The daily_features (v1) table was never built in production and has been deleted.
Only daily_features_v2 is canonical and accurate (verified by audit 2026-01-22).

See: DAILY_FEATURES_AUDIT_REPORT.md
"""

import re
from typing import Any


class DailyFeaturesV1Error(Exception):
    """
    Raised when code tries to use the deleted daily_features (v1) table.

    This is a hard fail to enforce correctness.
    """
    def __init__(self, query: str):
        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HARD FAIL: Attempted to use deleted table 'daily_features' (v1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The 'daily_features' (v1) table has been DELETED.

It was never built in production and is not accurate.

USE THIS INSTEAD:
  daily_features_v2

The v2 table is the ONLY canonical features table:
  - 100% accurate (verified by ground truth audit)
  - Zero lookahead/leakage
  - Used by all production systems

EVIDENCE:
  - Audit report: DAILY_FEATURES_AUDIT_REPORT.md
  - Audit date: 2026-01-22
  - V1 table rows: 0 (never existed)
  - V2 table rows: 1,780 (production data)

YOUR QUERY (REJECTED):
{query}

FIX:
Replace 'FROM daily_features' with 'FROM daily_features_v2'
Replace 'INTO daily_features' with 'INTO daily_features_v2'

This is a HARD FAIL to enforce correctness.
No warnings, no fallbacks, no silent behavior.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        super().__init__(message)
        self.query = query


def validate_query(query: str) -> None:
    """
    Validate that query does not reference daily_features (v1).

    Args:
        query: SQL query string

    Raises:
        DailyFeaturesV1Error: If query references daily_features without _v2
    """
    # Normalize query for checking (lowercase, remove extra whitespace)
    normalized = re.sub(r'\s+', ' ', query.lower().strip())

    # Check for "daily_features" without "_v2" suffix
    # Pattern: word boundary + "daily_features" + NOT followed by "_v2"
    if re.search(r'\bdaily_features\b(?!_v2)', normalized):
        raise DailyFeaturesV1Error(query)


class GuardedConnection:
    """
    Wrapper around DuckDB connection that validates queries before execution.

    This enforces that no code can access daily_features (v1).
    """

    def __init__(self, conn: Any):
        """
        Wrap a DuckDB connection with validation.

        Args:
            conn: DuckDB connection object
        """
        self._conn = conn

    def execute(self, query: str, *args, **kwargs) -> Any:
        """
        Execute query with validation.

        Args:
            query: SQL query string
            *args, **kwargs: Passed to underlying connection

        Returns:
            Query result from underlying connection

        Raises:
            DailyFeaturesV1Error: If query uses daily_features (v1)
        """
        validate_query(query)
        return self._conn.execute(query, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        """Forward all other attributes/methods to underlying connection."""
        return getattr(self._conn, name)

    def __enter__(self):
        """Support context manager protocol."""
        return self

    def __exit__(self, *args):
        """Support context manager protocol."""
        return self._conn.__exit__(*args)


def get_guarded_connection(conn: Any) -> GuardedConnection:
    """
    Wrap a DuckDB connection with the v1 guard.

    Args:
        conn: DuckDB connection

    Returns:
        GuardedConnection that validates all queries
    """
    return GuardedConnection(conn)
