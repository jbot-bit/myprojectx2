"""
CACHE LAYER - Performance optimization for Streamlit app

Provides cached wrappers around frequently-called database queries.
Uses st.cache_data with appropriate TTLs to reduce database round-trips.

Key optimizations:
1. Validated setups query (changes rarely) - 5 min cache
2. Config generator results (static within session) - 10 min cache
3. Historical data queries (immutable) - Longer cache

Usage:
    from cache_layer import get_cached_validated_setups

    setups = get_cached_validated_setups('MGC')
"""

import streamlit as st
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


@st.cache_data(ttl=300, show_spinner=False)
def get_cached_validated_setups(instrument: str) -> List[Dict]:
    """
    Cached wrapper for setup_detector.get_all_validated_setups().

    TTL: 5 minutes (300 seconds)
    Rationale: validated_setups table changes rarely (only when new setups approved)

    Args:
        instrument: Instrument symbol ('MGC', 'NQ', 'MPL')

    Returns:
        List of validated setup dicts
    """
    from setup_detector import SetupDetector

    detector = SetupDetector()
    return detector.get_all_validated_setups(instrument)


@st.cache_data(ttl=600, show_spinner=False)
def get_cached_instrument_configs(instrument: str) -> Tuple[Dict[str, list], Dict[str, list]]:
    """
    Cached wrapper for config.get_instrument_configs().

    TTL: 10 minutes (600 seconds)
    Rationale: Configs loaded from validated_setups, changes rarely

    Note: config.py already has module-level caching, but this adds
    Streamlit-specific caching for multi-tab switching scenarios.

    Args:
        instrument: Instrument symbol ('MGC', 'NQ', 'MPL')

    Returns:
        Tuple of (orb_configs dict, orb_size_filters dict)
    """
    from config import get_instrument_configs

    return get_instrument_configs(instrument)


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_daily_features(
    instrument: str,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    Cached wrapper for daily_features_v2 queries.

    TTL: 1 hour (3600 seconds)
    Rationale: Historical features are immutable, can cache aggressively

    Args:
        instrument: Instrument symbol ('MGC', 'NQ', 'MPL')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        List of daily feature dicts
    """
    from cloud_mode import get_database_connection

    conn = get_database_connection(read_only=True)
    if conn is None:
        logger.warning("Database connection unavailable for daily features query")
        return []

    query = """
        SELECT *
        FROM daily_features_v2
        WHERE instrument = ?
            AND date_local >= ?
            AND date_local <= ?
        ORDER BY date_local
    """

    try:
        result = conn.execute(query, [instrument, start_date, end_date])
        rows = result.fetchall()
        columns = [desc[0] for desc in result.description]

        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching daily features: {e}")
        return []
    finally:
        conn.close()


def clear_all_caches():
    """
    Clear all Streamlit caches.

    Use this after database updates or when you need fresh data.
    Call from UI with a button: st.button("Refresh Data", on_click=clear_all_caches)
    """
    st.cache_data.clear()
    logger.info("Cleared all Streamlit data caches")


# Expose cache management in UI
def render_cache_controls():
    """
    Render cache control UI elements.

    Use in sidebar:
        from cache_layer import render_cache_controls
        with st.sidebar:
            render_cache_controls()
    """
    with st.expander("🔄 Cache Controls"):
        st.caption("Cached data reduces database queries for faster performance")

        if st.button("Clear All Caches", help="Force refresh all cached data"):
            clear_all_caches()
            st.success("Caches cleared! Data will be refreshed on next access.")
            st.rerun()

        st.caption("""
        **Cache TTLs:**
        - Validated setups: 5 min
        - Instrument configs: 10 min
        - Daily features: 1 hour
        """)
