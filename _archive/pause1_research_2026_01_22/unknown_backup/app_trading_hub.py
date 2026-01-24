"""
MGC ORB Trading Hub - Enhanced Dashboard with AI Assistant
"""

from __future__ import annotations

import io
import os
import inspect
from datetime import datetime, time
from typing import Any, Dict, Optional, Tuple, List
from dataclasses import asdict
import pytz

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

import query_engine as qe
from analyze_orb_v2 import ORBAnalyzerV2
from validated_strategies import VALIDATED_MGC_STRATEGIES, TOP_STRATEGIES, CORRELATION_STRATEGIES, get_tradeable_strategies

# Load environment variables
load_dotenv()

# Page config MUST be first Streamlit command
st.set_page_config(
    page_title="ORB Trading Hub",
    layout="wide",
)

# Optional debug (safe here, after set_page_config)
# st.write("query_engine loaded from:", qe.__file__)
# st.write("Filters signature:", str(inspect.signature(qe.Filters)))

# ============================================================================
# AI CHAT INTEGRATION
# ============================================================================

class TradingAIAssistant:
    """AI assistant for trading research using Claude API"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            st.warning("⚠️ No ANTHROPIC_API_KEY found in environment. AI chat disabled.")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def get_system_context(self, data_summary: Dict[str, Any], current_price: float = 0, symbol: str = "MGC") -> str:
        """Generate system context about current data state"""

        live_data_context = ""
        if current_price > 0:
            live_data_context = f"""
**LIVE MARKET DATA AVAILABLE:**
- Current {symbol} Price: {current_price}
- You CAN see live prices and calculate distances to stops/targets
- When asked "what's the market doing", reference this live price
"""
        else:
            live_data_context = """
**NO LIVE PRICE DATA:**
- User hasn't entered current price yet
- Ask them to input current price in the sidebar for live analysis
"""

        return f"""You are a live trading assistant for ORB (Opening Range Breakout) strategies on MGC (Micro Gold) and NQ (Micro Nasdaq).

Your PRIMARY job is to help calculate stops, targets, and risk management in real-time.

{live_data_context}

CRITICAL CALCULATION RULES:

**MGC (Micro Gold) - HALF SL Mode:**
- Stop = ORB Midpoint (always)
- Risk (1R) = Distance from ORB edge to midpoint (HALF the ORB range)
- Target = ORB edge + (1.5 × Risk)
- Example: ORB 4615-4621 going LONG
  * Midpoint = 4618.0
  * Stop = 4618.0
  * Risk = 4621 - 4618 = 3.0 points (30 ticks) = 1R
  * Target = 4621 + 4.5 = 4625.5

**NQ (Micro Nasdaq) - FULL SL Mode:**
- Stop = Opposite ORB edge (always)
- Risk (1R) = Full ORB range
- Target = ORB edge + (1.5 × Risk)
- Filter: ORB must be < 0.100 × ATR(20)
- Example: ORB 25,595-25,607 going SHORT
  * Stop = 25,607 (ORB High)
  * Risk = 12 points (48 ticks) = 1R
  * Target = 25,595 - 18 = 25,577

**When User Asks for Calculations:**
1. Ask for: ORB High, ORB Low, Direction (LONG/SHORT)
2. Calculate midpoint (MGC) or identify opposite edge (NQ)
3. Show exact stop price
4. Show exact target price
5. Show risk in points and ticks

**Filter Checks:**
- MGC 10:00: Only if 09:00 hit 1R MFE (moved 1R in profitable direction)
- MGC 23:00: Skip if ORB > 0.155 × ATR
- MGC 00:30: Skip if Pre-NY travel < 167 ticks
- NQ 10:00: Skip if ORB > 0.100 × ATR
- MGC 09:00, 11:00, 18:00: No filter (baseline)

**When User Says "I'm in a trade":**
- Ask for entry price, ORB high/low, direction
- Calculate their exact stop and target
- Tell them current risk/reward
- Warn if they're close to stop

Current Data Context:
- Total days analyzed: {data_summary.get('total_days', 'N/A')}
- Date range: {data_summary.get('date_range', 'N/A')}
- ORBs tracked: 09:00, 10:00, 11:00, 18:00, 23:00, 00:30 (6 per day)

Be SPECIFIC with numbers. Don't give ranges - give exact prices. Be helpful for live trading.
"""

    def chat(self, user_message: str, conversation_history: List[Dict], data_summary: Dict, current_price: float = 0, symbol: str = "MGC") -> str:
        """Send message to Claude and get response"""
        if not self.is_available():
            return "AI assistant is not available. Please set ANTHROPIC_API_KEY environment variable."

        try:
            # Build messages from conversation history
            messages = conversation_history + [{"role": "user", "content": user_message}]

            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                system=self.get_system_context(data_summary, current_price, symbol),
                messages=messages
            )

            return response.content[0].text

        except Exception as e:
            return f"Error communicating with AI: {str(e)}"

# ============================================================================
# CACHING & DATA LOADING
# ============================================================================

@st.cache_resource(show_spinner=False)
def get_connection():
    return qe.get_connection("gold.db")

@st.cache_resource(show_spinner=False)
def get_ai_assistant():
    return TradingAIAssistant()

@st.cache_data(show_spinner=False)
def load_metadata() -> Dict[str, Any]:
    return qe.fetch_filter_metadata(get_connection())

@st.cache_data(show_spinner=False)
def load_headline_stats(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...],
    filters: qe.Filters, strategy: qe.StrategyConfig
) -> Dict[str, Any]:
    return qe.headline_stats_with_strategy(get_connection(), filters, strategy)

@st.cache_data(show_spinner=False)
def load_equity_curve(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...],
    filters: qe.Filters, strategy: qe.StrategyConfig
) -> pd.DataFrame:
    return qe.equity_curve_with_strategy(get_connection(), filters, strategy)

@st.cache_data(show_spinner=False)
def load_drilldown(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...],
    filters: qe.Filters, strategy: qe.StrategyConfig,
    limit: Optional[int], order: str
) -> pd.DataFrame:
    return qe.drilldown_with_strategy(get_connection(), filters, strategy, limit=limit, order=order)

@st.cache_data(show_spinner=False)
def load_funnel(
    filters_key: Tuple[Any, ...], strategy_key: Tuple[Any, ...],
    filters: qe.Filters, strategy: qe.StrategyConfig
) -> Dict[str, int]:
    return qe.entry_funnel(get_connection(), filters, strategy)

@st.cache_data(show_spinner=False)
def discover_edges() -> Dict[str, Any]:
    """Run edge discovery analysis"""
    # Reuse the existing connection to avoid DuckDB connection conflicts
    con = get_connection()
    analyzer = ORBAnalyzerV2(connection=con)

    # Discover all edges
    overall = analyzer.analyze_overall()
    pre_asia = analyzer.analyze_pre_asia()
    correlations = analyzer.analyze_orb_correlations()

    # Find best edges
    all_edges = []

    # Add overall edges
    for orb_time, stats in overall.items():
        for direction in ['UP', 'DOWN']:
            if direction in stats:
                all_edges.append({
                    'setup': f"{orb_time} {direction}",
                    'type': 'baseline',
                    **stats[direction]
                })

    # Add PRE block edges
    for edge in pre_asia:
        all_edges.append({
            'setup': edge['setup'],
            'type': 'pre_block',
            **edge
        })

    # Add correlation edges
    for edge in correlations:
        all_edges.append({
            'setup': edge['setup'],
            'type': 'correlation',
            **edge
        })

    # Sort by win rate * avg_r (quality score)
    for edge in all_edges:
        edge['quality_score'] = edge.get('win_rate', 0) * edge.get('avg_r', 0)

    all_edges.sort(key=lambda x: x['quality_score'], reverse=True)

    return {
        'all_edges': all_edges,
        'overall': overall,
        'pre_asia': pre_asia,
        'correlations': correlations
    }

@st.cache_data(show_spinner=False)
def load_filtered_backtest_results(symbol='MGC'):
    """Load VALIDATED, HONEST strategies - Zero Lookahead, Professional Grade"""

    if symbol == 'MGC':
        # Use validated strategies from TRADING_PLAYBOOK.md analysis
        results = {}
        for orb_code, strategy in VALIDATED_MGC_STRATEGIES.items():
            if strategy['tradeable']:  # Only include profitable strategies
                results[orb_code] = {
                    'trades': strategy['trades'],
                    'wins': strategy['wins'],
                    'losses': strategy['losses'],
                    'win_rate': strategy['win_rate'],
                    'expectancy': strategy['expectancy'],
                    'avg_mae': 0,  # Not relevant for strategy display
                    'avg_mfe': 0,
                    'mae_p50': 0,
                    'mfe_p50': 0,
                    'mae_p90': 0,
                    'mfe_p90': 0,
                    'notes': strategy['notes']
                }
        return results

    elif symbol == 'NQ':
        # Load NQ data from database (still valid)
        import duckdb
        con = duckdb.connect("gold.db")
        table_name = 'daily_features_v2_nq'
        orb_times = ['0900', '1000', '1100', '1800', '0030']  # Skip 2300 for NQ
        results = {}

        for orb_time in orb_times:
            query = f"""
            SELECT
                COUNT(*) as trades,
                SUM(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN orb_{orb_time}_outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                AVG(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1.0 ELSE -1.0 END) as expectancy
            FROM {table_name}
            WHERE orb_{orb_time}_break_dir IS NOT NULL
              AND orb_{orb_time}_break_dir != 'NONE'
            """

            result = con.execute(query).fetchone()
            if result and result[0] > 0:
                expectancy = result[3] if result[3] else 0
                if expectancy > 0:  # Only show profitable NQ strategies
                    results[orb_time] = {
                        'trades': result[0],
                        'wins': result[1],
                        'losses': result[2],
                        'win_rate': result[1] / (result[1] + result[2]) if (result[1] + result[2]) > 0 else 0,
                        'expectancy': expectancy,
                        'avg_mae': 0,
                        'avg_mfe': 0,
                        'mae_p50': 0,
                        'mfe_p50': 0,
                        'mae_p90': 0,
                        'mfe_p90': 0
                    }

        con.close()
        return results

    return {}

@st.cache_data(show_spinner=False)
def load_session_breakdown():
    """Load session breakdown (Asia, London, NY)"""
    results = load_filtered_backtest_results()

    sessions = {
        'ASIA': ['0900', '1000', '1100'],
        'LONDON': ['1800'],
        'NY': ['2300', '0030']
    }

    session_results = {}
    for session_name, orb_times in sessions.items():
        total_trades = sum(results.get(orb, {}).get('trades', 0) for orb in orb_times)
        total_wins = sum(results.get(orb, {}).get('wins', 0) for orb in orb_times)
        total_losses = sum(results.get(orb, {}).get('losses', 0) for orb in orb_times)

        if total_trades > 0:
            win_rate = total_wins / (total_wins + total_losses) if (total_wins + total_losses) > 0 else 0
            # Weighted average expectancy
            expectancy = sum(
                results.get(orb, {}).get('expectancy', 0) * results.get(orb, {}).get('trades', 0)
                for orb in orb_times
            ) / total_trades

            session_results[session_name] = {
                'trades': total_trades,
                'wins': total_wins,
                'losses': total_losses,
                'win_rate': win_rate,
                'expectancy': expectancy,
                'total_r': expectancy * total_trades
            }

    return session_results

# ============================================================================
# TIME-AWARE STRATEGY DISPLAY
# ============================================================================

def get_current_brisbane_time():
    """Get current time in Brisbane timezone"""
    brisbane_tz = pytz.timezone('Australia/Brisbane')
    return datetime.now(brisbane_tz)

def get_orb_status(current_time: datetime):
    """Determine status of each ORB based on current time"""
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_time_minutes = current_hour * 60 + current_minute

    orbs = [
        {'time': '00:30', 'start_min': 30, 'end_min': 35, 'session': 'NY'},
        {'time': '09:00', 'start_min': 540, 'end_min': 545, 'session': 'Asia'},
        {'time': '10:00', 'start_min': 600, 'end_min': 605, 'session': 'Asia'},
        {'time': '11:00', 'start_min': 660, 'end_min': 665, 'session': 'Asia'},
        {'time': '18:00', 'start_min': 1080, 'end_min': 1085, 'session': 'London'},
        {'time': '23:00', 'start_min': 1380, 'end_min': 1385, 'session': 'NY'},
    ]

    statuses = []
    for orb in orbs:
        if current_time_minutes < orb['start_min']:
            status = 'upcoming'
        elif orb['start_min'] <= current_time_minutes < orb['end_min']:
            status = 'forming'
        elif orb['end_min'] <= current_time_minutes < orb['end_min'] + 60:  # Within 1 hour after
            status = 'active'
        else:
            status = 'completed'

        statuses.append({
            'time': orb['time'],
            'session': orb['session'],
            'status': status,
            'start_min': orb['start_min'],
            'end_min': orb['end_min']
        })

    return statuses

def render_time_aware_dashboard(orb_results: Dict):
    """Render time-aware strategy dashboard"""
    st.markdown("## 🕐 Live Trading Dashboard")

    current_time = get_current_brisbane_time()
    st.markdown(f"**Current Brisbane Time:** {current_time.strftime('%H:%M:%S')} | {current_time.strftime('%A, %B %d, %Y')}")

    # FILTER OUT NEGATIVE EXPECTANCY TRADES - Only show profitable strategies
    orb_results = {code: result for code, result in orb_results.items() if result.get('expectancy', 0) > 0}

    orb_statuses = get_orb_status(current_time)

    # Separate ORBs by status
    forming_orbs = [o for o in orb_statuses if o['status'] == 'forming']
    active_orbs = [o for o in orb_statuses if o['status'] == 'active']
    upcoming_orbs = [o for o in orb_statuses if o['status'] == 'upcoming']
    completed_orbs = [o for o in orb_statuses if o['status'] == 'completed']

    # FORMING ORB (highest priority)
    if forming_orbs:
        st.markdown("---")
        st.markdown("### 🔴 NOW FORMING - WATCH CLOSELY!")
        for orb in forming_orbs:
            st.markdown(f"""
            <div style="background: #ffebee; border: 3px solid #f44336; border-radius: 8px; padding: 20px; margin: 10px 0;">
                <h2 style="color: #c62828; margin: 0;">{orb['time']} ORB - {orb['session']} Session</h2>
                <p style="font-size: 1.2em; margin: 10px 0;"><strong>STATUS:</strong> Range is forming RIGHT NOW ({orb['time']}-{orb['time'][:2]}:05)</p>
                <p style="font-size: 1.1em;"><strong>ACTION:</strong> Record the HIGH and LOW. Wait for breakout after {orb['time'][:2]}:05.</p>
            </div>
            """, unsafe_allow_html=True)

    # ACTIVE ORBs (trade opportunities)
    if active_orbs:
        st.markdown("---")
        st.markdown("### ⚡ ACTIVE - READY TO TRADE")
        for orb in active_orbs:
            orb_code = orb['time'].replace(':', '')
            result = orb_results.get(orb_code, {})

            win_rate = result.get('win_rate', 0) * 100
            expectancy = result.get('expectancy', 0)
            trades = result.get('trades', 0)

            strategy_text = get_strategy_recommendation(orb_code)

            st.markdown(f"""
            <div style="background: #e8f5e9; border: 3px solid #4caf50; border-radius: 8px; padding: 20px; margin: 10px 0;">
                <h2 style="color: #2e7d32; margin: 0;">{orb['time']} ORB - {orb['session']} Session</h2>
                <p style="font-size: 1.2em; margin: 10px 0;"><strong>STATUS:</strong> Breakout window is OPEN</p>
                <div style="display: flex; gap: 20px; margin: 10px 0;">
                    <div><strong>Win Rate:</strong> {win_rate:.1f}%</div>
                    <div><strong>Expectancy:</strong> {expectancy:+.3f}R</div>
                    <div><strong>Sample:</strong> {trades} trades</div>
                </div>
                <p style="font-size: 1.1em; margin: 10px 0;"><strong>STRATEGY:</strong></p>
                {strategy_text}
            </div>
            """, unsafe_allow_html=True)

    # UPCOMING ORBs
    if upcoming_orbs:
        st.markdown("---")
        st.markdown("### 📅 UPCOMING - PREPARE")
        st.markdown("*Set alarms and review strategies before these times*")

        # Calculate minutes until each upcoming ORB
        current_time_minutes = current_time.hour * 60 + current_time.minute

        for orb in upcoming_orbs:
            orb_code = orb['time'].replace(':', '')
            result = orb_results.get(orb_code, {})

            # Calculate time until
            time_until_min = orb['start_min'] - current_time_minutes
            if time_until_min < 0:
                time_until_min += 1440  # Add 24 hours if it's tomorrow

            hours_until = time_until_min // 60
            mins_until = time_until_min % 60
            time_until_str = f"{hours_until}h {mins_until}m" if hours_until > 0 else f"{mins_until}m"

            # Color coding based on win rate
            win_rate = result.get('win_rate', 0)
            expectancy = result.get('expectancy', 0)

            if win_rate >= 0.60:
                border_color = "#4caf50"  # Green
                quality = "🟢 HIGH"
            elif win_rate >= 0.55:
                border_color = "#ff9800"  # Orange
                quality = "🟡 MEDIUM"
            else:
                border_color = "#f44336"  # Red
                quality = "🔴 LOW"

            # Filter indicator
            filter_text = ""
            if orb_code == '1000':
                filter_text = "⚠️ <strong>FILTER REQUIRED:</strong> Only if 09:00 hit 1R MFE"
            elif orb_code == '2300':
                filter_text = "⚠️ <strong>FILTER REQUIRED:</strong> Skip if ORB > 0.155×ATR"
            elif orb_code == '0030':
                filter_text = "⚠️ <strong>FILTER REQUIRED:</strong> Only if Pre-NY travel > 167 ticks"
            else:
                filter_text = "✅ <strong>NO FILTER:</strong> Baseline strategy"

            st.markdown(f"""
            <div style="border: 2px solid {border_color}; border-radius: 8px; padding: 15px; margin: 10px 0; background: #fafafa;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h3 style="margin: 0; color: {border_color};">{orb['time']} ORB - {orb['session']} Session</h3>
                        <p style="font-size: 1.1em; margin: 5px 0;"><strong>⏰ Starts in: {time_until_str}</strong></p>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.2em; font-weight: bold;">{quality}</div>
                        <div style="font-size: 0.9em; color: #666;">Quality</div>
                    </div>
                </div>
                <div style="display: flex; gap: 30px; margin: 10px 0; padding: 10px; background: white; border-radius: 5px;">
                    <div><strong>Win Rate:</strong> <span style="font-size: 1.2em; color: {border_color};">{win_rate*100:.1f}%</span></div>
                    <div><strong>Expectancy:</strong> <span style="font-size: 1.2em; color: {border_color};">{expectancy:+.3f}R</span></div>
                    <div><strong>Trades:</strong> {result.get('trades', 0)}</div>
                </div>
                <div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 3px;">
                    {filter_text}
                </div>
                <div style="margin-top: 10px; font-size: 0.95em; color: #555;">
                    <strong>📋 Quick Prep:</strong> {get_prep_checklist(orb_code)}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # COMPLETED ORBs
    if completed_orbs:
        st.markdown("---")
        with st.expander(f"✅ COMPLETED TODAY ({len(completed_orbs)} ORBs)", expanded=False):
            for orb in completed_orbs:
                orb_code = orb['time'].replace(':', '')
                result = orb_results.get(orb_code, {})
                st.markdown(f"**{orb['time']} ({orb['session']}):** {result.get('win_rate', 0)*100:.1f}% WR | {result.get('expectancy', 0):+.3f}R")

    # VISUAL PERFORMANCE OVERVIEW
    st.markdown("---")
    st.markdown("### 📊 Performance Overview - All ORBs")

    render_performance_charts(orb_results)

def render_performance_charts(orb_results: Dict):
    """Render visual performance charts"""

    # Prepare data
    orb_times = ['0030', '0900', '1000', '1100', '1800', '2300']
    orb_labels = ['00:30\nNY', '09:00\nAsia', '10:00\nAsia', '11:00\nAsia', '18:00\nLondon', '23:00\nNY']
    win_rates = [orb_results.get(orb, {}).get('win_rate', 0) * 100 for orb in orb_times]
    expectancies = [orb_results.get(orb, {}).get('expectancy', 0) for orb in orb_times]
    trades = [orb_results.get(orb, {}).get('trades', 0) for orb in orb_times]

    # Create two columns for charts
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Win Rate by ORB")
        fig, ax = plt.subplots(figsize=(8, 5))

        # Color bars based on win rate
        colors = ['#4caf50' if wr >= 60 else '#ff9800' if wr >= 55 else '#f44336' for wr in win_rates]

        bars = ax.bar(orb_labels, win_rates, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        # Add value labels on bars
        for i, (bar, wr) in enumerate(zip(bars, win_rates)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{wr:.1f}%',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.axhline(50, color='red', linestyle='--', alpha=0.5, linewidth=2, label='50% baseline')
        ax.set_ylabel("Win Rate (%)", fontsize=12, fontweight='bold')
        ax.set_xlabel("ORB Time & Session", fontsize=12, fontweight='bold')
        ax.set_ylim(0, max(win_rates) + 10)
        ax.legend()
        ax.grid(alpha=0.3, axis='y')
        plt.tight_layout()
        st.pyplot(fig)

    with col2:
        st.markdown("#### Expectancy by ORB")
        fig, ax = plt.subplots(figsize=(8, 5))

        # Color bars based on expectancy
        colors = ['#4caf50' if e > 0.35 else '#ff9800' if e > 0.25 else '#2196f3' for e in expectancies]

        bars = ax.bar(orb_labels, expectancies, color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)

        # Add value labels on bars
        for i, (bar, exp) in enumerate(zip(bars, expectancies)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                   f'{exp:+.3f}R',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')

        ax.axhline(0, color='red', linestyle='--', alpha=0.5, linewidth=2)
        ax.set_ylabel("Expectancy (R)", fontsize=12, fontweight='bold')
        ax.set_xlabel("ORB Time & Session", fontsize=12, fontweight='bold')
        ax.set_ylim(min(expectancies) - 0.1, max(expectancies) + 0.1)
        ax.grid(alpha=0.3, axis='y')
        plt.tight_layout()
        st.pyplot(fig)

    # Session comparison
    st.markdown("---")
    st.markdown("#### Session Performance Comparison")

    col1, col2, col3 = st.columns(3)

    # Calculate session aggregates
    asia_orbs = ['0900', '1000', '1100']
    london_orbs = ['1800']
    ny_orbs = ['2300', '0030']

    def calc_session_stats(orb_list):
        total_trades = sum(orb_results.get(orb, {}).get('trades', 0) for orb in orb_list)
        total_wins = sum(orb_results.get(orb, {}).get('wins', 0) for orb in orb_list)
        total_losses = sum(orb_results.get(orb, {}).get('losses', 0) for orb in orb_list)
        win_rate = total_wins / (total_wins + total_losses) if (total_wins + total_losses) > 0 else 0
        weighted_expectancy = sum(
            orb_results.get(orb, {}).get('expectancy', 0) * orb_results.get(orb, {}).get('trades', 0)
            for orb in orb_list
        ) / total_trades if total_trades > 0 else 0
        return total_trades, win_rate, weighted_expectancy

    asia_trades, asia_wr, asia_exp = calc_session_stats(asia_orbs)
    london_trades, london_wr, london_exp = calc_session_stats(london_orbs)
    ny_trades, ny_wr, ny_exp = calc_session_stats(ny_orbs)

    with col1:
        st.markdown("""
        <div style="background: #e3f2fd; border: 2px solid #2196f3; border-radius: 8px; padding: 15px; text-align: center;">
            <h3 style="color: #1565c0; margin: 0;">🌏 ASIA</h3>
            <p style="font-size: 1.5em; margin: 10px 0; font-weight: bold;">{:.1f}%</p>
            <p style="margin: 5px 0;"><strong>Expectancy:</strong> {:+.3f}R</p>
            <p style="margin: 5px 0; color: #666;"><strong>ORBs:</strong> 09:00, 10:00, 11:00</p>
            <p style="margin: 5px 0; font-size: 0.9em;">{} trades</p>
        </div>
        """.format(asia_wr * 100, asia_exp, asia_trades), unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="background: #e8f5e9; border: 2px solid #4caf50; border-radius: 8px; padding: 15px; text-align: center;">
            <h3 style="color: #2e7d32; margin: 0;">🌍 LONDON</h3>
            <p style="font-size: 1.5em; margin: 10px 0; font-weight: bold;">{:.1f}%</p>
            <p style="margin: 5px 0;"><strong>Expectancy:</strong> {:+.3f}R</p>
            <p style="margin: 5px 0; color: #666;"><strong>ORB:</strong> 18:00</p>
            <p style="margin: 5px 0; font-size: 0.9em;">{} trades</p>
        </div>
        """.format(london_wr * 100, london_exp, london_trades), unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div style="background: #fff3e0; border: 2px solid #ff9800; border-radius: 8px; padding: 15px; text-align: center;">
            <h3 style="color: #e65100; margin: 0;">🌎 NY</h3>
            <p style="font-size: 1.5em; margin: 10px 0; font-weight: bold;">{:.1f}%</p>
            <p style="margin: 5px 0;"><strong>Expectancy:</strong> {:+.3f}R</p>
            <p style="margin: 5px 0; color: #666;"><strong>ORBs:</strong> 23:00, 00:30</p>
            <p style="margin: 5px 0; font-size: 0.9em;">{} trades</p>
        </div>
        """.format(ny_wr * 100, ny_exp, ny_trades), unsafe_allow_html=True)

    # Timeline diagram
    st.markdown("---")
    st.markdown("#### 24-Hour Trading Timeline")

    fig, ax = plt.subplots(figsize=(14, 3))

    # Draw timeline
    ax.axhline(0.5, color='gray', linewidth=2, alpha=0.3)

    # ORB markers
    orb_positions = [0.5, 9, 10, 11, 18, 23]
    orb_names = ['00:30', '09:00', '10:00', '11:00', '18:00', '23:00']
    orb_sessions = ['NY', 'Asia', 'Asia', 'Asia', 'London', 'NY']
    orb_colors = ['#ff9800', '#2196f3', '#2196f3', '#2196f3', '#4caf50', '#ff9800']

    for pos, name, session, color, orb_code in zip(orb_positions, orb_names, orb_sessions, orb_colors, orb_times):
        result = orb_results.get(orb_code, {})
        expectancy = result.get('expectancy', 0)

        # Draw marker
        ax.scatter(pos, 0.5, s=800, c=color, alpha=0.7, edgecolors='black', linewidths=2, zorder=3)

        # Add label
        ax.text(pos, 0.5, name, ha='center', va='center', fontsize=11, fontweight='bold', color='white', zorder=4)

        # Add session label below
        ax.text(pos, 0.3, session, ha='center', va='top', fontsize=9, color=color, fontweight='bold')

        # Add expectancy above
        ax.text(pos, 0.7, f'{expectancy:+.3f}R', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Session backgrounds
    ax.axvspan(0, 8, alpha=0.1, color='orange', label='NY Session')
    ax.axvspan(8, 17, alpha=0.1, color='blue', label='Asia Session')
    ax.axvspan(17, 23, alpha=0.1, color='green', label='London/NY')
    ax.axvspan(23, 24, alpha=0.1, color='orange')

    ax.set_xlim(-0.5, 24)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Hour (Brisbane Time)", fontsize=12, fontweight='bold')
    ax.set_xticks(range(0, 25, 3))
    ax.set_yticks([])
    ax.legend(loc='upper left', fontsize=10)
    ax.set_title("ORB Times with Expectancy (R) - Color = Session", fontsize=13, fontweight='bold')
    plt.tight_layout()
    st.pyplot(fig)

    # Filter requirements summary
    st.markdown("---")
    st.markdown("#### 🎯 Filter Requirements Quick Reference")

    filter_data = [
        {'ORB': '09:00', 'Filter': '✅ None', 'Quality': '🟡 GOOD', 'Notes': 'Baseline optimal'},
        {'ORB': '10:00', 'Filter': '⚠️ Required', 'Quality': '🟢 HIGH (if filtered)', 'Notes': 'Only if 09:00 hit 1R MFE'},
        {'ORB': '11:00', 'Filter': '✅ None', 'Quality': '🟢 BEST', 'Notes': 'Highest expectancy'},
        {'ORB': '18:00', 'Filter': '✅ None', 'Quality': '🟢 EXCELLENT', 'Notes': 'Strongest edge'},
        {'ORB': '23:00', 'Filter': '⚠️ Required', 'Quality': '🟡 GOOD (if filtered)', 'Notes': 'Skip if ORB > 0.155×ATR'},
        {'ORB': '00:30', 'Filter': '⚠️ Required', 'Quality': '🟡 SELECTIVE', 'Notes': 'Only if Pre-NY > 167 ticks'}
    ]

    df_filters = pd.DataFrame(filter_data)
    st.dataframe(df_filters, use_container_width=True, hide_index=True)

def get_strategy_recommendation(orb_code: str) -> str:
    """Get detailed strategy recommendation for an ORB with EXACT execution instructions"""
    from validated_strategies import VALIDATED_MGC_STRATEGIES, CORRELATION_STRATEGIES

    # Get strategy data
    strategy = VALIDATED_MGC_STRATEGIES.get(orb_code, {})
    if not strategy:
        return "<p>No strategy data available</p>"

    # Build execution instructions
    sl_mode = strategy.get('sl_mode', 'FULL')
    rr = strategy.get('rr', 1.0)
    win_rate = strategy.get('win_rate', 0) * 100
    expectancy = strategy.get('expectancy', 0)
    trades = strategy.get('trades', 0)

    # Example calculation
    example_orb = "Example: ORB 4615-4621 (6 ticks)"
    if sl_mode == 'HALF':
        example_entry = "Entry: 4622 (long, first close above)"
        example_stop = "Stop: 4618 (midpoint)"
        example_target = f"Target: 4625 ({rr}R = {rr} × 3 ticks)"
        example_r = "1R = 4 ticks (entry to stop)"
    else:  # FULL
        example_entry = "Entry: 4622 (long, first close above)"
        example_stop = "Stop: 4615 (opposite edge)"
        example_target = f"Target: {4622 + int(rr * 6)} ({rr}R = {rr} × 6 ticks)"
        example_r = "1R = 7 ticks (entry to stop)"

    # Get correlation strategies for this ORB
    correlations = [c for c in CORRELATION_STRATEGIES if c.get('base_session') == orb_code]
    correlation_html = ""
    if correlations:
        correlation_html = "<br/><strong>🔥 CORRELATION EDGES (Enhanced Setups):</strong><br/>"
        for corr in correlations:
            tier_badge = "🌟 S-TIER" if corr['tier'] == 'S' else "⭐ A-TIER"
            correlation_html += f"""
            • <strong>{corr['name']}:</strong> {corr['win_rate']*100:.1f}% WR, {corr['expectancy']:+.2f}R ({corr['trades']} trades) {tier_badge}<br/>
            &nbsp;&nbsp;→ {corr['description']}<br/>
            """

    strategy_html = f"""
        <div style="background: #e3f2fd; border-left: 4px solid #2196f3; padding: 15px; margin: 10px 0; border-radius: 5px;">
            <h4 style="margin-top: 0; color: #1976d2;">📋 HOW TO TRADE THIS ORB</h4>

            <div style="background: white; padding: 12px; border-radius: 5px; margin: 10px 0;">
                <strong>⏱️ ENTRY:</strong> {strategy.get('entry', 'Wait for close outside ORB')}<br/>
                <strong>🛡️ STOP LOSS:</strong> {strategy.get('stop', 'N/A')} ({sl_mode} SL mode)<br/>
                <strong>🎯 TARGET:</strong> {strategy.get('target', 'N/A')} ({rr}R)<br/>
                <strong>💰 RISK:</strong> 0.10-0.25% of account per trade
            </div>

            <div style="background: #fff3cd; padding: 12px; border-radius: 5px; margin: 10px 0; border-left: 3px solid #ffc107;">
                <strong>📊 EXAMPLE CALCULATION:</strong><br/>
                {example_orb}<br/>
                {example_entry}<br/>
                {example_stop}<br/>
                {example_target}<br/>
                {example_r}
            </div>

            <div style="margin-top: 10px;">
                <strong>📈 Performance:</strong> {win_rate:.1f}% WR | {expectancy:+.3f}R expectancy | {trades} trades
                {correlation_html}
            </div>

            <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                <strong>💡 Notes:</strong> {strategy.get('notes', 'No additional notes')}
            </div>
        </div>
    """

    # Special filters or warnings
    filter_msg = ""
    if orb_code == '1000':
        filter_msg = "<div style='background: #fff3cd; padding: 10px; margin-top: 10px; border-left: 3px solid #ff9800; border-radius: 3px;'>⚠️ <strong>MAX ORB SIZE:</strong> Skip if ORB > 10pts (100 ticks)</div>"
    elif orb_code == '2300':
        filter_msg = "<div style='background: #e8f5e9; padding: 10px; margin-top: 10px; border-left: 3px solid #4caf50; border-radius: 3px;'>✅ <strong>NO FILTER:</strong> Trade baseline. Check for cascade setup first (Priority 1).</div>"
    elif orb_code == '0030':
        filter_msg = "<div style='background: #e8f5e9; padding: 10px; margin-top: 10px; border-left: 3px solid #4caf50; border-radius: 3px;'>✅ <strong>NO FILTER:</strong> Trade baseline. Don't trade if 23:00 ORB already active.</div>"
    elif orb_code in ['0900', '1100', '1800']:
        filter_msg = "<div style='background: #e8f5e9; padding: 10px; margin-top: 10px; border-left: 3px solid #4caf50; border-radius: 3px;'>✅ <strong>NO FILTER:</strong> Baseline strategy is optimal. Trade all breakouts.</div>"

    return strategy_html + filter_msg

def get_simple_strategy(orb_code: str) -> str:
    """Get simple one-line strategy"""
    from validated_strategies import VALIDATED_MGC_STRATEGIES
    strategy = VALIDATED_MGC_STRATEGIES.get(orb_code, {})
    if not strategy:
        return "Standard strategy"

    sl_mode = strategy.get('sl_mode', 'FULL')
    rr = strategy.get('rr', 1.0)
    return f"{strategy.get('notes', '')} | {sl_mode} SL, {rr}R target"

def get_prep_checklist(orb_code: str) -> str:
    """Get preparation checklist for upcoming ORB"""
    checklists = {
        '0900': "Set alarm for 08:55. Asia session start - High win rate (63.3%). FULL SL mode.",
        '1000': "Check 09:00 outcome. Look for 09:00 WIN for correlation edge. Max 10pt ORB. FULL SL, 3R target.",
        '1100': "Review 09:00 and 10:00 momentum. Best Asia ORB - highest priority trade. FULL SL mode.",
        '1800': "BEST DAY ORB - London open. Review Asia session. FULL SL, 2R target.",
        '2300': "NIGHT ORB - Check for cascade setup FIRST (Priority 1). If no cascade, trade ORB. HALF SL mode.",
        '0030': "NY ORB - Don't trade if 23:00 ORB active. HALF SL mode."
    }
    return checklists.get(orb_code, "Prepare chart and review strategy")

# ============================================================================
# UI HELPERS
# ============================================================================

def render_metric_card(label: str, value: Any, delta: Optional[str] = None, help_text: Optional[str] = None):
    """Render a metric card with optional delta and help"""
    col = st.columns(1)[0]
    col.metric(label=label, value=value, delta=delta, help=help_text)

def render_edge_card(edge: Dict, index: int):
    """Render an edge discovery card with explanation"""
    setup = edge['setup']
    
    # Add explanation based on setup pattern
    explanation = ""
    if "after" in setup.lower():
        # Correlation pattern
        parts = setup.split(" after ")
        current = parts[0]
        previous = parts[1] if len(parts) > 1 else ""
        explanation = f"<div style='color: #666; font-size: 0.9em; margin-top: 8px;'><strong>Meaning:</strong> When {previous}, then {current} has better odds. This is a <em>momentum continuation pattern</em>.</div>"
    elif "UP" in setup or "DOWN" in setup:
        # Directional pattern
        direction = "UP" if "UP" in setup else "DOWN"
        explanation = f"<div style='color: #666; font-size: 0.9em; margin-top: 8px;'><strong>Meaning:</strong> Price breaks {direction.lower()} (above/below ORB). <em>UP = bullish breakout, DOWN = bearish breakout</em>.</div>"
    
    st.markdown(f"""
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 8px 0; background: #f9f9f9;">
        <h4 style="margin: 0 0 8px 0;">#{index + 1} - {setup}</h4>
        <div style="display: flex; gap: 24px; flex-wrap: wrap;">
            <div><strong>Win Rate:</strong> {edge.get('win_rate', 0):.1%}</div>
            <div><strong>Avg R:</strong> {edge.get('avg_r', 0):+.2f}</div>
            <div><strong>Total R:</strong> {edge.get('total_r', 0):+.0f}</div>
            <div><strong>Trades:</strong> {edge.get('total_trades', 0)}</div>
            <div><strong>Type:</strong> <span style="background: #007bff; color: white; padding: 2px 8px; border-radius: 4px;">{edge['type']}</span></div>
        </div>
        {explanation}
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Initialize session state with trading memory
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'discovered_edges' not in st.session_state:
        st.session_state.discovered_edges = None
    if 'active_trades' not in st.session_state:
        st.session_state.active_trades = []  # Track current trades
    if 'today_orbs' not in st.session_state:
        st.session_state.today_orbs = {}  # Store ORB ranges discussed today

    # Load metadata
    metadata = load_metadata()
    min_date = pd.to_datetime(metadata.get("min_date")).date() if metadata.get("min_date") else None
    max_date = pd.to_datetime(metadata.get("max_date")).date() if metadata.get("max_date") else None

    # Data summary for AI
    data_summary = {
        'total_days': metadata.get('total_days', 0),
        'date_range': f"{min_date} to {max_date}" if min_date and max_date else "N/A",
        'total_orbs': metadata.get('total_days', 0) * 6
    }

    # Sidebar - Symbol Selector and AI Chat
    with st.sidebar:
        st.markdown("### 📊 Live Market Data")

        # Symbol selector
        symbol = st.selectbox(
            "Instrument",
            options=['MGC', 'NQ'],
            index=0,
            help="MGC = Micro Gold, NQ = Nasdaq E-mini"
        )
        symbol_name = "Micro Gold" if symbol == "MGC" else "Nasdaq E-mini"

        # Live price input
        col1, col2 = st.columns([2, 1])
        with col1:
            current_price = st.number_input(
                f"{symbol} Current Price",
                value=0.0,
                step=0.1 if symbol == "MGC" else 0.25,
                format="%.2f",
                key="current_price"
            )
        with col2:
            if st.button("📡 Update", use_container_width=True):
                st.session_state.last_price_update = datetime.now()

        if current_price > 0:
            st.success(f"✓ Live: {current_price}")
            if 'last_price_update' in st.session_state:
                st.caption(f"Updated: {st.session_state.last_price_update.strftime('%H:%M:%S')}")

        st.markdown("---")

        st.markdown("### 🤖 LIVE Trading Assistant")

        ai = get_ai_assistant()

        if ai.is_available():
            st.success("✓ Ready to calculate stops/targets")

            st.markdown("""
            **Quick Commands:**
            - "MGC 10:00 ORB 4615-4621 long"
            - "NQ short 25595-25607"
            - "What's my stop for MGC?"
            - "Did the filter pass?"
            """)

            # Chat interface
            user_input = st.text_area(
                "Ask about your trade:",
                placeholder="e.g., MGC 10:00 ORB is 4615-4621, going long. What's my stop and target?",
                height=120,
                key="ai_input"
            )

            col1, col2 = st.columns(2)
            if col1.button("💬 Calculate", use_container_width=True, type="primary"):
                if user_input.strip():
                    with st.spinner("🤔 Calculating..."):
                        response = ai.chat(user_input, st.session_state.chat_history, data_summary, current_price, symbol)
                        st.session_state.chat_history.append({"role": "user", "content": user_input})
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
                        st.rerun()

            if col2.button("🗑️ Clear", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()

            # Display chat history
            if st.session_state.chat_history:
                st.markdown("---")
                st.markdown("**Your Trading Assistant:**")
                for msg in st.session_state.chat_history[-8:]:  # Show last 4 exchanges
                    if msg["role"] == "user":
                        st.markdown(f"**🙋 You:** {msg['content']}")
                    else:
                        st.markdown(f"**🤖 AI:** {msg['content']}")
        else:
            st.error("❌ AI assistant unavailable")
            st.caption("Set ANTHROPIC_API_KEY in .env to enable AI chat")
            st.info("Without AI, you can still calculate manually:\n- MGC: Stop = ORB midpoint\n- NQ: Stop = opposite ORB edge")

        st.markdown("---")

        # Quick stats
        st.markdown("### 📈 Data Summary")
        st.metric("Total Days", data_summary['total_days'])
        st.metric("Total ORBs", data_summary['total_orbs'])
        st.caption(f"**Range:** {data_summary['date_range']}")

    # Header (after symbol is defined)
    st.title(f"📊 {symbol} ORB Trading Hub")
    st.markdown(f"**{symbol_name} - Zero-Lookahead Edge Discovery & Strategy Optimization**")
    st.markdown("---")

    # TIME-AWARE DASHBOARD (TOP OF PAGE)
    orb_results = load_filtered_backtest_results(symbol)
    render_time_aware_dashboard(orb_results)

    st.markdown("---")
    st.markdown("---")

    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏆 ALL STRATEGIES",
        "🔍 Edge Discovery",
        "⚙️ Strategy Builder",
        "📊 Backtest Results",
        "🎯 Filtered Results (All 6 ORBs)",
        "🛡️ Conservative Execution",
        "📚 Documentation"
    ])

    # ========================================================================
    # TAB 1: ALL STRATEGIES (NEW)
    # ========================================================================
    with tab1:
        st.header("🏆 Complete Strategy Inventory - Ranked by Performance")
        st.markdown("**All validated, professional-grade strategies with zero-lookahead methodology**")

        # Tier badges
        st.markdown("""
        <div style="display: flex; gap: 15px; margin: 20px 0; padding: 15px; background: #f5f5f5; border-radius: 8px;">
            <span style="padding: 5px 12px; background: #ffd700; border-radius: 5px; font-weight: bold;">S+ TIER</span>
            <span style="padding: 5px 12px; background: #c0c0c0; border-radius: 5px; font-weight: bold;">S TIER</span>
            <span style="padding: 5px 12px; background: #cd7f32; border-radius: 5px; font-weight: bold;">A TIER</span>
            <span style="padding: 5px 12px; background: #e8e8e8; border-radius: 5px; font-weight: bold;">B TIER</span>
        </div>
        """, unsafe_allow_html=True)

        # PRIMARY STRATEGIES
        st.markdown("### 🎯 PRIMARY STRATEGIES (Always Check First)")

        primary_data = []
        for strategy in TOP_STRATEGIES[:2]:  # First 2 are primary
            primary_data.append({
                'Tier': strategy['tier'],
                'Strategy': strategy['name'],
                'Expectancy': f"{strategy['expectancy']:+.2f}R",
                'Win Rate': f"{strategy['win_rate']*100:.1f}%",
                'Frequency': strategy['frequency'],
                'Trades': strategy['trades'],
                'Risk': strategy['risk']
            })

        df_primary = pd.DataFrame(primary_data)
        st.dataframe(df_primary, use_container_width=True, hide_index=True)

        with st.expander("📋 PRIMARY STRATEGY DETAILS", expanded=False):
            for strategy in TOP_STRATEGIES[:2]:
                st.markdown(f"""
                **{strategy['name']}** ({strategy['tier']} Tier)
                - **Expectancy:** {strategy['expectancy']:+.2f}R | **Win Rate:** {strategy['win_rate']*100:.1f}%
                - **Frequency:** {strategy['frequency']}
                - **Entry:** {strategy['entry']}
                - **Filters:** {strategy['filters']}
                - **Description:** {strategy['description']}
                """)
                st.markdown("---")

        # ORB STRATEGIES
        st.markdown("### 📊 ORB STRATEGIES (All 6 Sessions)")

        orb_data = []
        for orb_code, strategy in VALIDATED_MGC_STRATEGIES.items():
            if strategy['tradeable']:
                tier = 'A' if strategy['expectancy'] >= 0.3 else 'B'
                orb_data.append({
                    'Tier': tier,
                    'ORB': orb_code,
                    'Session': f"{orb_code[:2]}:{orb_code[2:]}",
                    'Expectancy': f"{strategy['expectancy']:+.3f}R",
                    'Win Rate': f"{strategy['win_rate']*100:.1f}%",
                    'Trades': strategy['trades'],
                    'SL Mode': strategy['sl_mode'],
                    'Target': f"{strategy['rr']}R",
                    'Notes': strategy['notes'][:50] + "..."
                })

        # Sort by expectancy
        df_orbs = pd.DataFrame(orb_data).sort_values('Expectancy', ascending=False)
        st.dataframe(df_orbs, use_container_width=True, hide_index=True)

        # Execution details for each ORB
        st.markdown("### 📋 EXECUTION DETAILS - How to Trade Each ORB")

        for orb_code in ['1800', '1100', '1000', '2300', '0900', '0030']:  # Sorted by expectancy
            strategy = VALIDATED_MGC_STRATEGIES.get(orb_code)
            if strategy and strategy['tradeable']:
                tier = 'A' if strategy['expectancy'] >= 0.3 else 'B'
                tier_color = '#4caf50' if tier == 'A' else '#2196f3'

                with st.expander(f"{orb_code[:2]}:{orb_code[2:]} ORB - {strategy['expectancy']:+.3f}R ({tier} Tier)", expanded=False):
                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.markdown(f"""
                        **📈 Performance:**
                        - Expectancy: **{strategy['expectancy']:+.3f}R**
                        - Win Rate: **{strategy['win_rate']*100:.1f}%**
                        - Sample: {strategy['trades']} trades

                        **⚙️ Configuration:**
                        - Stop Loss: **{strategy['sl_mode']}** mode
                        - Target: **{strategy['rr']}R**
                        - Risk: 0.10-0.25% per trade
                        """)

                    with col2:
                        st.markdown(f"""
                        **📋 Execution:**
                        - **Entry:** {strategy['entry']}
                        - **Stop:** {strategy['stop']}
                        - **Target:** {strategy['target']}

                        **💡 Notes:**
                        {strategy['notes']}
                        """)

                    # Example calculation
                    st.markdown("**📊 Example Calculation:**")
                    if strategy['sl_mode'] == 'HALF':
                        st.code("""
ORB: 4615-4621 (6 ticks)
LONG: Entry 4622, Stop 4618 (midpoint), Target 4625 (1R = 3 ticks × 1)
SHORT: Entry 4614, Stop 4618 (midpoint), Target 4611 (1R = 4 ticks × 1)
                        """, language="text")
                    else:
                        st.code(f"""
ORB: 4615-4621 (6 ticks)
LONG: Entry 4622, Stop 4615 (opposite), Target {4622 + int(strategy['rr'] * 7)} ({strategy['rr']}R = 7 ticks × {strategy['rr']})
SHORT: Entry 4614, Stop 4621 (opposite), Target {4614 - int(strategy['rr'] * 7)} ({strategy['rr']}R = 7 ticks × {strategy['rr']})
                        """, language="text")

        # CORRELATION STRATEGIES
        st.markdown("### 🔥 CORRELATION STRATEGIES (Session-Dependent Edges)")

        corr_data = []
        for corr in CORRELATION_STRATEGIES:
            corr_data.append({
                'Tier': corr['tier'],
                'Strategy': corr['name'],
                'Expectancy': f"{corr['expectancy']:+.2f}R",
                'Win Rate': f"{corr['win_rate']*100:.1f}%",
                'Trades': corr['trades'],
                'Filter': corr['filter'],
                'Description': corr['description']
            })

        df_corr = pd.DataFrame(corr_data)
        st.dataframe(df_corr, use_container_width=True, hide_index=True)

        # Summary stats
        st.markdown("---")
        st.markdown("### 📊 Portfolio Summary")

        col1, col2, col3, col4 = st.columns(4)

        total_strategies = len(TOP_STRATEGIES) + len(CORRELATION_STRATEGIES)
        avg_expectancy = sum(s['expectancy'] for s in TOP_STRATEGIES) / len(TOP_STRATEGIES)
        best_strategy = max(TOP_STRATEGIES, key=lambda x: x['expectancy'])

        col1.metric("Total Strategies", total_strategies)
        col2.metric("Best Expectancy", f"{best_strategy['expectancy']:+.2f}R")
        col3.metric("Avg Expectancy", f"{avg_expectancy:+.2f}R")
        col4.metric("Data Coverage", "741 days")

        st.info("💡 **Trading Priority:** Always check Cascades first → Night ORBs second → Day ORBs third → Correlations as filters")

    # ========================================================================
    # TAB 2: EDGE DISCOVERY
    # ========================================================================
    with tab2:
        st.header("Edge Discovery")
        st.markdown("Discover profitable trading edges using zero-lookahead analysis")
        
        with st.expander("📖 Understanding the Terminology", expanded=False):
            st.markdown("""
            **UP/DOWN** = Break direction (which way price broke out of the ORB)
            - **UP** = Price broke above the ORB high (bullish)
            - **DOWN** = Price broke below the ORB low (bearish)
            
            **WIN/LOSS** = Trade outcome (did the trade make money?)
            - **WIN** = Hit profit target before stop loss
            - **LOSS** = Hit stop loss before profit target
            
            **Example: "10:00 UP after 09:00 WIN"**
            - At 10:00, price broke UP (above 10:00 ORB high)
            - AND the previous 09:00 ORB trade was a WIN
            - This pattern wins 57.9% of the time (vs 55.5% baseline)
            - It's a **momentum continuation** pattern
            
            **How to Use:**
            1. Watch for 09:00 ORB to complete and record if it WINS or LOSES
            2. At 10:00, if 09:00 was a WIN and price breaks UP → Higher confidence trade
            3. Use correlations to filter and size positions
            
            See **TERMINOLOGY_EXPLAINED.md** for full details.
            """)

        col1, col2 = st.columns([3, 1])

        with col2:
            if st.button("🔬 Run Analysis", use_container_width=True, type="primary"):
                with st.spinner("Analyzing 40+ edge configurations..."):
                    st.session_state.discovered_edges = discover_edges()
                st.success("✓ Analysis complete!")
                st.rerun()

        if st.session_state.discovered_edges is None:
            st.info("👆 Click 'Run Analysis' to discover edges")

            # Show quick summary
            st.markdown("### What Gets Analyzed:")
            st.markdown("""
            - **Baseline edges** - All ORBs (09:00, 10:00, 11:00, 18:00, 23:00, 00:30) × directions
            - **PRE block edges** - Filtered by PRE_ASIA, PRE_LONDON, PRE_NY ranges
            - **ORB correlation edges** - Sequential dependencies (e.g., 10:00 after 09:00 WIN)
            - **Quality scoring** - Win Rate × Avg R for ranking
            """)

        else:
            edges = st.session_state.discovered_edges['all_edges']

            # Filters
            st.markdown("### Filter Results")
            col1, col2, col3, col4 = st.columns(4)

            min_wr = col1.slider("Min Win Rate", 0.0, 1.0, 0.50, 0.01)
            min_avg_r = col2.slider("Min Avg R", -1.0, 1.0, 0.0, 0.01)
            min_trades = col3.slider("Min Trades", 0, 200, 20, 10)
            edge_type = col4.multiselect(
                "Edge Type",
                options=['baseline', 'pre_block', 'correlation'],
                default=['baseline', 'pre_block', 'correlation']
            )

            # Filter edges
            filtered = [
                e for e in edges
                if e.get('win_rate', 0) >= min_wr
                and e.get('avg_r', 0) >= min_avg_r
                and e.get('total_trades', 0) >= min_trades
                and e['type'] in edge_type
            ]

            st.markdown(f"### Top Edges ({len(filtered)} found)")

            if len(filtered) == 0:
                st.warning("No edges match your filters. Try relaxing the criteria.")
            else:
                # Display top edges
                for i, edge in enumerate(filtered[:10]):  # Show top 10
                    render_edge_card(edge, i)

                # Export
                st.markdown("---")
                if st.button("💾 Export All Results", use_container_width=True):
                    df = pd.DataFrame(filtered)
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"edges_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

    # ========================================================================
    # TAB 3: STRATEGY BUILDER
    # ========================================================================
    with tab3:
        st.header("Strategy Builder")
        st.markdown("Build and test custom ORB strategies")

        # Strategy configuration
        st.markdown("### Strategy Parameters")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Entry Setup**")
            entry_model = st.selectbox(
                "Entry Model",
                options=list(qe.ENTRY_MODELS.keys()),
                format_func=lambda x: qe.ENTRY_MODELS[x]
            )
            confirm_closes = st.number_input("Confirmation Closes", 1, 3, 1)

        with col2:
            st.markdown("**Risk Management**")
            max_stop_ticks = st.number_input("Max Stop (ticks)", 0, 200, 100, 10,
                                            help="0 = no limit")
            rr_target = st.number_input("RR Target", 1.0, 5.0, 2.0, 0.5)

        with col3:
            st.markdown("**Filters**")
            orb_times = st.multiselect(
                "ORB Times",
                options=list(qe.ORB_TIMES),
                default=['1000']
            )
            direction = st.selectbox("Direction", options=['ANY', 'UP', 'DOWN'])

        # Build strategy
        strategy = qe.StrategyConfig(
            level_basis="orb_boundary",
            entry_model=entry_model,
            confirm_closes=confirm_closes,
            retest_required=False,
            retest_rule="touch",
            pierce_ticks=None,
            rejection_tf="1m",
            stop_rule="ORB_opposite_boundary",
            max_stop_ticks=max_stop_ticks if max_stop_ticks > 0 else None,
            cutoff_minutes=None,
            one_trade_per_orb=True
        )

        filters = qe.Filters(
            start_date=str(min_date) if min_date else None,
            end_date=str(max_date) if max_date else None,
            orb_times=tuple(orb_times),
            break_dir=direction,
            outcomes=tuple(qe.OUTCOME_OPTIONS),
            asia_type_code=None,
            include_null_asia=True,
            london_type_code=None,
            include_null_london=True,
            pre_ny_type_code=None,
            include_null_pre_ny=True,
            enable_atr_filter=False,
            atr_min=None,
            atr_max=None,
            enable_asia_range_filter=False,
            asia_range_min=None,
            asia_range_max=None,
        )


        # Generate keys for caching
        filters_key = qe.filters_key(filters)
        strategy_key = qe.strategy_key(strategy)


        # Load results
        if st.button("▶️ Run Backtest", type="primary"):
            with st.spinner("Running backtest..."):
                stats = load_headline_stats(filters_key, strategy_key, filters, strategy)
                funnel = load_funnel(filters_key, strategy_key, filters, strategy)
                equity = load_equity_curve(filters_key, strategy_key, filters, strategy)

            # Display results
            st.markdown("### Results")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Trades", stats.get('total_trades', 0))
            col2.metric("Win Rate", f"{stats.get('win_rate', 0):.1%}")
            col3.metric("Avg R", f"{stats.get('avg_r', 0):+.2f}")
            col4.metric("Total R", f"{stats.get('total_r', 0):+.0f}")

            # Equity curve
            if not equity.empty:
                st.markdown("### Equity Curve")
                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(equity.index, equity['cumulative_r'], linewidth=2)
                ax.set_xlabel("Trade Number")
                ax.set_ylabel("Cumulative R")
                ax.grid(alpha=0.3)
                st.pyplot(fig)

            # Entry funnel
            st.markdown("### Entry Funnel")
            funnel_data = {
                'Stage': list(funnel.keys()),
                'Count': list(funnel.values())
            }
            st.bar_chart(pd.DataFrame(funnel_data).set_index('Stage'))

    # ========================================================================
    # TAB 4: BACKTEST RESULTS
    # ========================================================================
    with tab4:
        st.header("Backtest Results")
        st.markdown("View detailed 1-minute precision backtest results")

        # Load RR comparison
        try:
            from rr_summary import get_rr_summary
            rr_df = get_rr_summary()

            st.markdown("### RR Target Comparison")
            st.dataframe(rr_df, use_container_width=True)

            # Chart
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

            ax1.bar(rr_df['rr'], rr_df['win_rate'])
            ax1.set_xlabel("RR Target")
            ax1.set_ylabel("Win Rate")
            ax1.set_title("Win Rate by RR")

            ax2.bar(rr_df['rr'], rr_df['avg_r'])
            ax2.axhline(0, color='red', linestyle='--', alpha=0.5)
            ax2.set_xlabel("RR Target")
            ax2.set_ylabel("Avg R")
            ax2.set_title("Avg R by RR Target")

            st.pyplot(fig)

        except ImportError:
            st.warning("📊 **RR Summary module not found**")
            st.info("""
            This is optional functionality for comparing different RR targets.

            **To enable:**
            1. Run a grid backtest: `python backtest_orb_exec_1m.py --rr-grid "1.5,2.0,2.5,3.0" --confirm 1`
            2. Or ensure `rr_summary.py` exists in the project root

            **Current status:** App works without this module, but RR comparison charts are unavailable.
            """)
        except Exception as e:
            st.error(f"❌ **Error loading backtest results:** {str(e)}")
            st.info("Run: `python backtest_orb_exec_1m.py --rr-grid \"1.5,2.0,2.5,3.0\" --confirm 1`")

    # ========================================================================
    # TAB 5: FILTERED RESULTS (ALL 6 ORBs)
    # ========================================================================
    with tab5:
        st.header("Filtered Backtest Results - All 6 ORBs")
        st.markdown("**Configuration:** Half SL (ORB midpoint), R:R 1.5, ORB-Anchored TP, 1-minute execution")

        # Load results
        orb_results = load_filtered_backtest_results(symbol)
        session_results = load_session_breakdown()

        # Overall summary
        total_trades = sum(r.get('trades', 0) for r in orb_results.values())
        total_wins = sum(r.get('wins', 0) for r in orb_results.values())
        total_losses = sum(r.get('losses', 0) for r in orb_results.values())
        overall_win_rate = total_wins / (total_wins + total_losses) if (total_wins + total_losses) > 0 else 0
        overall_expectancy = sum(
            r.get('expectancy', 0) * r.get('trades', 0) for r in orb_results.values()
        ) / total_trades if total_trades > 0 else 0
        total_r = overall_expectancy * total_trades

        st.markdown("### Overall Performance")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Trades", f"{total_trades:,}")
        col2.metric("Win Rate", f"{overall_win_rate:.1%}")
        col3.metric("Expectancy", f"{overall_expectancy:+.4f}R")
        col4.metric("Total R", f"{total_r:+.1f}R")
        total_days = data_summary.get('total_days', 1)
        avg_r_per_day = total_r / total_days if total_days > 0 else 0
        col5.metric("Avg R per Day", f"{avg_r_per_day:+.2f}R")

        st.markdown("---")

        # Results by ORB
        st.markdown("### Results by ORB")

        orb_data = []
        for orb_time in ['0900', '1000', '1100', '1800', '2300', '0030']:
            if orb_time in orb_results:
                r = orb_results[orb_time]
                orb_data.append({
                    'ORB': orb_time,
                    'Trades': r['trades'],
                    'Wins': r['wins'],
                    'Losses': r['losses'],
                    'Win Rate': f"{r['win_rate']:.1%}",
                    'Expectancy': f"{r['expectancy']:+.4f}R",
                    'Total R': f"{r['expectancy'] * r['trades']:+.1f}R"
                })

        if orb_data:
            st.dataframe(pd.DataFrame(orb_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Session breakdown
        st.markdown("### Session Breakdown")

        col1, col2, col3 = st.columns(3)

        for idx, (session_name, session_data) in enumerate(session_results.items()):
            col = [col1, col2, col3][idx]
            with col:
                st.markdown(f"**{session_name}**")
                st.metric("Trades", session_data['trades'])
                st.metric("Win Rate", f"{session_data['win_rate']:.1%}")
                st.metric("Expectancy", f"{session_data['expectancy']:+.4f}R")
                st.metric("Total R", f"{session_data['total_r']:+.1f}R")

        st.markdown("---")

        # MAE/MFE Analysis
        st.markdown("### MAE/MFE Distribution by ORB")
        st.markdown("*Maximum Adverse/Favorable Excursion (normalized by ORB-anchored R)*")

        mae_mfe_data = []
        for orb_time in ['0900', '1000', '1100', '1800', '2300', '0030']:
            if orb_time in orb_results:
                r = orb_results[orb_time]
                mae_mfe_data.append({
                    'ORB': orb_time,
                    'MAE P50': f"{r['mae_p50']:.3f}R",
                    'MAE P90': f"{r['mae_p90']:.3f}R",
                    'MFE P50': f"{r['mfe_p50']:.3f}R",
                    'MFE P90': f"{r['mfe_p90']:.3f}R",
                    'MFE/MAE Ratio': f"{r['mfe_p50'] / r['mae_p50']:.2f}" if r['mae_p50'] > 0 else 'N/A'
                })

        if mae_mfe_data:
            st.dataframe(pd.DataFrame(mae_mfe_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Visualizations
        st.markdown("### Expectancy Comparison")

        if orb_results:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

            # Expectancy by ORB
            orb_times = list(orb_results.keys())
            expectancies = [orb_results[o]['expectancy'] for o in orb_times]
            colors = ['green' if e > 0 else 'red' for e in expectancies]

            ax1.bar(orb_times, expectancies, color=colors, alpha=0.7)
            ax1.axhline(0, color='black', linestyle='--', alpha=0.3)
            ax1.set_xlabel("ORB Time")
            ax1.set_ylabel("Expectancy (R)")
            ax1.set_title("Expectancy by ORB")
            ax1.grid(alpha=0.3)

            # Win rate by ORB
            win_rates = [orb_results[o]['win_rate'] * 100 for o in orb_times]
            ax2.bar(orb_times, win_rates, color='steelblue', alpha=0.7)
            ax2.axhline(50, color='red', linestyle='--', alpha=0.5, label='50% baseline')
            ax2.set_xlabel("ORB Time")
            ax2.set_ylabel("Win Rate (%)")
            ax2.set_title("Win Rate by ORB")
            ax2.legend()
            ax2.grid(alpha=0.3)

            plt.tight_layout()
            st.pyplot(fig)

        st.markdown("---")

        # Filter recommendations
        st.markdown("### 🎯 Optimal Filters Applied")
        st.markdown("""
        **Filters are only applied when improvement > 5% to avoid noise fitting:**

        | ORB | Filter | Improvement | Rationale |
        |-----|--------|-------------|-----------|
        | **0030** | Pre-NY travel > 167 ticks | +33.0% | High volatility filter |
        | **1000** | Prior 0900 hit 1R MFE | +13.8% | Momentum continuation |
        | **0900** | NONE | Baseline best | Already optimal |
        | **1100** | NONE | +3.9% too small | Likely noise |
        | **1800** | NONE | Baseline best | Already optimal |
        | **2300** | NONE | +3.6% too small | Likely noise |

        **Key Insight:** Quality over quantity - 14% fewer trades but 10.5% better expectancy
        """)

    # ========================================================================
    # TAB 6: CONSERVATIVE EXECUTION
    # ========================================================================
    with tab6:
        st.header("Conservative Execution Testing")
        st.markdown("**Purpose:** Test if edge is execution-dependent")

        st.markdown("""
        ### Test Parameters
        - **+2 Minute Entry Delay**: Entry 2 minutes after first close outside ORB
        - **Conservative Same-Bar Resolution**: If TP+SL both hit in same bar → LOSS
        - **Purpose**: Verify edge survives realistic execution constraints

        ### Results Summary
        """)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Standard Execution")
            st.metric("Expectancy", "+0.4299R per trade")
            st.metric("Trades", "2682")
            st.metric("Method", "Instant entry, optimistic same-bar")

        with col2:
            st.markdown("#### Conservative Execution")
            st.metric("Expectancy", "+0.3833R per trade", "-10.8%")
            st.metric("Both Hit Rate", "0.1%", "Very rare")
            st.metric("Method", "+2min delay, conservative same-bar")

        st.markdown("---")

        st.markdown("### Interpretation")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("""
            **Edge is ROBUST, not execution-dependent:**

            1. **Minimal Decline**: Only 10.8% expectancy decline under worst-case execution
            2. **Low Both-Hit Rate**: Only 0.1% of trades have TP+SL in same bar
            3. **Still Profitable**: +0.38R per trade is strong even with conservative assumptions
            4. **Real-World Viable**: 2-minute delay simulates realistic order entry time

            **Conclusion**: This is a STRUCTURAL EDGE, not an artifact of execution assumptions.
            The strategy will work with human execution and realistic fills.
            """)

        with col2:
            st.success("✓ **PASSED**\n\nEdge survives realistic execution constraints")

        st.markdown("---")

        # Detailed breakdown
        st.markdown("### Conservative Execution by ORB")

        conservative_data = [
            {'ORB': '0900', 'Standard': '+0.4183R', 'Conservative': '+0.3667R', 'Decline': '-12.3%'},
            {'ORB': '1000', 'Standard': '+0.4079R', 'Conservative': '+0.3621R', 'Decline': '-11.2%'},
            {'ORB': '1100', 'Standard': '+0.4923R', 'Conservative': '+0.4389R', 'Decline': '-10.8%'},
            {'ORB': '1800', 'Standard': '+0.4799R', 'Conservative': '+0.4312R', 'Decline': '-10.1%'},
            {'ORB': '2300', 'Standard': '+0.3964R', 'Conservative': '+0.3501R', 'Decline': '-11.7%'},
            {'ORB': '0030', 'Standard': '+0.3073R', 'Conservative': '+0.2688R', 'Decline': '-12.5%'},
        ]

        st.dataframe(pd.DataFrame(conservative_data), use_container_width=True, hide_index=True)

        st.markdown("""
        **Note:** Decline is consistent across all ORBs (10-12%), indicating systematic execution impact
        rather than execution-dependent edge.
        """)

    # ========================================================================
    # TAB 7: DOCUMENTATION
    # ========================================================================
    with tab7:
        st.header("Documentation")

        st.markdown("""
        ### Quick Start Guide

        #### 1. Edge Discovery
        - Click **"Run Analysis"** in the Edge Discovery tab
        - Review top edges ranked by quality score (Win Rate × Avg R)
        - Filter by minimum win rate, avg R, and sample size
        - Export results to CSV for further analysis

        #### 2. Strategy Builder
        - Configure entry model, confirmation closes, and risk parameters
        - Select ORB times and direction filters
        - Run backtest to see performance metrics
        - View equity curve and entry funnel

        #### 3. AI Assistant
        - Ask questions about your data in the sidebar
        - Get insights on edge discovery results
        - Validate zero-lookahead compliance
        - Design new strategy ideas

        ### Key Principles

        #### Zero-Lookahead Methodology
        **Rule:** If you can't calculate it at the open, you can't use it to trade the open.

        **Valid for decisions:**
        - PRE blocks (PRE_ASIA, PRE_LONDON, PRE_NY)
        - Previous day ORB outcomes
        - Completed session stats

        **INVALID (lookahead bias):**
        - Session type codes for current session
        - Intraday session stats before session close
        - Future ORB outcomes

        #### Honesty Over Accuracy
        - Real win rates: 50-58% (honest, tradeable)
        - Inflated backtests: 57%+ (lookahead bias)
        - Lower but REAL numbers are better

        ### Known Edges

        1. **10:00 UP** - 55.5% WR, +0.11 R (247 trades) - Primary edge
        2. **10:00 UP after 09:00 WIN** - 57.9% WR, +0.16 R (114 trades) - Best correlation
        3. **11:00 UP + PRE_ASIA > 50t** - 55.1% WR, +0.10 R (107 trades)
        4. **11:00 DOWN after 09:00 LOSS + 10:00 WIN** - 57.7% WR, +0.15 R (71 trades)

        ### Latest Analysis Reports

        **Filtered Backtest Results:**
        - **FILTERED_BACKTEST_RESULTS.md** - Complete results for all 6 ORBs with optimal filters
        - **AUDIT_REPORT.md** - Comprehensive audit for lookahead bias
        - **AUDIT_SUMMARY.md** - Quick audit summary
        - **EDGE_VALIDATION_REPORT.md** - Edge validation and robustness analysis

        **Trading Rules & Edge Discovery:**
        - **TRADING_RULESET.md** - Recommended trading rules for each ORB
        - **TERMINOLOGY_EXPLAINED.md** - Understanding UP/DOWN, WIN/LOSS, correlations

        **System Documentation:**
        - **WORKFLOW_GUIDE.md** - Complete end-to-end process
        - **TRADING_PLAYBOOK.md** - Trading rules and setups
        - **DATABASE_SCHEMA.md** - Table documentation
        - **ZERO_LOOKAHEAD_RULES.md** - Temporal rules
        - **ROBUSTNESS_TESTING_README.md** - Conservative execution testing

        ### Key Findings Summary

        **Edge is Real and Robust:**
        1. All 6 ORBs tested across 740 days (2024-01-02 to 2026-01-10)
        2. Overall: +0.4299R expectancy per trade (57.2% win rate)
        3. No lookahead bias detected (comprehensive audit completed)
        4. Edge survives conservative execution (-10.8% decline only)
        5. Filters improve quality over quantity (+10.5% expectancy)

        **Best Performing:**
        - **London (1800)**: +0.48R per trade (strongest)
        - **Asia Session**: +0.44R per trade (1100, 0900, 1000)
        - **NY Session**: +0.37R per trade (weaker but still profitable)

        **Recommended Filters:**
        - **0030**: Only trade if Pre-NY travel > 167 ticks (+33% improvement)
        - **1000**: Only trade if 0900 hit 1R MFE (+13.8% improvement)
        - **Others**: No filter needed (baseline already optimal)

        ### Environment Setup

        To enable AI chat:
        ```bash
        # Add to .env file
        ANTHROPIC_API_KEY=your_key_here
        ```

        Get your API key at: https://console.anthropic.com/
        """)

if __name__ == "__main__":
    main()
