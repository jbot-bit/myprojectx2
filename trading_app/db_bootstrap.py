"""
Database bootstrap utilities for ensuring required tables exist at app startup.
"""

import logging
from typing import Iterable

from cloud_mode import get_database_connection

logger = logging.getLogger(__name__)


EDGE_CANDIDATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS edge_candidates (
    candidate_id INTEGER PRIMARY KEY,
    created_at_utc TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    instrument VARCHAR,
    name VARCHAR,
    hypothesis_text VARCHAR,
    status VARCHAR DEFAULT 'DRAFT',
    test_window_start DATE,
    test_window_end DATE,
    approved_at TIMESTAMP,
    approved_by VARCHAR,
    promoted_validated_setup_id INTEGER,
    promoted_by VARCHAR,
    promoted_at TIMESTAMP,
    notes VARCHAR,
    metrics_json JSON,
    robustness_json JSON,
    slippage_assumptions_json JSON,
    filter_spec_json JSON,
    feature_spec_json JSON,
    code_version VARCHAR,
    data_version VARCHAR,
    test_config_json JSON
);
"""

VALIDATED_SETUPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS validated_setups (
    setup_id VARCHAR PRIMARY KEY,
    instrument VARCHAR,
    orb_time VARCHAR,
    rr DOUBLE,
    sl_mode VARCHAR,
    close_confirmations INTEGER,
    buffer_ticks DOUBLE,
    orb_size_filter DOUBLE,
    atr_filter DOUBLE,
    min_gap_filter DOUBLE,
    trades INTEGER,
    win_rate DOUBLE,
    avg_r DOUBLE,
    annual_trades INTEGER,
    tier VARCHAR,
    notes VARCHAR,
    validated_date DATE,
    data_source VARCHAR
);
"""

<<<<<<< HEAD
AI_CHAT_HISTORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_chat_history (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR,
    role VARCHAR,
    content TEXT,
    context_data JSON,
    instrument VARCHAR,
    tags VARCHAR[]
);
"""

=======
>>>>>>> origin/snapshot/full-repo-2026-01-212222

def ensure_required_tables(conn, statements: Iterable[str] | None = None) -> None:
    """
    Ensure required tables exist in the target database.

    Args:
        conn: DuckDB connection object.
        statements: Optional iterable of SQL statements to run.
    """
    statements_to_run = list(statements) if statements is not None else [
        EDGE_CANDIDATES_SCHEMA,
        VALIDATED_SETUPS_SCHEMA,
<<<<<<< HEAD
        AI_CHAT_HISTORY_SCHEMA,
=======
>>>>>>> origin/snapshot/full-repo-2026-01-212222
    ]

    for statement in statements_to_run:
        conn.execute(statement)


def bootstrap_database() -> bool:
    """
    Bootstrap database schema for app startup.

    Returns:
        True if bootstrap succeeded, False otherwise.
    """
    try:
        conn = get_database_connection(read_only=False)
        ensure_required_tables(conn)
        conn.commit()
        conn.close()
        logger.info("Database bootstrap completed successfully.")
        return True
    except Exception as exc:
        logger.error(f"Database bootstrap failed: {exc}")
        return False
