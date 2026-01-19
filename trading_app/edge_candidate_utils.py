"""
Utility functions for edge_candidates table.

Handles JSON field serialization/deserialization robustly.
Works with both DuckDB JSON type and string representations.
"""

import json
from typing import Any, Dict, Optional


def parse_json_field(value: Any) -> Optional[Dict]:
    """
    Parse a JSON field from DuckDB, handling both JSON and string types.

    Args:
        value: Value from DuckDB (could be JSON, string, or None)

    Returns:
        Parsed dict or None
    """
    if value is None:
        return None

    # If already a dict, return it
    if isinstance(value, dict):
        return value

    # If string, parse it
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # If it's not valid JSON, return None
            return None

    # Unknown type, return None
    return None


def serialize_json_field(value: Optional[Dict]) -> Optional[str]:
    """
    Serialize a dict to JSON string for DuckDB storage.

    Args:
        value: Dict to serialize (or None)

    Returns:
        JSON string or None
    """
    if value is None:
        return None

    if not isinstance(value, dict):
        raise TypeError(f"Expected dict, got {type(value)}")

    return json.dumps(value)


def safe_json_cast(value: Optional[Dict]) -> str:
    """
    Create a safe JSON cast for DuckDB SQL insertion.

    Args:
        value: Dict to serialize

    Returns:
        SQL fragment with JSON casting
    """
    if value is None:
        return "NULL"

    json_str = json.dumps(value)
    # Escape single quotes for SQL
    json_str_escaped = json_str.replace("'", "''")
    return f"'{json_str_escaped}'::JSON"


# Example usage:
#
# Reading from DuckDB:
# -----------------
# result = con.execute("SELECT test_config_json FROM edge_candidates WHERE candidate_id=1").fetchone()
# test_config = parse_json_field(result[0])  # Returns dict or None
#
# if test_config:
#     random_seed = test_config.get("random_seed")
#     walk_forward = test_config.get("walk_forward_windows")
#
#
# Writing to DuckDB:
# -----------------
# test_config = {
#     "random_seed": 42,
#     "walk_forward_windows": 4,
#     "train_pct": 0.7
# }
#
# # Method 1: Using parameterized query with JSON string
# config_json_str = serialize_json_field(test_config)
# con.execute("""
#     UPDATE edge_candidates
#     SET test_config_json = ?::JSON
#     WHERE candidate_id = ?
# """, [config_json_str, candidate_id])
#
# # Method 2: Using safe_json_cast (for dynamic SQL)
# con.execute(f"""
#     UPDATE edge_candidates
#     SET test_config_json = {safe_json_cast(test_config)}
#     WHERE candidate_id = {candidate_id}
# """)
