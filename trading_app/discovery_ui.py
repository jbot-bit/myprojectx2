"""
Strategy Discovery UI - Create and test new edge candidates

Provides UI for:
1. Running backtests on new ORB configurations
2. Creating edge candidates from backtest results
3. Quick hypothesis testing
"""

import streamlit as st
import json
from datetime import date
from typing import Optional
import logging

from strategy_discovery import StrategyDiscovery, DiscoveryConfig
from cloud_mode import get_database_connection

logger = logging.getLogger(__name__)


def create_edge_candidate_from_backtest(
    instrument: str,
    orb_time: str,
    rr: float,
    sl_mode: str,
    orb_size_filter: Optional[float],
    backtest_result: dict,
    hypothesis: str,
    test_window_start: str,
    test_window_end: str
) -> int:
    """
    Create edge candidate from backtest results.

    Returns:
        candidate_id of created candidate
    """
    try:
        conn = get_database_connection(read_only=False)

        # Build metrics JSON
        metrics = {
            "orb_time": orb_time,
            "rr": rr,
            "win_rate": backtest_result["win_rate"],
            "avg_r": backtest_result["avg_r"],
            "annual_trades": backtest_result["annual_trades"],
            "tier": backtest_result["tier"],
            "total_r": backtest_result.get("total_r", 0),
            "trades": backtest_result["total_trades"]
        }

        # Build filter spec JSON
        filter_spec = {
            "orb_size_filter": orb_size_filter,
            "sl_mode": sl_mode,
            "close_confirmations": 1,  # Standard for ORB
            "buffer_ticks": 0.0
        }

        # Build test config JSON
        test_config = {
            "test_window_start": test_window_start,
            "test_window_end": test_window_end,
            "scan_window_hours": 24  # Standard for extended scan
        }

        # Slippage assumptions
        slippage = {
            "entry_slippage_ticks": 1,
            "exit_slippage_ticks": 1,
            "assumptions": "Standard 1-tick slippage both ways"
        }

        # Generate name
        name = f"{instrument} {orb_time} ORB RR={rr} {sl_mode}"
        if orb_size_filter:
            name += f" Filter={orb_size_filter*100:.1f}%"

        # Insert into edge_candidates
        result = conn.execute("""
            INSERT INTO edge_candidates (
                instrument,
                name,
                hypothesis_text,
                status,
                test_window_start,
                test_window_end,
                metrics_json,
                filter_spec_json,
                test_config_json,
                slippage_assumptions_json,
                code_version,
                data_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING candidate_id
        """, [
            instrument,
            name,
            hypothesis,
            "DRAFT",  # Start as DRAFT
            test_window_start,
            test_window_end,
            json.dumps(metrics),
            json.dumps(filter_spec),
            json.dumps(test_config),
            json.dumps(slippage),
            "v1.0.0",  # Code version
            f"{test_window_start}_to_{test_window_end}"  # Data version
        ]).fetchone()

        conn.commit()
        conn.close()

        candidate_id = result[0]
        logger.info(f"Created edge candidate {candidate_id}: {name}")
        return candidate_id

    except Exception as e:
        logger.error(f"Error creating edge candidate: {e}")
        raise


def render_discovery_panel():
    """
    Render the Strategy Discovery panel.

    Allows user to:
    1. Configure backtest parameters
    2. Run backtest
    3. Create edge candidate if profitable
    """
    st.header("🔬 Strategy Discovery")
    st.caption("Backtest new ORB configurations and create edge candidates")

    # Initialize discovery engine
    if 'discovery_engine' not in st.session_state:
        st.session_state.discovery_engine = StrategyDiscovery()

    st.divider()

    # Configuration form
    st.subheader("📋 Backtest Configuration")

    col1, col2, col3 = st.columns(3)

    with col1:
        instrument = st.selectbox(
            "Instrument",
            ["MGC", "NQ", "MPL"],
            index=0,
            key="discovery_instrument"
        )

    with col2:
        orb_time = st.selectbox(
            "ORB Time",
            ["0900", "1000", "1100", "1800", "2300", "0030"],
            index=4,  # Default to 2300
            key="discovery_orb_time"
        )

    with col3:
        rr = st.selectbox(
            "Risk:Reward",
            [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0],
            index=1,  # Default to 1.5
            key="discovery_rr"
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        sl_mode = st.selectbox(
            "Stop Loss Mode",
            ["FULL", "HALF"],
            index=1,  # Default to HALF
            key="discovery_sl_mode"
        )

    with col2:
        use_filter = st.checkbox(
            "Use ORB Size Filter",
            value=True,
            key="discovery_use_filter"
        )

    with col3:
        if use_filter:
            orb_size_filter = st.number_input(
                "Filter (% ATR)",
                min_value=0.05,
                max_value=0.50,
                value=0.155,
                step=0.005,
                format="%.3f",
                key="discovery_filter_value",
                help="ORB must be smaller than this % of ATR"
            )
        else:
            orb_size_filter = None

    # Test window
    st.divider()
    st.subheader("📅 Test Window")

    col1, col2 = st.columns(2)

    with col1:
        test_start = st.date_input(
            "Start Date",
            value=date(2024, 1, 1),
            key="discovery_test_start"
        )

    with col2:
        test_end = st.date_input(
            "End Date",
            value=date(2026, 1, 10),
            key="discovery_test_end"
        )

    # Hypothesis
    hypothesis = st.text_area(
        "Hypothesis (optional)",
        placeholder="Describe why you think this configuration will be profitable...",
        key="discovery_hypothesis"
    )

    st.divider()

    # Run backtest button
    if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Running backtest..."):
            try:
                # Create config
                config = DiscoveryConfig(
                    instrument=instrument,
                    orb_time=orb_time,
                    rr=rr,
                    sl_mode=sl_mode,
                    orb_size_filter=orb_size_filter
                )

                # Run backtest
                result = st.session_state.discovery_engine.backtest_config(config)

                if result is None:
                    st.error("❌ Backtest failed - no data found for this configuration")
                else:
                    # Store result in session state
                    st.session_state.backtest_result = result
                    st.session_state.backtest_config = {
                        "instrument": instrument,
                        "orb_time": orb_time,
                        "rr": rr,
                        "sl_mode": sl_mode,
                        "orb_size_filter": orb_size_filter,
                        "test_start": str(test_start),
                        "test_end": str(test_end),
                        "hypothesis": hypothesis or f"Testing {instrument} {orb_time} ORB RR={rr} {sl_mode}"
                    }

                    st.rerun()

            except Exception as e:
                st.error(f"❌ Backtest error: {e}")
                logger.error(f"Backtest error: {e}", exc_info=True)

    # Display backtest results
    if 'backtest_result' in st.session_state:
        st.divider()
        st.subheader("📊 Backtest Results")

        result = st.session_state.backtest_result

        # Key metrics in columns
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Trades", result.total_trades)
        with col2:
            st.metric("Win Rate", f"{result.win_rate:.1f}%")
        with col3:
            st.metric("Avg R", f"{result.avg_r:+.3f}R")
        with col4:
            st.metric("Annual Trades", result.annual_trades)

        col1, col2 = st.columns(2)

        with col1:
            st.metric("Tier", result.tier)
        with col2:
            st.metric("Total R", f"{result.total_r:+.1f}R")

        # Display config
        with st.expander("⚙️ Configuration"):
            st.json(st.session_state.backtest_config)

        # Create candidate button
        st.divider()

        is_profitable = result.avg_r > 0 and result.total_trades >= 10

        if is_profitable:
            st.success("✅ This configuration is PROFITABLE! Create edge candidate?")

            if st.button("🎯 Create Edge Candidate", type="primary", use_container_width=True):
                try:
                    config = st.session_state.backtest_config

                    candidate_id = create_edge_candidate_from_backtest(
                        instrument=config["instrument"],
                        orb_time=config["orb_time"],
                        rr=config["rr"],
                        sl_mode=config["sl_mode"],
                        orb_size_filter=config["orb_size_filter"],
                        backtest_result={
                            "win_rate": result.win_rate,
                            "avg_r": result.avg_r,
                            "annual_trades": result.annual_trades,
                            "tier": result.tier,
                            "total_r": result.total_r,
                            "total_trades": result.total_trades
                        },
                        hypothesis=config["hypothesis"],
                        test_window_start=config["test_start"],
                        test_window_end=config["test_end"]
                    )

                    st.success(f"✅ Created edge candidate #{candidate_id}")
                    st.info("Go to 'Edge Candidates' panel below to review and approve")

                    # Clear backtest result
                    del st.session_state.backtest_result
                    del st.session_state.backtest_config
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error creating candidate: {e}")
                    logger.error(f"Error creating candidate: {e}", exc_info=True)
        else:
            st.warning("⚠️ This configuration is NOT profitable (avg R ≤ 0 or < 10 trades)")
            st.info("Try different parameters or filter thresholds")
