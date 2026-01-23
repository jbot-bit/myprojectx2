"""
Market State Detection

Evaluates current market conditions to match conditional edges.

Key conditions detected:
- asia_bias: Price position relative to Asia session range (ABOVE/BELOW/INSIDE)
- pre_orb_trend: NOT IMPLEMENTED YET (requires intraday bars)
- orb_size: NOT IMPLEMENTED YET (calculated at ORB formation)

This module is PURE - no side effects, no database writes, easily testable.
"""

import duckdb
from typing import Dict, Optional
from datetime import date
from pathlib import Path
import os


def get_database_path() -> Path:
    """Get database path from environment or default location."""
    db_path_str = os.getenv("DUCKDB_PATH", "data/db/gold.db")
    return Path(db_path_str)


def get_asia_range(db_path: Optional[Path] = None, target_date: Optional[date] = None) -> Optional[Dict[str, float]]:
    """
    Get Asia session range for a specific date.

    Args:
        db_path: Path to database (default: from env or data/db/gold.db)
        target_date: Date to query (default: today)

    Returns:
        Dict with keys: asia_high, asia_low, asia_range
        None if no data found
    """
    if db_path is None:
        db_path = get_database_path()

    if target_date is None:
        target_date = date.today()

    try:
        conn = duckdb.connect(str(db_path), read_only=True)

        result = conn.execute("""
            SELECT asia_high, asia_low, asia_range
            FROM daily_features_v2
            WHERE date_local = ? AND instrument = 'MGC'
        """, [target_date]).fetchone()

        conn.close()

        if result is None:
            return None

        return {
            'asia_high': float(result[0]) if result[0] is not None else None,
            'asia_low': float(result[1]) if result[1] is not None else None,
            'asia_range': float(result[2]) if result[2] is not None else None,
        }

    except Exception as e:
        print(f"ERROR loading Asia range: {e}")
        return None


def detect_asia_bias(current_price: float, asia_high: float, asia_low: float) -> str:
    """
    Determine price position relative to Asia range.

    Args:
        current_price: Current market price
        asia_high: Asia session high
        asia_low: Asia session low

    Returns:
        "ABOVE" if price > asia_high
        "BELOW" if price < asia_low
        "INSIDE" if asia_low <= price <= asia_high
    """
    if current_price > asia_high:
        return "ABOVE"
    elif current_price < asia_low:
        return "BELOW"
    else:
        return "INSIDE"


def get_market_state(
    current_price: float,
    db_path: Optional[Path] = None,
    target_date: Optional[date] = None
) -> Dict[str, str]:
    """
    Get current market state for condition matching.

    Args:
        current_price: Current market price
        db_path: Path to database (default: from env)
        target_date: Date to query (default: today)

    Returns:
        Dict with market state conditions:
        {
            'asia_bias': 'ABOVE'|'BELOW'|'INSIDE'|'UNKNOWN',
            'asia_high': float,
            'asia_low': float,
            'asia_range': float
        }

    Example:
        >>> state = get_market_state(current_price=2650.5)
        >>> print(state['asia_bias'])
        'ABOVE'
    """
    asia_data = get_asia_range(db_path, target_date)

    if asia_data is None or asia_data['asia_high'] is None or asia_data['asia_low'] is None:
        return {
            'asia_bias': 'UNKNOWN',
            'asia_high': None,
            'asia_low': None,
            'asia_range': None
        }

    asia_bias = detect_asia_bias(
        current_price,
        asia_data['asia_high'],
        asia_data['asia_low']
    )

    return {
        'asia_bias': asia_bias,
        'asia_high': asia_data['asia_high'],
        'asia_low': asia_data['asia_low'],
        'asia_range': asia_data['asia_range']
    }


def get_potential_states(current_price: float, asia_high: float, asia_low: float) -> Dict[str, str]:
    """
    Get potential market states if price moves.

    Args:
        current_price: Current market price
        asia_high: Asia session high
        asia_low: Asia session low

    Returns:
        Dict of potential states:
        {
            'if_price_above': 'ABOVE' (what happens if price breaks above),
            'if_price_below': 'BELOW' (what happens if price breaks below)
        }

    This helps show "potential edges" - what becomes active if conditions change.
    """
    current_bias = detect_asia_bias(current_price, asia_high, asia_low)

    potential = {}

    if current_bias == 'INSIDE':
        # Inside range - can go either direction
        potential['if_breaks_above'] = 'ABOVE'
        potential['if_breaks_below'] = 'BELOW'
    elif current_bias == 'ABOVE':
        # Already above - only other potential is back inside
        potential['if_returns_inside'] = 'INSIDE'
    elif current_bias == 'BELOW':
        # Already below - only other potential is back inside
        potential['if_returns_inside'] = 'INSIDE'

    return potential


if __name__ == "__main__":
    """Test market state detection."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python market_state.py <current_price> [date YYYY-MM-DD]")
        print("\nExample: python market_state.py 2650.5")
        print("Example: python market_state.py 2650.5 2026-01-15")
        sys.exit(1)

    current_price = float(sys.argv[1])
    target_date = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()

    print("=" * 70)
    print("MARKET STATE DETECTION")
    print("=" * 70)
    print(f"Date: {target_date}")
    print(f"Current Price: ${current_price:.2f}")

    # Get market state
    state = get_market_state(current_price, target_date=target_date)

    print(f"\nAsia Session Range:")
    if state['asia_high'] is not None:
        print(f"  High: ${state['asia_high']:.2f}")
        print(f"  Low:  ${state['asia_low']:.2f}")
        print(f"  Range: ${state['asia_range']:.2f}")
    else:
        print("  No data available")

    print(f"\nMarket State:")
    print(f"  asia_bias: {state['asia_bias']}")

    # Show potential states
    if state['asia_high'] is not None:
        potential = get_potential_states(current_price, state['asia_high'], state['asia_low'])
        if potential:
            print(f"\nPotential States (if price moves):")
            for condition, bias in potential.items():
                print(f"  {condition}: {bias}")

    print("=" * 70)
