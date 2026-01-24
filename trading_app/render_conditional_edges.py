"""
Render conditional edges display for trading app.

Simple, honest display of:
- Current market state (Asia bias)
- Active edges (conditions met NOW)
- Baseline edges (always available)
- Position sizing guidance (quality multipliers)

NO OVERPROMISING. Shows actual conditions and what's active vs potential.
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import Dict, List, Optional

from setup_detector import SetupDetector


def render_market_state_panel(market_state: Dict) -> None:
    """
    Display current market state in simple, honest terms.

    Args:
        market_state: Dict from market_state.py with asia_bias, etc.
    """
    st.markdown("### Market State")

    if market_state.get('asia_bias') == 'UNKNOWN':
        st.warning("⚠️ No Asia session data available for today")
        return

    # Display Asia bias prominently
    bias = market_state['asia_bias']

    if bias == 'ABOVE':
        st.success(f"✅ **Price ABOVE Asia Range** ({market_state['asia_high']:.2f})")
        st.caption("Conditional setups for ABOVE bias are now active")
    elif bias == 'BELOW':
        st.error(f"✅ **Price BELOW Asia Range** ({market_state['asia_low']:.2f})")
        st.caption("Conditional setups for BELOW bias are now active")
    elif bias == 'INSIDE':
        st.info(f"⏸️ **Price INSIDE Asia Range** ({market_state['asia_low']:.2f} - {market_state['asia_high']:.2f})")
        st.caption("No conditional edges active. Using baseline setups.")

    # Show Asia range for context
    with st.expander("Asia Session Range"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("High", f"${market_state['asia_high']:.2f}")
        with col2:
            st.metric("Low", f"${market_state['asia_low']:.2f}")
        with col3:
            st.metric("Range", f"${market_state['asia_range']:.2f}")


def render_active_edges_panel(
    active_setups: List[Dict],
    baseline_setups: List[Dict],
    current_price: float
) -> None:
    """
    Display active and baseline edges honestly.

    Shows:
    - Active conditional setups (if conditions are met)
    - Baseline setups (always available as fallback)
    - Quality multipliers for position sizing

    Args:
        active_setups: Conditional setups matching current market state
        baseline_setups: Baseline setups (always available)
        current_price: Current market price
    """
    st.markdown("### Available Edges")

    # Active conditional setups (if any)
    if active_setups and len(active_setups) > 0:
        st.markdown("#### 🎯 Active Conditional Edges")
        st.caption("These setups have conditions met RIGHT NOW")

        # Show top 5 active setups
        df_active = pd.DataFrame(active_setups[:5])

        # Format for display
        display_df = pd.DataFrame({
            'ORB': df_active['orb_time'],
            'RR': df_active['rr'],
            'SL': df_active['sl_mode'],
            'Expectancy': df_active['avg_r'].apply(lambda x: f"+{x:.3f}R"),
            'WR': df_active['win_rate'].apply(lambda x: f"{x:.1f}%"),
            'Quality': df_active['quality_multiplier'].apply(lambda x: f"{x:.1f}x"),
            'Condition': df_active.apply(lambda row: f"{row['condition_type']}={row['condition_value']}", axis=1),
            'Tier': df_active['tier']
        })

        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        # Position sizing guidance
        max_quality = df_active['quality_multiplier'].max()
        if max_quality >= 2.5:
            st.success(f"💎 **PREMIUM EDGE ACTIVE** - Best setup is {max_quality}x quality (size accordingly)")
        elif max_quality >= 2.0:
            st.info(f"⭐ **EXCELLENT EDGE** - Best setup is {max_quality}x quality")

    else:
        st.info("ℹ️ No conditional edges active (conditions not met)")

    # Baseline setups (always shown as fallback)
    with st.expander(f"📊 Baseline Setups ({len(baseline_setups)} available)", expanded=not bool(active_setups)):
        st.caption("These setups are ALWAYS available (no conditions required)")

        if baseline_setups and len(baseline_setups) > 0:
            df_baseline = pd.DataFrame(baseline_setups[:5])

            display_df = pd.DataFrame({
                'ORB': df_baseline['orb_time'],
                'RR': df_baseline['rr'],
                'SL': df_baseline['sl_mode'],
                'Expectancy': df_baseline['avg_r'].apply(lambda x: f"+{x:.3f}R"),
                'WR': df_baseline['win_rate'].apply(lambda x: f"{x:.1f}%"),
                'Quality': df_baseline['quality_multiplier'].apply(lambda x: f"{x:.1f}x"),
                'Tier': df_baseline['tier']
            })

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No baseline setups configured")


def render_position_sizing_guide() -> None:
    """Display position sizing guidance based on quality multipliers."""
    with st.expander("📏 Position Sizing Guide"):
        st.markdown("""
        **Quality multipliers indicate edge strength for position sizing:**

        - **3.0x (UNICORN)**: 3x normal size - Crown jewel setups (1.0R+ expectancy)
        - **2.5x (ELITE)**: 2.5x normal size - Exceptional edges (0.8-1.0R)
        - **2.0x (EXCELLENT)**: 2x normal size - Strong edges (0.6-0.8R)
        - **1.5x (GOOD)**: 1.5x normal size - Solid setups (0.4-0.6R)
        - **1.0x (BASELINE)**: 1x normal size - Standard setups

        **Example:** If your standard position is 1 micro contract:
        - 3.0x setup → Trade 3 micros
        - 2.0x setup → Trade 2 micros
        - 1.0x setup → Trade 1 micro

        **IMPORTANT:** Only size up if the conditional edge is ACTIVE (conditions met).
        Don't use conditional quality multipliers for baseline setups.
        """)


def render_conditional_edges_full(
    instrument: str,
    current_price: float,
    target_date: Optional[date] = None
) -> None:
    """
    Full conditional edges panel for trading app.

    Displays:
    1. Current market state
    2. Active conditional edges
    3. Baseline edges (fallback)
    4. Position sizing guidance

    Args:
        instrument: Instrument symbol (e.g., 'MGC')
        current_price: Current market price
        target_date: Date to evaluate (default: today)
    """
    st.markdown("## 🎯 Conditional Edge System")
    st.caption("Honest, real-time edge detection based on market conditions")

    # Initialize detector
    detector = SetupDetector()

    # Get active and baseline setups
    try:
        result = detector.get_active_and_potential_setups(
            instrument=instrument,
            current_price=current_price,
            target_date=target_date
        )

        market_state = result['market_state']
        active_setups = result['active']
        baseline_setups = result['baseline']

        # Display panels
        col1, col2 = st.columns([1, 2])

        with col1:
            render_market_state_panel(market_state)
            render_position_sizing_guide()

        with col2:
            render_active_edges_panel(active_setups, baseline_setups, current_price)

        # Show metrics
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Active Edges", len(active_setups))
        with col2:
            st.metric("Baseline Edges", len(baseline_setups))
        with col3:
            best_active = max([s['avg_r'] for s in active_setups], default=0)
            st.metric("Best Active Edge", f"+{best_active:.3f}R" if best_active > 0 else "N/A")
        with col4:
            total_quality = sum([s.get('quality_multiplier', 1.0) for s in active_setups[:3]])
            avg_quality = total_quality / min(3, len(active_setups)) if active_setups else 1.0
            st.metric("Avg Quality (Top 3)", f"{avg_quality:.1f}x")

    except Exception as e:
        st.error(f"Error loading conditional edges: {e}")
        st.caption("Falling back to baseline setups only")


def render_conditional_edges_compact(
    instrument: str,
    current_price: float
) -> None:
    """
    Compact conditional edges display for sidebar or inline use.

    Args:
        instrument: Instrument symbol
        current_price: Current market price
    """
    detector = SetupDetector()

    try:
        result = detector.get_active_and_potential_setups(
            instrument=instrument,
            current_price=current_price
        )

        market_state = result['market_state']
        active_setups = result['active']

        # Show market state badge
        bias = market_state.get('asia_bias', 'UNKNOWN')

        if bias == 'ABOVE':
            st.success(f"✅ ABOVE Asia ({len(active_setups)} edges active)")
        elif bias == 'BELOW':
            st.error(f"✅ BELOW Asia ({len(active_setups)} edges active)")
        elif bias == 'INSIDE':
            st.info(f"⏸️ INSIDE Asia (baseline only)")
        else:
            st.warning("⚠️ No Asia data")

        # Show best active edge
        if active_setups and len(active_setups) > 0:
            best = active_setups[0]
            st.caption(f"Best: {best['orb_time']} RR={best['rr']} ({best['avg_r']:.3f}R, {best['quality_multiplier']}x)")

    except Exception as e:
        st.caption(f"Conditional edges unavailable: {str(e)[:50]}")


if __name__ == "__main__":
    """Test the display"""
    st.set_page_config(page_title="Conditional Edges Test", layout="wide")

    st.title("Conditional Edge System Test")

    # Get test inputs
    instrument = st.selectbox("Instrument", ["MGC", "NQ", "MPL"])
    current_price = st.number_input("Current Price", value=4480.0, step=0.1)

    # Show full display
    render_conditional_edges_full(instrument, current_price)
