"""
CHATBOT-STYLE UI - Minimal, conversation-focused interface

Shows:
1. Compact status bar (price, current setup)
2. AI chat as primary interface
3. Quick action buttons

No clutter - just chat with your strategies.
"""

import streamlit as st
from datetime import datetime, timedelta
from strategy_engine import ActionType

def render_chatbot_mode(evaluation, current_price, data_loader, ai_assistant, session_state):
    """
    Ultra-simple chatbot-focused UI.

    Layout:
    - Thin status bar at top (price, status, next ORB)
    - Large AI chat interface
    - Quick action buttons
    """

    # ========================================================================
    # COMPACT STATUS BAR (Single line info)
    # ========================================================================

    # Get status
    if evaluation:
        strategy_name = getattr(evaluation, 'strategy_name', 'None')
        action = evaluation.action.value if hasattr(evaluation, 'action') else 'STAND_DOWN'

        # Clean strategy name
        orb_name = strategy_name.replace('_ORB', '') if strategy_name != 'None' else 'No active'

        # Status emoji
        if action == 'ENTER':
            status_emoji = '🟢'
            status_text = f'{orb_name} READY'
        elif action == 'PREPARE':
            status_emoji = '🟡'
            status_text = f'{orb_name} Forming'
        elif action == 'MANAGE':
            status_emoji = '🔵'
            status_text = f'{orb_name} Active Trade'
        else:
            status_emoji = '⏸️'
            status_text = 'Waiting'

            # Find next ORB
            now = datetime.now()
            orb_times = [(9,0,'0900'), (10,0,'1000'), (11,0,'1100'),
                        (18,0,'1800'), (23,0,'2300'), (0,30,'0030')]

            next_orb = None
            min_wait = None

            for h, m, name in orb_times:
                orb_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if h <= 3 and now.hour >= 12:
                    orb_time += timedelta(days=1)
                if orb_time > now:
                    wait = (orb_time - now).total_seconds() / 60
                    if min_wait is None or wait < min_wait:
                        next_orb = name
                        min_wait = wait

            if next_orb:
                hours = int(min_wait // 60)
                mins = int(min_wait % 60)
                if hours > 0:
                    status_text = f'Next: {next_orb} in {hours}h{mins}m'
                else:
                    status_text = f'Next: {next_orb} in {mins}m'
    else:
        status_emoji = '⚪'
        status_text = 'Initializing...'

    # Price display
    price_str = f'${current_price:.2f}' if current_price > 0 else '$--'

    # Single-line status bar with dark theme
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 16px 24px;
        border-radius: 12px;
        margin-bottom: 24px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <span style="font-size: 32px; font-weight: 700; color: #00d9ff;">MGC</span>
                <span style="font-size: 28px; font-weight: 600; color: #fff;">{price_str}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 24px;">{status_emoji}</span>
                <span style="font-size: 18px; color: #e0e0e0;">{status_text}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ========================================================================
    # TRADE SIGNAL (if ready)
    # ========================================================================

    if evaluation and hasattr(evaluation, 'action') and evaluation.action == ActionType.ENTER:
        direction = getattr(evaluation, 'direction', 'UNKNOWN')
        entry = getattr(evaluation, 'entry_price', 0)
        stop = getattr(evaluation, 'stop_price', 0)
        target = getattr(evaluation, 'target_price', 0)

        # Trade signal card
        signal_color = '#00d900' if direction == 'LONG' else '#ff4444'

        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, {signal_color}20 0%, {signal_color}10 100%);
            border: 2px solid {signal_color};
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
        ">
            <div style="font-size: 24px; font-weight: 700; color: {signal_color}; margin-bottom: 12px;">
                {direction} SETUP READY
            </div>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; color: #e0e0e0;">
                <div>
                    <div style="font-size: 12px; color: #888;">Entry</div>
                    <div style="font-size: 20px; font-weight: 600;">${entry:.2f}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #888;">Stop</div>
                    <div style="font-size: 20px; font-weight: 600;">${stop:.2f}</div>
                </div>
                <div>
                    <div style="font-size: 12px; color: #888;">Target</div>
                    <div style="font-size: 20px; font-weight: 600;">${target:.2f}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ========================================================================
    # AI CHAT INTERFACE (MAIN FOCUS)
    # ========================================================================

    st.markdown("### 🤖 Strategy Assistant")

    # Chat history display
    chat_container = st.container()
    with chat_container:
        chat_history = getattr(session_state, 'chat_history', [])
        if not chat_history:
            st.info("👋 Ask me about strategies, setups, or current market conditions!")
        else:
            # Show recent messages (last 10)
            recent_messages = chat_history[-10:]
            for msg in recent_messages:
                if msg['role'] == 'user':
                    st.markdown(f"""
                    <div style="
                        background: #16213e;
                        padding: 12px 16px;
                        border-radius: 12px;
                        margin: 8px 0;
                        margin-left: 20%;
                    ">
                        <div style="font-size: 12px; color: #888; margin-bottom: 4px;">You</div>
                        <div style="color: #e0e0e0;">{msg['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="
                        background: #1a1a2e;
                        padding: 12px 16px;
                        border-radius: 12px;
                        margin: 8px 0;
                        margin-right: 20%;
                        border-left: 3px solid #00d9ff;
                    ">
                        <div style="font-size: 12px; color: #00d9ff; margin-bottom: 4px;">AI</div>
                        <div style="color: #e0e0e0;">{msg['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # Quick action buttons
    st.markdown("**Quick Questions:**")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 Analyze Current Setup", use_container_width=True):
            session_state.pending_question = "Analyze the current ORB setup. Should I take this trade?"

    with col2:
        if st.button("🎯 Best Strategy Now", use_container_width=True):
            session_state.pending_question = "What's the best strategy to use right now based on current conditions?"

    with col3:
        if st.button("⚠️ Risk Assessment", use_container_width=True):
            session_state.pending_question = "What are the main risks with the current setup?"

    # Chat input
    user_input = st.text_area(
        "Your message:",
        key="chatbot_input",
        placeholder="Ask about strategies, current setup, or market conditions...",
        height=80
    )

    col1, col2 = st.columns([3, 1])

    with col1:
        send_clicked = st.button("Send", type="primary", use_container_width=True)

    with col2:
        if st.button("Clear", use_container_width=True):
            session_state.chat_history = []
            st.rerun()

    # Process input (from button or text)
    message_to_send = None

    if send_clicked and user_input.strip():
        message_to_send = user_input
    elif hasattr(session_state, 'pending_question') and session_state.pending_question:
        message_to_send = session_state.pending_question
        session_state.pending_question = None

    if message_to_send:
        with st.spinner("Thinking..."):
            try:
                # Build context
                strategy_state = None
                if evaluation:
                    strategy_state = {
                        'strategy': getattr(evaluation, 'strategy_name', 'None'),
                        'action': evaluation.action.value if hasattr(evaluation, 'action') else 'STAND_DOWN',
                        'entry': getattr(evaluation, 'entry_price', None),
                        'stop': getattr(evaluation, 'stop_price', None),
                        'target': getattr(evaluation, 'target_price', None),
                        'orb_high': getattr(evaluation, 'orb_high', None),
                        'orb_low': getattr(evaluation, 'orb_low', None),
                        'direction': getattr(evaluation, 'direction', None),
                        'reasons': getattr(evaluation, 'reasons', [])
                    }

                # Get AI response
                chat_hist = getattr(session_state, 'chat_history', [])
                sess_id = getattr(session_state, 'session_id', 'chatbot')

                response = ai_assistant.chat(
                    user_message=message_to_send,
                    conversation_history=chat_hist[-6:],  # Last 3 exchanges
                    session_id=sess_id,
                    instrument='MGC',
                    current_price=current_price,
                    strategy_state=strategy_state,
                    session_levels={},
                    orb_data={},
                    backtest_stats={}
                )

                # Update history
                if not hasattr(session_state, 'chat_history'):
                    session_state.chat_history = []

                session_state.chat_history.append({'role': 'user', 'content': message_to_send})
                session_state.chat_history.append({'role': 'assistant', 'content': response})

                # Save to memory
                try:
                    memory_manager = getattr(session_state, 'memory_manager', None)
                    if memory_manager:
                        memory_manager.save_message(
                            session_id=sess_id,
                            role='user',
                            content=message_to_send,
                            instrument='MGC'
                        )
                        memory_manager.save_message(
                            session_id=sess_id,
                            role='assistant',
                            content=response,
                            instrument='MGC'
                        )
                except:
                    pass  # Don't fail on memory save

                st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")

    # ========================================================================
    # MINIMAL SETTINGS (collapsible)
    # ========================================================================

    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

    with st.expander("⚙️ Settings"):
        col1, col2 = st.columns(2)

        with col1:
            current_account_size = getattr(session_state, 'account_size', 10000.0)
            account_size = st.number_input(
                "Account Size ($)",
                value=current_account_size,
                step=1000.0
            )
            session_state.account_size = account_size

        with col2:
            current_auto_refresh = getattr(session_state, 'auto_refresh_enabled', True)
            auto_refresh = st.checkbox(
                "Auto-refresh",
                value=current_auto_refresh
            )
            session_state.auto_refresh_enabled = auto_refresh

        if st.button("🔄 Refresh Data", use_container_width=True):
            if data_loader:
                with st.spinner("Refreshing..."):
                    data_loader.refresh()
                    st.success("Updated!")
                    st.rerun()


def render_chatbot_mode_toggle():
    """Simple toggle for chatbot mode."""

    if not hasattr(st.session_state, 'chatbot_mode'):
        st.session_state.chatbot_mode = True  # Default to chatbot mode

    mode = st.toggle("💬 Chatbot Mode", value=st.session_state.chatbot_mode,
                    help="Minimal chat interface with just price and AI assistant")
    st.session_state.chatbot_mode = mode

    return mode
