"""
LIVE TRADING HUB - Streamlit Application
Real-time decision support engine for trading.
"""

import sys
from pathlib import Path

# Add trading_app directory and repo root to Python path
if __name__ == "__main__" or "streamlit" in sys.modules:
    current_dir = Path(__file__).parent
    repo_root = current_dir.parent
    # Add both paths for proper imports
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import logging
import uuid
import os
from streamlit_autorefresh import st_autorefresh

from config import *
from data_loader import LiveDataLoader
from strategy_engine import StrategyEngine, ActionType, StrategyState
from utils import calculate_position_size, format_price, log_to_journal
from ai_memory import AIMemoryManager
from ai_assistant import TradingAIAssistant
from cloud_mode import is_cloud_deployment, show_cloud_setup_instructions
from setup_scanner import SetupScanner, render_setup_scanner_tab
from enhanced_charting import EnhancedChart, ORBOverlay, TradeMarker, ChartTimeframe, resample_bars
from live_chart_builder import build_live_trading_chart, calculate_trade_levels
from data_quality_monitor import DataQualityMonitor, render_data_quality_panel
from market_hours_monitor import MarketHoursMonitor, render_market_hours_indicator
from risk_manager import RiskManager, RiskLimits, render_risk_dashboard
from position_tracker import PositionTracker, render_position_panel, render_empty_position_panel
from strategy_discovery import StrategyDiscovery, DiscoveryConfig, add_setup_to_production, generate_config_snippet
from market_intelligence import MarketIntelligence
from render_intelligence import render_intelligence_panel
from professional_ui import (
    inject_professional_css,
    render_pro_metric,
    render_status_badge,
    render_intelligence_card,
    render_countdown_timer,
    render_price_display
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CANONICAL ENVIRONMENT CHECK (STARTUP GATE)
# ============================================================================
try:
    from trading_app.canonical import assert_canonical_environment
    assert_canonical_environment()
except Exception as e:
    # Import Streamlit error handling
    import streamlit as st
    st.error(f"""
    **CANONICAL ENVIRONMENT ERROR**

    The application failed to start due to environment validation errors:

    ```
    {str(e)}
    ```

    **How to Fix:**
    1. Ensure CANONICAL.json exists in repository root
    2. Remove any shadow database files (check trading_app/ directory)
    3. Verify data/db/gold.db exists or set CLOUD_MODE=1
    4. Run: `python tools/preflight.py` for detailed diagnostics

    **Contact:** Check README.md for setup instructions
    """)
    st.stop()

# ============================================================================
# DATABASE BOOTSTRAP (Ensure required tables exist)
# ============================================================================
try:
    from db_bootstrap import bootstrap_database
    bootstrap_success = bootstrap_database()
    if not bootstrap_success:
        logger.warning("Database bootstrap completed with warnings (some tables may be missing)")
except Exception as e:
    logger.error(f"Database bootstrap error: {e}")
    # Don't stop app - continue with best effort

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="Trading Hub",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject professional CSS
inject_professional_css()

# Add responsive mobile CSS
st.markdown("""
<style>
    /* Mobile responsiveness improvements */
    @media (max-width: 768px) {
        h1 { font-size: 32px !important; }
        h2 { font-size: 24px !important; }
        h3 { font-size: 20px !important; }

        /* Stack metrics vertically on mobile */
        .stMetric { margin-bottom: 16px; }

        /* Ensure text is readable */
        body { font-size: 16px; }

        /* Touch-friendly spacing */
        .stButton button {
            min-height: 48px;
            font-size: 16px;
        }
    }

    /* Better spacing throughout */
    .stMarkdown { line-height: 1.6; }

    /* Ensure charts are responsive */
    .js-plotly-plot { width: 100% !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
if "data_loader" not in st.session_state:
    st.session_state.data_loader = None
if "strategy_engine" not in st.session_state:
    st.session_state.strategy_engine = None
if "last_evaluation" not in st.session_state:
    st.session_state.last_evaluation = None
if "account_size" not in st.session_state:
    st.session_state.account_size = DEFAULT_ACCOUNT_SIZE
if "current_symbol" not in st.session_state:
    st.session_state.current_symbol = PRIMARY_INSTRUMENT
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "memory_manager" not in st.session_state:
    st.session_state.memory_manager = AIMemoryManager()  # Uses canonical DB routing
if "ai_assistant" not in st.session_state:
    st.session_state.ai_assistant = TradingAIAssistant(st.session_state.memory_manager)
if "chat_history" not in st.session_state:
    # Load persistent history from database
    try:
        loaded_history = st.session_state.memory_manager.load_session_history(
            session_id=st.session_state.session_id,
            limit=50  # Last 50 messages
        )
        # Convert to chat format
        st.session_state.chat_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in loaded_history
        ]
        if loaded_history:
            logger.info(f"Loaded {len(loaded_history)} messages from persistent memory")
    except Exception as e:
        logger.warning(f"Could not load chat history: {e}")
        st.session_state.chat_history = []
if "setup_scanner" not in st.session_state:
    # Use cloud-aware path
    from cloud_mode import get_database_path
    db_path = get_database_path()
    st.session_state.setup_scanner = SetupScanner(db_path)
if "chart_timeframe" not in st.session_state:
    st.session_state.chart_timeframe = ChartTimeframe.M1
if "indicators_enabled" not in st.session_state:
    st.session_state.indicators_enabled = {
        "ema_9": False,
        "ema_20": False,
        "vwap": True,
        "rsi": False,
        "orb_overlays": True,
    }
if "data_quality_monitor" not in st.session_state:
    st.session_state.data_quality_monitor = DataQualityMonitor()
if "market_hours_monitor" not in st.session_state:
    st.session_state.market_hours_monitor = MarketHoursMonitor()
if "risk_manager" not in st.session_state:
    # Initialize with default limits
    limits = RiskLimits(
        daily_loss_dollars=1000.0,  # $1000 max daily loss
        daily_loss_r=10.0,          # 10R max daily loss
        weekly_loss_dollars=3000.0,  # $3000 max weekly loss
        weekly_loss_r=30.0,          # 30R max weekly loss
        max_concurrent_positions=3,
        max_position_size_pct=2.0
    )
    st.session_state.risk_manager = RiskManager(DEFAULT_ACCOUNT_SIZE, limits)
if "position_tracker" not in st.session_state:
    st.session_state.position_tracker = PositionTracker()
if "strategy_discovery" not in st.session_state:
    # Use cloud-aware path (None = auto-detect)
    st.session_state.strategy_discovery = StrategyDiscovery(None)
if "market_intelligence" not in st.session_state:
    st.session_state.market_intelligence = MarketIntelligence(TZ_LOCAL)

# ============================================================================
# SIDEBAR - SETTINGS
# ============================================================================
with st.sidebar:
    st.title("⚙️ Settings")

    # Instrument selection
    symbol = st.selectbox(
        "Instrument",
        [PRIMARY_INSTRUMENT, SECONDARY_INSTRUMENT],
        index=0
    )

    if symbol != st.session_state.current_symbol:
        st.session_state.current_symbol = symbol
        st.session_state.data_loader = None  # Force reload

    # Account size
    account_size = st.number_input(
        "Account Size ($)",
        min_value=1000.0,
        max_value=10000000.0,
        value=st.session_state.account_size,
        step=1000.0
    )
    st.session_state.account_size = account_size

    st.divider()

    # Data status
    st.subheader("📊 Data Status")

    if st.button("Initialize/Refresh Data"):
        with st.spinner("Loading data..."):
            try:
                # Initialize data loader
                loader = LiveDataLoader(symbol)

                # Fetch data (cloud-aware)
                if is_cloud_deployment():
                    # In cloud: fetch live data from ProjectX API
                    if os.getenv("PROJECTX_API_KEY"):
                        loader.refresh()  # Fetches from ProjectX API automatically
                        st.success("Fetched live data from ProjectX API")
                    else:
                        st.error("No PROJECTX_API_KEY found. Add it in Streamlit Cloud secrets.")
                        st.stop()
                else:
                    # Local: check if we need to backfill
                    latest_bar = loader.get_latest_bar()
                    needs_backfill = True

                    if latest_bar:
                        # Check if we have recent data (within last 6 hours)
                        latest_time = latest_bar['ts_utc']
                        time_since_last = datetime.now(TZ_UTC) - latest_time
                        if time_since_last.total_seconds() < 6 * 3600:  # 6 hours
                            needs_backfill = False
                            st.info("📊 Loading from cache (data < 6 hours old)")

                    if needs_backfill:
                        # Backfill from database then refresh
                        from cloud_mode import get_database_path
                        db_path = get_database_path()
                        st.info("🔄 Loading fresh data from database...")
                        loader.backfill_from_gold_db(db_path, days=2)

                    loader.refresh()

                st.session_state.data_loader = loader

                # Initialize ML engine if enabled
                ml_engine = None
                if ML_ENABLED:
                    try:
                        import sys
                        from pathlib import Path
                        sys.path.insert(0, str(Path(__file__).parent.parent))
                        from ml_inference.inference_engine import MLInferenceEngine

                        ml_engine = MLInferenceEngine()
                        logger.info("ML engine initialized successfully")
                    except ImportError:
                        logger.error("ML enabled but ml_inference module not found. Install ML dependencies or disable with ENABLE_ML=0")
                        st.error("⚠️ ML enabled but not installed. Set ENABLE_ML=0 or install ML dependencies.")
                    except Exception as e:
                        logger.error(f"ML engine initialization failed: {e}")
                        st.error(f"⚠️ ML initialization failed: {e}")
                else:
                    logger.info("ML disabled (ENABLE_ML not set)")

                st.session_state.strategy_engine = StrategyEngine(loader, ml_engine=ml_engine)

                # Update data quality monitor with latest bar
                latest_bar = loader.get_latest_bar()
                if latest_bar:
                    st.session_state.data_quality_monitor.update_bar(
                        symbol,
                        latest_bar['ts_local'],
                        {
                            'open': latest_bar['open'],
                            'high': latest_bar['high'],
                            'low': latest_bar['low'],
                            'close': latest_bar['close'],
                            'volume': latest_bar.get('volume', 0)
                        }
                    )

                st.success(f"Loaded data for {symbol}")
                logger.info(f"Data initialized for {symbol}")

            except Exception as e:
                st.error(f"Error loading data: {e}")
                logger.error(f"Data load error: {e}", exc_info=True)

    if st.session_state.data_loader:
        latest_bar = st.session_state.data_loader.get_latest_bar()
        if latest_bar:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(render_pro_metric("Last Bar", latest_bar["ts_local"].strftime("%H:%M")), unsafe_allow_html=True)
            with col2:
                st.markdown(render_pro_metric("Price", f"${latest_bar['close']:.2f}"), unsafe_allow_html=True)

    st.divider()

    # Instrument config display
    if st.session_state.strategy_engine:
        st.subheader(f"⚙️ {symbol} Config")
        engine = st.session_state.strategy_engine

        # Show instrument-specific settings
        st.caption(f"**CASCADE Gap:** {engine.cascade_min_gap:.1f}pts")

        # Show ORB configs
        with st.expander("📋 ORB Configurations", expanded=False):
            orb_data = []
            for orb_name, config in engine.orb_configs.items():
                if config.get("tier") == "SKIP":
                    orb_data.append({
                        "ORB": orb_name,
                        "Status": "⏭️ SKIP",
                        "RR": "-",
                        "SL": "-"
                    })
                else:
                    orb_data.append({
                        "ORB": orb_name,
                        "Status": "✅ Active",
                        "RR": f"{config['rr']}R",
                        "SL": config["sl_mode"]
                    })

            st.dataframe(
                pd.DataFrame(orb_data),
                use_container_width=True,
                hide_index=True
            )

        # Show active filters
        with st.expander("🔍 ORB Size Filters", expanded=False):
            filter_data = []
            for orb_name, threshold in engine.orb_size_filters.items():
                if threshold is None:
                    filter_data.append({"ORB": orb_name, "Filter": "None"})
                else:
                    filter_data.append({"ORB": orb_name, "Filter": f"< {threshold*100:.1f}% ATR"})

            st.dataframe(
                pd.DataFrame(filter_data),
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    # Cache controls for performance
    from cache_layer import render_cache_controls
    render_cache_controls()

    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    if auto_refresh:
        st.info(f"Refreshing every {DATA_REFRESH_SECONDS}s")

    # Safety features removed per user request

# ============================================================================
# SINGLE PAGE - NO TABS (User requested streamlined view)
# ============================================================================

# ========================================================================
# AUTO-REFRESH SETUP (Makes app truly "LIVE")
# ========================================================================
# Determine if it's market hours
now = datetime.now(TZ_LOCAL)
is_market_hours = 9 <= now.hour < 17

# Initialize auto-refresh state
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = is_market_hours

# Auto-refresh controls in a compact expander (don't take up space)
with st.expander("⚡ Live Update Settings", expanded=False):
    col1, col2 = st.columns([1, 1])

    with col1:
        auto_refresh = st.checkbox(
            "Auto-Refresh",
            value=st.session_state.auto_refresh_enabled,
            help="Automatically refresh data every few seconds"
        )
        st.session_state.auto_refresh_enabled = auto_refresh

    with col2:
        if auto_refresh:
            # Faster during market hours, slower outside
            default_interval = 10 if is_market_hours else 30

            refresh_interval = st.slider(
                "Interval (seconds)",
                min_value=5,
                max_value=60,
                value=default_interval,
                step=5,
                help="How often to refresh data"
            )

    # Show status
    if auto_refresh:
        st.success(f"🔄 Auto-refreshing every {refresh_interval}s")
    else:
        st.info("⏸️ Auto-refresh disabled - click 'Refresh Now' in sidebar")

# Trigger the auto-refresh
if st.session_state.auto_refresh_enabled:
    count = st_autorefresh(interval=refresh_interval * 1000, key="live_refresh")
    # Show subtle refresh indicator in corner
    st.caption(f"🔄 Updates: {count} | Last: {now.strftime('%H:%M:%S')}")

# Professional header with session badge
symbol = st.session_state.current_symbol
now_time = datetime.now(TZ_LOCAL).strftime("%H:%M:%S")
now_hour = datetime.now(TZ_LOCAL).hour
session_name = "ASIA" if 9 <= now_hour < 18 else "LONDON" if 18 <= now_hour < 23 else "NY"

# Session color coding for quick visual recognition
session_colors = {"ASIA": "#4CAF50", "LONDON": "#2196F3", "NY": "#FF9800"}
session_color = session_colors.get(session_name, "#9E9E9E")

st.markdown(f"""
<div style="text-align: center; padding: 24px 0; margin-bottom: 20px; border-bottom: 4px solid {session_color};">
    <h1 style="margin: 0; font-size: 48px; font-weight: 700; color: #1a1a1a;">🔴 LIVE {symbol}</h1>
    <div style="margin-top: 16px; display: flex; justify-content: center; align-items: center; gap: 20px;">
        <span style="background: {session_color}; color: white; padding: 8px 20px; border-radius: 24px; font-weight: 600; font-size: 16px;">
            {session_name} SESSION
        </span>
        <span style="color: #666; font-size: 18px; font-weight: 500;">{now_time}</span>
    </div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.data_loader or not st.session_state.strategy_engine:
    # AUTO-INITIALIZE DATA (so user doesn't need to click button)
    st.info("🔄 Loading data... Please wait.")

    try:
        # Initialize data loader
        loader = LiveDataLoader(symbol)

        # Fetch data (cloud-aware)
        if is_cloud_deployment():
            # In cloud: fetch live data from ProjectX API
            if os.getenv("PROJECTX_API_KEY"):
                loader.refresh()  # Fetches from ProjectX API automatically
            else:
                st.error("No PROJECTX_API_KEY found. Add it in Streamlit Cloud secrets.")
                st.stop()
        else:
            # Local: check if we need to backfill
            latest_bar = loader.get_latest_bar()
            needs_backfill = True

            if latest_bar:
                # Check if we have recent data (within last 6 hours)
                latest_time = latest_bar['ts_utc']
                time_since_last = datetime.now(TZ_UTC) - latest_time
                if time_since_last.total_seconds() < 6 * 3600:  # 6 hours
                    needs_backfill = False

            if needs_backfill:
                # Backfill from database then refresh
                from cloud_mode import get_database_path
                db_path = get_database_path()
                loader.backfill_from_gold_db(db_path, days=2)

            loader.refresh()

        st.session_state.data_loader = loader

        # Initialize ML engine if enabled
        ml_engine = None
        if ML_ENABLED:
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from ml_inference.inference_engine import MLInferenceEngine

                ml_engine = MLInferenceEngine()
                logger.info("ML engine initialized successfully")
            except ImportError:
                logger.error("ML enabled but ml_inference module not found. Install ML dependencies or disable with ENABLE_ML=0")
            except Exception as e:
                logger.error(f"ML engine initialization failed: {e}")
        else:
            logger.info("ML disabled (ENABLE_ML not set)")

        st.session_state.strategy_engine = StrategyEngine(loader, ml_engine=ml_engine)

        # Update data quality monitor with latest bar
        latest_bar = loader.get_latest_bar()
        if latest_bar:
            st.session_state.data_quality_monitor.update_bar(
                symbol,
                latest_bar['ts_local'],
                {
                    'open': latest_bar['open'],
                    'high': latest_bar['high'],
                    'low': latest_bar['low'],
                    'close': latest_bar['close'],
                    'volume': latest_bar.get('volume', 0)
                }
            )

        st.success(f"✅ Data loaded for {symbol}")
        st.rerun()  # Reload page to show all content

    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        logger.error(f"Data load error: {e}", exc_info=True)
        # Don't stop - allow AI chat to still work
        pass

# ========================================================================
# CLEAN MARKET SNAPSHOT (TOP OF PAGE)
# ========================================================================

# Get current price and ATR
# CRITICAL: Refresh data BEFORE getting latest bar to ensure fresh price
st.session_state.data_loader.refresh()
latest_bar = st.session_state.data_loader.get_latest_bar()
current_price = latest_bar['close'] if latest_bar else 0
current_atr = st.session_state.data_loader.get_today_atr() or 40.0

# CRITICAL: Hard freshness gate - refuse stale data
data_is_stale = False
if latest_bar:
    latest_bar_ts = latest_bar['ts_utc']
    now_utc = datetime.now(TZ_UTC)
    freshness_seconds = (now_utc - latest_bar_ts).total_seconds()

    if freshness_seconds > 90:
        data_is_stale = True
        st.error(f"DATA STALE - REFRESHING (last bar: {int(freshness_seconds)}s ago)")
        st.warning("Trade recommendations blocked due to stale data. Please wait for refresh.")

if current_price > 0 and not data_is_stale:
    # MGC tick size: 0.10 points = 1 tick
    TICK_SIZE = 0.10

    # Compact price/ATR display with TICKS
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("MGC Price", f"${current_price:.2f}")
    with col2:
        atr_ticks = int(current_atr / TICK_SIZE)
        st.metric("ATR (20)", f"{atr_ticks} ticks", help=f"{current_atr:.2f} pts")
    with col3:
        filter_2300 = 0.155 * current_atr
        filter_2300_ticks = int(filter_2300 / TICK_SIZE)
        st.metric("2300 Filter", f"<{filter_2300_ticks} ticks", help=f"ORB < {filter_2300:.2f} pts (15.5% ATR)")
    with col4:
        filter_0030 = 0.112 * current_atr
        filter_0030_ticks = int(filter_0030 / TICK_SIZE)
        st.metric("0030 Filter", f"<{filter_0030_ticks} ticks", help=f"ORB < {filter_0030:.2f} pts (11.2% ATR)")

st.divider()

# ========================================================================
# STRATEGY EVALUATION (Must run FIRST to get trading decision)
# ========================================================================
try:
    evaluation = st.session_state.strategy_engine.evaluate_all()
    st.session_state.last_evaluation = evaluation

    # Log state change
    log_to_journal(evaluation)

except Exception as e:
    st.error(f"Strategy evaluation error: {e}")
    logger.error(f"Evaluation error: {e}", exc_info=True)
    # Don't stop - allow rest of app (including AI chat) to render
    evaluation = None

# ========================================================================
# 🚦 DECISION PANEL - WHAT TO DO NOW (MOST IMPORTANT - ALWAYS VISIBLE)
# ========================================================================

# Only show decision panel if evaluation succeeded
if evaluation:
    st.markdown('<div style="background: linear-gradient(to bottom, #ffffff, #f8f9fa); padding: 24px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin: 20px 0;">', unsafe_allow_html=True)

    # Color-code by action
    action_styles = {
        ActionType.STAND_DOWN: {"color": "#6c757d", "bg": "#f8f9fa", "emoji": "⏸️"},
        ActionType.PREPARE: {"color": "#0d6efd", "bg": "#cfe2ff", "emoji": "⚡"},
        ActionType.ENTER: {"color": "#198754", "bg": "#d1e7dd", "emoji": "🎯"},
        ActionType.MANAGE: {"color": "#fd7e14", "bg": "#ffe5d0", "emoji": "📊"},
        ActionType.EXIT: {"color": "#dc3545", "bg": "#f8d7da", "emoji": "🚪"},
    }

    style = action_styles.get(evaluation.action, action_styles[ActionType.STAND_DOWN])

# Large prominent status banner
st.markdown(f"""
<div style="
    background: linear-gradient(135deg, {style['bg']} 0%, {style['bg']}dd 100%);
    border-left: 8px solid {style['color']};
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
">
    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 16px;">
        <span style="font-size: 48px;">{style['emoji']}</span>
        <div>
            <div style="font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px;">Status</div>
            <div style="font-size: 32px; font-weight: bold; color: {style['color']};">{evaluation.action.value}</div>
        </div>
    </div>
    <div style="font-size: 18px; color: #333; margin-bottom: 8px;">
        <strong>Strategy:</strong> {evaluation.strategy_name}
    </div>
</div>
""", unsafe_allow_html=True)

# Reasons and action in clean cards
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 💡 WHY")
    reasons_html = ""
    for reason in evaluation.reasons[:3]:
        reasons_html += f'<div style="padding: 8px 0; border-left: 3px solid {style["color"]}; padding-left: 12px; margin: 4px 0;">• {reason}</div>'
    st.markdown(f'<div style="font-size: 16px;">{reasons_html}</div>', unsafe_allow_html=True)

with col2:
    st.markdown("### 🎯 NEXT ACTION")
    st.markdown(f"""
    <div style="
        background: {style['color']}22;
        border: 2px solid {style['color']};
        border-radius: 8px;
        padding: 16px;
        font-size: 18px;
        font-weight: bold;
        color: {style['color']};
        text-align: center;
    ">
        {evaluation.next_instruction}
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # Close decision panel container

st.divider()

# ========================================================================
# NEXT ORB COUNTDOWN & SETUP DISPLAY (Collapsible)
# ========================================================================
with st.expander("⏱️ Next ORB Countdown & Setup Details", expanded=False):
    now = datetime.now(TZ_LOCAL)

    # Define ORB times (24-hour format)
    orb_times = {
            "0900": (9, 0, 5),   # 09:00-09:05
            "1000": (10, 0, 5),  # 10:00-10:05
            "1100": (11, 0, 5),  # 11:00-11:05
            "1800": (18, 0, 5),  # 18:00-18:05
            "2300": (23, 0, 5),  # 23:00-23:05
            "0030": (0, 30, 35), # 00:30-00:35
        }

    # Find next ORB
    next_orb_name = None
    next_orb_start = None
    next_orb_end = None
    min_delta = timedelta(days=1)

    for orb_name, (hour, minute, end_minute) in orb_times.items():
        orb_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        orb_end = now.replace(hour=hour, minute=end_minute, second=0, microsecond=0)

        # Handle midnight crossing (0030)
        if hour == 0 and now.hour >= 12:
            orb_start += timedelta(days=1)
            orb_end += timedelta(days=1)

        # If we're past this ORB today, check tomorrow
        if now > orb_end:
            orb_start += timedelta(days=1)
            orb_end += timedelta(days=1)

        delta = orb_start - now
        if delta < min_delta and delta > timedelta(0):
            min_delta = delta
            next_orb_name = orb_name
            next_orb_start = orb_start
            next_orb_end = orb_end

    # Check if we're IN an ORB window right now
    in_orb_window = False
    current_orb_name = None
    current_orb_end = None

    for orb_name, (hour, minute, end_minute) in orb_times.items():
        orb_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        orb_end = now.replace(hour=hour, minute=end_minute, second=0, microsecond=0)

        # Handle midnight crossing
        if hour == 0 and now.hour >= 12:
            orb_start += timedelta(days=1)
            orb_end += timedelta(days=1)

        if orb_start <= now <= orb_end:
            in_orb_window = True
            current_orb_name = orb_name
            current_orb_end = orb_end
            break

    # Display countdown or active ORB
    if in_orb_window:
        # ORB WINDOW IS ACTIVE RIGHT NOW
        time_remaining = (current_orb_end - now).total_seconds()
        minutes = int(time_remaining // 60)
        seconds = int(time_remaining % 60)

        # Get current ORB high/low from live data
        orb_start_time = now.replace(hour=orb_times[current_orb_name][0], minute=orb_times[current_orb_name][1], second=0, microsecond=0)

        if st.session_state.data_loader:
            orb_bars = st.session_state.data_loader.get_bars_in_range(orb_start_time, now)
            if not orb_bars.empty:
                orb_high = orb_bars['high'].max()
                orb_low = orb_bars['low'].min()
                orb_size = orb_high - orb_low
            else:
                orb_high = orb_low = orb_size = None
        else:
            orb_high = orb_low = orb_size = None

        # Get filter threshold
        engine = st.session_state.strategy_engine
        if engine:
            filter_threshold = engine.orb_size_filters.get(current_orb_name)
            atr = st.session_state.data_loader.get_today_atr() if st.session_state.data_loader else None
        else:
            filter_threshold = None
            atr = None

        if filter_threshold and atr and orb_size:
            filter_passed = orb_size < (atr * filter_threshold)
            filter_text = f"< {filter_threshold*100:.1f}% ATR (~{atr * filter_threshold:.1f}pts)"
        else:
            filter_passed = True
            filter_text = "None"

        # Active ORB window banner
        st.markdown(render_intelligence_card(
            f"🚨 {current_orb_name} ORB ACTIVE",
            "Window forming now - Note high and low",
            "critical"
        ), unsafe_allow_html=True)

        # Countdown timer
        st.markdown(render_countdown_timer(
            f"{minutes:02d}:{seconds:02d}",
            "Until Window Closes"
        ), unsafe_allow_html=True)

        # ORB metrics in professional cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(render_pro_metric(
                "ORB HIGH",
                f"${orb_high:.2f}" if orb_high else "$0.00",
                "↑" if orb_high else None,
                True
            ), unsafe_allow_html=True)
        with col2:
            st.markdown(render_pro_metric(
                "ORB LOW",
                f"${orb_low:.2f}" if orb_low else "$0.00",
                "↓" if orb_low else None,
                False
            ), unsafe_allow_html=True)
        with col3:
            st.markdown(render_pro_metric(
                "ORB SIZE",
                f"{orb_size:.2f}pts" if orb_size else "0.00pts"
            ), unsafe_allow_html=True)

        # Filter status
        if filter_passed:
            st.success(f"✅ **FILTER PASSED** - {filter_text}")
        else:
            st.error(f"❌ **FILTER FAILED** - {filter_text}")

        st.info(f"⏳ **WAIT FOR BREAKOUT** - Enter on first 1-min close OUTSIDE range at {current_orb_end.strftime('%H:%M:%S')}")

    elif next_orb_name and next_orb_start:
        # COUNTDOWN TO NEXT ORB
        time_until = (next_orb_start - now).total_seconds()
        hours = int(time_until // 3600)
        minutes = int((time_until % 3600) // 60)
        seconds = int(time_until % 60)

        # Get config for this ORB (only if engine is initialized)
        engine = st.session_state.strategy_engine
        if engine:
            orb_config = engine.orb_configs.get(next_orb_name, {})
            filter_threshold = engine.orb_size_filters.get(next_orb_name)
            atr = st.session_state.data_loader.get_today_atr()
        else:
            orb_config = {}
            filter_threshold = None
            atr = None

        # Check if SKIP
        is_skip = orb_config.get("tier") == "SKIP"

        if is_skip:
            st.markdown(render_intelligence_card(
                f"⏭️ SKIP {next_orb_name}",
                f"Setup skipped - Next active in {hours}h {minutes}m",
                "low"
            ), unsafe_allow_html=True)
        else:
            st.markdown(render_intelligence_card(
                f"⏰ NEXT: {next_orb_name} ORB",
                f"Window {next_orb_start.strftime('%H:%M')} - {next_orb_end.strftime('%H:%M')}",
                "medium"
            ), unsafe_allow_html=True)

        st.markdown(render_countdown_timer(
            f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            "Until ORB Window"
        ), unsafe_allow_html=True)

        # Setup details (if not skipped)
        if not is_skip:
            st.markdown("### Setup Details")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(render_pro_metric(
                    "CONFIG",
                    f"{orb_config.get('rr', '?')}R",
                    orb_config.get("sl_mode", "?")
                ), unsafe_allow_html=True)
            with col2:
                filter_text = f"< {filter_threshold*100:.0f}% ATR" if filter_threshold else "None"
                filter_detail = f"~{atr * filter_threshold:.1f}pts" if (filter_threshold and atr) else "All sizes OK"
                st.markdown(render_pro_metric(
                    "FILTER",
                    filter_text,
                    filter_detail
                ), unsafe_allow_html=True)
            with col3:
                risk_pct = "0.50%" if orb_config.get("tier", "DAY") == "NIGHT" else "0.25%"
                st.markdown(render_pro_metric(
                    "POSITION RISK",
                    risk_pct
                ), unsafe_allow_html=True)

# ========================================================================
# LIVE TRADING CHART with TRADE ZONES
# ========================================================================
st.subheader("📈 Live Trading Chart")

try:
    # Get recent bars
    bars_df = st.session_state.data_loader.fetch_latest_bars(
        lookback_minutes=CHART_LOOKBACK_BARS
    )

    if bars_df.empty:
        st.warning("⏳ No bar data available - click 'Initialize/Refresh Data' in sidebar")
    else:
        # Get current price
        latest_bar = st.session_state.data_loader.get_latest_bar()
        current_price = latest_bar['close'] if latest_bar else None

        # Get ORB data from strategy state
        state = evaluation.state
        orb_high = state.current_orb_high if hasattr(state, 'current_orb_high') else None
        orb_low = state.current_orb_low if hasattr(state, 'current_orb_low') else None
        orb_name = state.active_orb_name if hasattr(state, 'active_orb_name') else "0900"

        # Calculate ORB window times
        if orb_name and evaluation.strategy_name:
            # Extract hour and minute from orb_name (e.g., "0900" -> hour=9, min=0)
            orb_hour = int(orb_name[:2])
            orb_min = int(orb_name[2:]) if len(orb_name) == 4 else 0

            now_local = datetime.now(TZ_LOCAL)
            orb_start = now_local.replace(hour=orb_hour, minute=orb_min, second=0, microsecond=0)
            orb_end = orb_start + timedelta(minutes=5)

            # Handle midnight crossing
            if orb_hour == 0 and now_local.hour >= 12:
                orb_start += timedelta(days=1)
                orb_end += timedelta(days=1)
        else:
            orb_start = None
            orb_end = None

        # Get trade details if there's an active setup
        entry_price = None
        stop_price = None
        target_price = None
        direction = None

        if evaluation.action == ActionType.ENTER and orb_high and orb_low:
            # Determine direction based on current price vs ORB
            if current_price and current_price > orb_high:
                direction = "LONG"
            elif current_price and current_price < orb_low:
                direction = "SHORT"

            # Get setup config for this ORB
            engine = st.session_state.strategy_engine
            orb_config = engine.orb_configs.get(orb_name, {})

            if direction and orb_config:
                # Calculate trade levels
                levels = calculate_trade_levels(
                    orb_high=orb_high,
                    orb_low=orb_low,
                    direction=direction,
                    rr=orb_config.get('rr', 1.0),
                    sl_mode=orb_config.get('sl_mode', 'FULL')
                )

                entry_price = levels['entry']
                stop_price = levels['stop']
                target_price = levels['target']

        # Check filter status
        filter_passed = True
        tier = "B"
        if orb_high and orb_low and orb_name:
            engine = st.session_state.strategy_engine
            orb_config = engine.orb_configs.get(orb_name, {})
            tier = orb_config.get('tier', 'B')

            # Check filter
            filter_result = st.session_state.data_loader.check_orb_size_filter(
                orb_high, orb_low, orb_name
            )
            filter_passed = filter_result.get('pass', True)

        # Build the live trading chart with trade zones
        fig = build_live_trading_chart(
            bars_df=bars_df,
            orb_high=orb_high,
            orb_low=orb_low,
            orb_name=orb_name,
            orb_start=orb_start,
            orb_end=orb_end,
            current_price=current_price,
            filter_passed=filter_passed,
            tier=tier,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            direction=direction,
            height=CHART_HEIGHT
        )

        # Display chart with ORB status card on the right
        chart_col, orb_status_col = st.columns([3, 1])

        with chart_col:
            st.plotly_chart(fig, use_container_width=True)

        with orb_status_col:
            st.markdown("### 📊 ORB Status")

            # Current ORB info
            if orb_high and orb_low:
                orb_size_pts = orb_high - orb_low
                st.metric("ORB High", f"${orb_high:.2f}")
                st.metric("ORB Low", f"${orb_low:.2f}")
                st.metric("Size", f"{orb_size_pts:.2f} pts")

                # Filter status
                if filter_passed:
                    st.success("✅ Filter PASSED")
                else:
                    st.error("❌ Filter FAILED")
            else:
                st.info("⏳ No active ORB")

            st.divider()

            # Next ORB countdown (compact)
            now = datetime.now(TZ_LOCAL)
            orb_times = {
                "0900": (9, 0), "1000": (10, 0), "1100": (11, 0),
                "1800": (18, 0), "2300": (23, 0), "0030": (0, 30)
            }

            next_orb_name = None
            next_orb_start = None
            min_delta = timedelta(days=1)

            for orb_name, (hour, minute) in orb_times.items():
                orb_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if hour == 0 and now.hour >= 12:
                    orb_start += timedelta(days=1)
                if orb_start > now:
                    delta = orb_start - now
                    if delta < min_delta:
                        min_delta = delta
                        next_orb_name = orb_name
                        next_orb_start = orb_start

            if next_orb_name:
                time_until = (next_orb_start - now).total_seconds()
                hours = int(time_until // 3600)
                minutes = int((time_until % 3600) // 60)
                st.markdown(f"**Next ORB**: {next_orb_name}")
                st.markdown(f"⏱️ {hours}h {minutes}m")

        # Trade levels summary below chart
        if entry_price and direction:
            st.markdown("### 🎯 Trade Levels")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(render_pro_metric(
                    "DIRECTION",
                    f"{'🚀 LONG' if direction == 'LONG' else '🔻 SHORT'}"
                ), unsafe_allow_html=True)

            with col2:
                st.markdown(render_pro_metric(
                    "ENTRY",
                    f"${entry_price:.2f}"
                ), unsafe_allow_html=True)

            with col3:
                st.markdown(render_pro_metric(
                    "STOP",
                    f"${stop_price:.2f}",
                    f"-${abs(entry_price - stop_price):.2f}",
                    False
                ), unsafe_allow_html=True)

            with col4:
                st.markdown(render_pro_metric(
                    "TARGET",
                    f"${target_price:.2f}",
                    f"+${abs(target_price - entry_price):.2f}",
                    True
                ), unsafe_allow_html=True)

except Exception as e:
    st.error(f"Chart error: {e}")
    logger.error(f"Chart error: {e}", exc_info=True)

# Entry details if READY or ACTIVE - STREAMLINED
if evaluation and evaluation.action in [ActionType.ENTER, ActionType.MANAGE]:
    st.divider()

    # Prominent trade details card
    st.markdown("### 📍 TRADE DETAILS")

    # Calculate all metrics
    entry_price = evaluation.entry_price or 0
    stop_price = evaluation.stop_price or 0
    target_price = evaluation.target_price or 0
    risk_pct = evaluation.risk_pct or 0
    risk_dollars = account_size * (risk_pct / 100)

    # Calculate R:R ratio
    if entry_price and stop_price and target_price:
        risk_points = abs(entry_price - stop_price)
        reward_points = abs(target_price - entry_price)
        rr_ratio = reward_points / risk_points if risk_points > 0 else 0
        direction = "LONG" if target_price > entry_price else "SHORT"
    else:
        rr_ratio = 0
        direction = "UNKNOWN"

    # Visual trade card with gradient
    trade_color = "#198754" if evaluation.action == ActionType.ENTER else "#fd7e14"

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {trade_color}15 0%, {trade_color}25 100%);
        border: 3px solid {trade_color};
        border-radius: 12px;
        padding: 24px;
        margin: 16px 0;
    ">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">Direction</div>
                <div style="font-size: 28px; font-weight: bold; color: {trade_color};">{direction}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">Entry</div>
                <div style="font-size: 28px; font-weight: bold; color: #333;">${entry_price:.2f}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">Stop</div>
                <div style="font-size: 28px; font-weight: bold; color: #dc3545;">${stop_price:.2f}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">Target</div>
                <div style="font-size: 28px; font-weight: bold; color: #198754;">${target_price:.2f}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">R:R Ratio</div>
                <div style="font-size: 28px; font-weight: bold; color: #0d6efd;">1:{rr_ratio:.1f}</div>
            </div>
            <div style="text-align: center; padding: 16px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <div style="font-size: 14px; color: #666; text-transform: uppercase; margin-bottom: 8px;">Risk</div>
                <div style="font-size: 24px; font-weight: bold; color: #fd7e14;">${risk_dollars:.0f}</div>
                <div style="font-size: 14px; color: #666;">({risk_pct:.2f}%)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Active positions panel removed per user request

# ============================================================================
# CONDITIONAL EDGES - MARKET STATE & ACTIVE SETUPS
# ============================================================================
st.divider()

with st.expander("🎯 Conditional Edges (Phase 1B)", expanded=True):
    try:
        from render_conditional_edges import render_conditional_edges_full

        # Get current price from latest bar
        if current_price > 0:
            render_conditional_edges_full(
                instrument=symbol,
                current_price=current_price
            )
        else:
            st.warning("⚠️ No price data available. Load data to see conditional edges.")
    except Exception as e:
        st.error(f"Error loading Conditional Edges: {e}")
        logger.error(f"Conditional edges error: {e}", exc_info=True)

# ============================================================================
# STRATEGY DISCOVERY & EDGE CANDIDATES
# ============================================================================
st.divider()

# Discovery Panel - Create new candidates
with st.expander("🔬 Strategy Discovery (Backtest New Setups)", expanded=False):
    try:
        from discovery_ui import render_discovery_panel
        render_discovery_panel()
    except Exception as e:
        st.error(f"Error loading Discovery panel: {e}")
        logger.error(f"Discovery panel error: {e}", exc_info=True)

st.divider()

# Edge Candidates Review - Approve and promote
with st.expander("🎯 Edge Candidates Review & Approval", expanded=True):
    try:
        from edge_candidates_ui import render_edge_candidates_panel
        render_edge_candidates_panel()
    except Exception as e:
        st.error(f"Error loading Edge Candidates panel: {e}")
        logger.error(f"Edge Candidates panel error: {e}", exc_info=True)

# ============================================================================
# CHART UPLOAD & VISION ANALYSIS
# ============================================================================
st.divider()
st.title("📸 Upload Chart for AI Analysis")

st.markdown("""
**Upload a TradingView screenshot** and get AI-powered analysis with:
- Pattern recognition
- Support/resistance levels
- Strategy recommendations
- Entry/exit suggestions
""")

# Initialize chart analyzer if not exists
if "chart_analyzer" not in st.session_state:
    from chart_analyzer import ChartAnalyzer
    st.session_state.chart_analyzer = ChartAnalyzer(instrument=symbol)

chart_analyzer = st.session_state.chart_analyzer

if not chart_analyzer.is_available():
    st.error("⚠️ Chart analysis not available. Add ANTHROPIC_API_KEY to .env file.")
else:
    st.success("✅ Chart analyzer ready! (Claude Vision API)")

    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a chart image or CSV",
        type=["png", "jpg", "jpeg", "csv"],
        help="Upload a TradingView screenshot (image) or CSV export for AI analysis"
    )

    if uploaded_file is not None:
        # Detect file type
        is_csv = uploaded_file.name.endswith('.csv')

        if is_csv:
            # ===== CSV HANDLING =====
            st.info("📊 CSV file detected. Parsing TradingView chart data...")

            try:
                import pandas as pd
                import io

                # Read CSV
                csv_data = uploaded_file.read()
                df = pd.read_csv(io.BytesIO(csv_data))

                # Show preview
                st.subheader("📋 CSV Preview")
                st.dataframe(df.head(10), use_container_width=True)

                # Validate required columns (case-insensitive check)
                df_columns_lower = [col.lower() for col in df.columns]
                required_cols = ['time', 'open', 'high', 'low', 'close']
                missing_cols = [col for col in required_cols if col not in df_columns_lower]

                if missing_cols:
                    st.error(f"❌ CSV validation failed. Missing required columns: {', '.join(missing_cols)}")
                    st.info("Required columns: time, open, high, low, close (volume is optional)")
                    st.warning("⚠️ CSV NOT ingested. Fix the file and upload again.")
                else:
                    st.success(f"✅ CSV validation passed! Found {len(df)} rows.")
                    st.info("**Columns detected:** " + ", ".join(df.columns.tolist()))

                    # Analyze button for CSV
                    if st.button("🔍 Analyze CSV Chart Data", type="primary"):
                        with st.spinner("Analyzing CSV data with Claude Vision..."):
                            try:
                                # Convert CSV to text summary for analysis
                                csv_summary = f"""
TradingView CSV Data Summary:
- Rows: {len(df)}
- Columns: {', '.join(df.columns.tolist())}
- Date Range: {df.iloc[0]['time'] if 'time' in df.columns else 'N/A'} to {df.iloc[-1]['time'] if 'time' in df.columns else 'N/A'}

First 5 rows:
{df.head().to_string()}

Last 5 rows:
{df.tail().to_string()}
"""

                                # Use chart analyzer with CSV text (no image)
                                # For now, just show the summary since chart_analyzer expects image bytes
                                st.subheader("📊 CSV Data Summary")
                                st.text(csv_summary)
                                st.info("💡 CSV ingestion into database coming soon. For now, use image uploads for AI analysis.")

                            except Exception as e:
                                st.error(f"❌ Error analyzing CSV: {e}")
                                logger.error(f"CSV analysis error: {e}", exc_info=True)

            except Exception as e:
                st.error(f"❌ Failed to parse CSV file: {e}")
                st.warning("⚠️ Ensure the file is a valid CSV with headers: time, open, high, low, close")
                logger.error(f"CSV parse error: {e}", exc_info=True)

        else:
            # ===== IMAGE HANDLING (EXISTING LOGIC) =====
            # Display uploaded image
            st.image(uploaded_file, caption="Uploaded Chart", use_column_width=True)

            # Analyze button
            if st.button("🔍 Analyze Chart", type="primary"):
                with st.spinner("Analyzing chart with Claude Vision..."):
                    try:
                        # Read image bytes
                        image_bytes = uploaded_file.read()

                        # Determine image type
                        image_type = "image/jpeg" if uploaded_file.name.endswith(('.jpg', '.jpeg')) else "image/png"

                        # Call vision API
                        analysis = chart_analyzer.analyze_chart_image(image_bytes, image_type)

                        if analysis:
                            st.success("✅ Analysis complete!")

                            # Display results
                            st.subheader("📊 Analysis Results")

                            if "pattern" in analysis:
                                st.markdown(f"**Pattern Detected:** {analysis['pattern']}")

                            if "levels" in analysis:
                                st.markdown("**Key Levels:**")
                                for level in analysis['levels']:
                                    st.write(f"- {level}")

                            if "strategy" in analysis:
                                st.markdown(f"**Recommended Strategy:** {analysis['strategy']}")

                            if "setup" in analysis:
                                st.markdown(f"**Setup:** {analysis['setup']}")

                            if "raw_response" in analysis:
                                with st.expander("📝 Full Analysis"):
                                    st.markdown(analysis['raw_response'])

                        else:
                            st.error("❌ Analysis failed. Check logs for details.")

                    except Exception as e:
                        st.error(f"❌ Error analyzing chart: {e}")
                        logger.error(f"Chart analysis error: {e}", exc_info=True)

# ============================================================================
# AI CHAT - STREAMLINED AT BOTTOM OF PAGE
# ============================================================================
st.divider()
st.title("🧠 AI Strategy Advisor")
st.caption("💡 Chat about strategy ideas → Say 'test this' → Auto-execute backtest → Create edge candidates")

# Check if AI is available
if not st.session_state.ai_assistant.is_available():
    st.error("⚠️ AI Assistant not available. Add ANTHROPIC_API_KEY to .env file.")
    st.info("Get your API key from: https://console.anthropic.com/")
    st.code("ANTHROPIC_API_KEY=sk-ant-your-key-here", language="bash")
else:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.success("✅ Strategy Advisor ready! Claude Sonnet 4.5 - Discuss strategies, auto-execute backtests")
    with col2:
        if len(st.session_state.chat_history) > 0:
            st.metric("💾 Memory", f"{len(st.session_state.chat_history)} messages")

    # Memory management
    with st.expander("🗂️ Memory Management"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reload History", help="Reload last 50 messages from database"):
                try:
                    loaded_history = st.session_state.memory_manager.load_session_history(
                        session_id=st.session_state.session_id,
                        limit=50
                    )
                    st.session_state.chat_history = [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in loaded_history
                    ]
                    st.success(f"Reloaded {len(loaded_history)} messages")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error reloading: {e}")

        with col2:
            if st.button("🗑️ Clear Session", help="Clear current session (database kept)", type="secondary"):
                st.session_state.chat_history = []
                st.success("Session cleared (database preserved)")
                st.rerun()

        st.caption("💾 All messages are automatically saved to database and persist across app restarts")

    # Display chat history
    st.subheader("💬 Conversation")

    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.info("Start a conversation! Ask me about strategies, risk calculations, or trade setups.")
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f"**You:** {msg['content']}")
                else:
                    st.markdown(f"**AI:** {msg['content']}")
                    st.divider()

    # Chat input
    st.subheader("Ask a Question")

    user_input = st.text_area(
        "Your message:",
        key="ai_chat_input",
        placeholder="Example: I'm thinking about testing MGC 2300 ORB with 1.5R and HALF stop, filter at 15.5% ATR. What do you think?",
        height=100
    )

    # Initialize Strategy Advisor if not exists
    if 'strategy_advisor' not in st.session_state:
        try:
            from strategy_advisor import StrategyAdvisor
            st.session_state.strategy_advisor = StrategyAdvisor()
        except Exception as e:
            logger.error(f"Error initializing Strategy Advisor: {e}")
            st.session_state.strategy_advisor = None

    col1, col2, col3 = st.columns([1, 1, 3])

    with col1:
        if st.button("Send", type="primary", use_container_width=True):
            if user_input.strip():
                with st.spinner("Thinking..."):
                    # Use Strategy Advisor if available, fallback to basic AI
                    if st.session_state.strategy_advisor:
                        # Enhanced chat with strategy discovery execution
                        response, execution_result = st.session_state.strategy_advisor.chat_with_execution(
                            user_message=user_input,
                            conversation_history=st.session_state.chat_history,
                            auto_execute=True  # Auto-execute when user says "test this"
                        )

                        # Show execution notification if backtest was run
                        if execution_result:
                            if execution_result["success"]:
                                if execution_result["candidate_id"]:
                                    st.success(f"🎯 Edge Candidate #{execution_result['candidate_id']} created!")
                                else:
                                    st.info("Backtest completed but not profitable enough")
                            else:
                                st.warning("Backtest execution had issues")
                    else:
                        # Fallback to basic AI assistant
                        try:
                            # Get current context
                            strategy_state = None
                            if st.session_state.get('last_evaluation'):
                                result = st.session_state.last_evaluation
                                strategy_state = {
                                    'strategy': getattr(result, 'strategy_name', 'None'),
                                    'action': getattr(result, 'action', 'STAND_DOWN'),
                                    'reasons': getattr(result, 'reasons', []),
                                    'next_action': getattr(result, 'next_instruction', 'Wait'),
                                    'current_session': 'Unknown'
                                }

                            # Get current price
                            current_price = 0
                            if st.session_state.data_loader:
                                latest = st.session_state.data_loader.get_latest_bar()
                                if latest:
                                    current_price = latest.get('close', 0)

                            # Call basic AI
                            response = st.session_state.ai_assistant.chat(
                                user_message=user_input,
                                conversation_history=st.session_state.chat_history,
                                session_id=st.session_state.session_id,
                                instrument=st.session_state.current_symbol,
                                current_price=current_price,
                                strategy_state=strategy_state,
                                session_levels={},
                                orb_data={},
                                backtest_stats={}
                            )
                        except Exception as e:
                            response = f"Error: {str(e)}"
                            logger.error(f"AI chat error: {e}", exc_info=True)

                    # Update history
                    st.session_state.chat_history.append({"role": "user", "content": user_input})
                    st.session_state.chat_history.append({"role": "assistant", "content": response})

                    # Save to memory
                    try:
                        st.session_state.ai_memory.save_message(
                            session_id=st.session_state.session_id,
                            role="user",
                            content=user_input,
                            instrument=st.session_state.current_symbol
                        )
                        st.session_state.ai_memory.save_message(
                            session_id=st.session_state.session_id,
                            role="assistant",
                            content=response,
                            instrument=st.session_state.current_symbol
                        )
                    except:
                        pass

                # Rerun to show new messages
                st.rerun()

    with col2:
        if st.button("Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    # Quick examples
    st.subheader("💡 Example Questions")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Strategy Discovery:**
        - "I want to test MGC 2300 ORB with 1.5R and HALF stop"
        - "Let's try 0030 ORB with 3.0R, filter at 11.2% ATR"
        - "What if we use FULL stop on 1000 ORB instead?"

        **Then say:** "test this" or "run it" to execute!
        """)

    with col2:
        st.markdown("""
        **Strategy Questions:**
        - "Why is 2300 ORB better than 0900?"
        - "What's the best RR for night ORBs?"
        - "Should I use FULL or HALF stop?"
        - "Explain ORB size filters"
        """)

    # Show recent trade discussions from memory
    st.divider()
    st.subheader("📚 Recent Trade Discussions")

    recent_trades = st.session_state.memory_manager.get_recent_trades(
        session_id=st.session_state.session_id,
        days=7
    )

    if recent_trades:
        for trade in recent_trades[:5]:
            with st.expander(f"{trade['timestamp'].strftime('%Y-%m-%d %H:%M')} - {trade['role']}"):
                st.write(trade['content'])
    else:
        st.info("No recent trade discussions found. Start asking questions to build your memory!")

# ============================================================================
# AUTO-REFRESH
# ============================================================================
if auto_refresh and st.session_state.data_loader:
    time.sleep(DATA_REFRESH_SECONDS)
    st.rerun()
