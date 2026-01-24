"""
SIMPLE FOCUSED UI - Show only what matters for active ORB

Clean, action-oriented layout:
1. Active ORB status (BIG)
2. Current price vs ORB levels
3. What to do RIGHT NOW
4. AI analysis of current setup
5. Best strategies for this ORB

No clutter, no complexity - just what you need to trade.
"""

import streamlit as st
from datetime import datetime, timedelta

def render_simple_trading_view(evaluation, current_price, orb_data, ai_assistant, session_state):
    """
    Render simplified focused trading view.

    Shows:
    - Active ORB status (big, clear)
    - Price position vs ORB
    - Action recommendation
    - AI analysis
    """

    # ========================================================================
    # SECTION 1: ACTIVE ORB STATUS (BIG AND CLEAR)
    # ========================================================================

    st.markdown("### 🎯 ACTIVE SESSION")

    if evaluation and hasattr(evaluation, 'state') and evaluation.state.value != "INVALID":
        # Get ORB name and state
        orb_name = getattr(evaluation, 'strategy_name', 'Unknown').replace("_ORB", "")
        state = evaluation.state.value if hasattr(evaluation, 'state') else "UNKNOWN"

        # Color coding
        action_value = getattr(evaluation, 'action', None)
        action_value = action_value.value if action_value and hasattr(action_value, 'value') else None

        if state == "READY" or action_value == "ENTER":
            color = "🟢"
            bg_color = "#1a5f1a"  # Dark green
        elif state == "PREPARING":
            color = "🟡"
            bg_color = "#5f5f1a"  # Dark yellow
        elif state == "ACTIVE":
            color = "🔵"
            bg_color = "#1a1a5f"  # Dark blue
        else:
            color = "⚪"
            bg_color = "#3a3a3a"  # Dark gray

        # BIG STATUS BOX
        st.markdown(f"""
        <div style="background-color: {bg_color}; padding: 30px; border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; font-size: 48px;">{color} {orb_name} ORB</h1>
            <h2 style="color: white; margin: 10px 0 0 0;">{state}</h2>
        </div>
        """, unsafe_allow_html=True)

        # ====================================================================
        # SECTION 2: PRICE POSITION (WHERE ARE WE?)
        # ====================================================================

        st.markdown("### 📊 CURRENT POSITION")

        col1, col2, col3 = st.columns(3)

        with col1:
            if hasattr(evaluation, 'orb_high') and evaluation.orb_high:
                st.metric("ORB High", f"${evaluation.orb_high:.2f}",
                         delta=f"{current_price - evaluation.orb_high:+.2f}" if current_price > 0 else None)

        with col2:
            if current_price > 0:
                st.metric("Current Price", f"${current_price:.2f}",
                         delta=None)

        with col3:
            if hasattr(evaluation, 'orb_low') and evaluation.orb_low:
                st.metric("ORB Low", f"${evaluation.orb_low:.2f}",
                         delta=f"{current_price - evaluation.orb_low:+.2f}" if current_price > 0 else None)

        # Price vs ORB visualization
        orb_high = getattr(evaluation, 'orb_high', None)
        orb_low = getattr(evaluation, 'orb_low', None)

        if orb_high and orb_low and current_price > 0:
            orb_range = orb_high - orb_low

            if current_price > orb_high:
                position = "🔼 ABOVE ORB (Bullish breakout zone)"
                position_color = "green"
            elif current_price < orb_low:
                position = "🔽 BELOW ORB (Bearish breakout zone)"
                position_color = "red"
            else:
                position = "↔️ INSIDE ORB (Waiting for breakout)"
                position_color = "orange"

            st.markdown(f"**Position**: <span style='color: {position_color}; font-size: 20px;'>{position}</span>", unsafe_allow_html=True)
            st.caption(f"ORB Range: {orb_range:.2f} pts")

        # ====================================================================
        # SECTION 3: WHAT TO DO RIGHT NOW
        # ====================================================================

        st.markdown("### 💡 ACTION")

        action = evaluation.action.value if hasattr(evaluation, 'action') else "STAND_DOWN"

        if action == "ENTER":
            # READY TO TRADE
            st.success(f"✅ **TRADE SETUP READY**")

            direction = getattr(evaluation, 'direction', 'Unknown')
            st.markdown(f"**Direction**: {direction}")

            col1, col2, col3 = st.columns(3)
            with col1:
                entry = getattr(evaluation, 'entry_price', 0)
                if entry:
                    st.metric("Entry", f"${entry:.2f}")
            with col2:
                stop = getattr(evaluation, 'stop_price', 0)
                if stop:
                    st.metric("Stop", f"${stop:.2f}")
            with col3:
                target = getattr(evaluation, 'target_price', 0)
                if target:
                    st.metric("Target", f"${target:.2f}")

            # Risk info
            risk_pct = getattr(evaluation, 'risk_pct', None)
            if risk_pct:
                st.info(f"📊 Risk: {risk_pct:.2%} of account")

            # Setup quality
            setup_tier = getattr(evaluation, 'setup_tier', None)
            if setup_tier:
                tier_emoji = {"S+": "🏆", "S": "⭐", "A": "🎯", "B": "✓", "C": "•"}.get(setup_tier, "•")
                quality = f"{tier_emoji} {setup_tier} Tier Setup"

                win_rate = getattr(evaluation, 'win_rate', None)
                if win_rate:
                    quality += f" • {win_rate:.0f}% WR"

                avg_r = getattr(evaluation, 'avg_r', None)
                if avg_r:
                    quality += f" • {avg_r:+.2f}R avg"

                st.caption(quality)

        elif action == "PREPARE":
            # FORMING OR WAITING
            next_instruction = getattr(evaluation, 'next_instruction', 'Preparing...')
            st.info(f"⏳ **{next_instruction}**")

            # Show ORB formation progress if available
            now = datetime.now()
            if "forming" in next_instruction.lower():
                try:
                    # Extract ORB time from strategy name
                    orb_name_str = getattr(evaluation, 'strategy_name', '').replace("_ORB", "")
                    if orb_name_str and len(orb_name_str) >= 2:
                        orb_hour = int(orb_name_str[:2])
                        orb_min = int(orb_name_str[2:]) if len(orb_name_str) > 2 else 0
                        orb_start = now.replace(hour=orb_hour, minute=orb_min, second=0, microsecond=0)
                        orb_end = orb_start.replace(minute=orb_start.minute + 5)

                        if now < orb_end:
                            elapsed = (now - orb_start).total_seconds() / 60
                            remaining = 5 - elapsed
                            st.progress(elapsed / 5)
                            st.caption(f"⏱️ {remaining:.1f} minutes until ORB complete")
                except (ValueError, AttributeError):
                    pass  # Skip progress bar if parsing fails

        else:
            # WAIT / STAND DOWN
            next_instruction = getattr(evaluation, 'next_instruction', 'Wait for setup')
            st.warning(f"⏸️ **WAIT**: {next_instruction}")

        # ====================================================================
        # SECTION 4: WHY? (REASONING)
        # ====================================================================

        with st.expander("📋 Setup Details", expanded=(action == "ENTER")):
            st.markdown("**Reasons:**")
            reasons = getattr(evaluation, 'reasons', [])
            for reason in reasons:
                st.markdown(f"- {reason}")

            # Best alternative if current setup not ideal
            setup_tier = getattr(evaluation, 'setup_tier', None)
            if setup_tier and setup_tier not in ["S+", "S", "A"]:
                st.caption("💡 This is not the highest probability setup. Consider waiting for better conditions.")

    else:
        # NO ACTIVE ORB
        st.markdown("""
        <div style="background-color: #3a3a3a; padding: 30px; border-radius: 10px; text-align: center;">
            <h2 style="color: white; margin: 0;">⏸️ NO ACTIVE SETUP</h2>
            <p style="color: #cccccc; margin: 10px 0 0 0;">Waiting for next ORB window</p>
        </div>
        """, unsafe_allow_html=True)

        # Show next ORB time
        now = datetime.now()
        next_orbs = []
        orb_times = [(9, 0, "0900"), (10, 0, "1000"), (11, 0, "1100"),
                     (18, 0, "1800"), (23, 0, "2300"), (0, 30, "0030")]

        for h, m, name in orb_times:
            orb_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

            # Handle overnight ORBs (if current time is late, check tomorrow's early ORBs)
            if h <= 3 and now.hour >= 12:
                orb_time = orb_time + timedelta(days=1)

            if orb_time > now:
                diff = (orb_time - now).total_seconds() / 60
                next_orbs.append((name, diff))

        if next_orbs:
            next_orbs.sort(key=lambda x: x[1])
            next_orb, minutes = next_orbs[0]
            hours = int(minutes // 60)
            mins = int(minutes % 60)

            if hours > 0:
                time_str = f"{hours}h {mins}m"
            else:
                time_str = f"{mins}m"

            st.info(f"⏰ Next ORB: **{next_orb}** in {time_str}")

    # ========================================================================
    # SECTION 5: AI QUICK ANALYSIS
    # ========================================================================

    st.markdown("---")
    st.markdown("### 🤖 AI Analysis")

    # Quick question buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📊 Analyze Setup", use_container_width=True):
            session_state['quick_question'] = "Analyze the current ORB setup. Is this a good trade?"

    with col2:
        if st.button("🎯 Best Strategy", use_container_width=True):
            session_state['quick_question'] = "What's the best strategy for this ORB time right now?"

    with col3:
        if st.button("⚠️ Risk Check", use_container_width=True):
            session_state['quick_question'] = "What are the risks with this setup?"

    # Chat interface (compact)
    user_input = st.text_input(
        "Ask about current market:",
        key="simple_ai_input",
        placeholder="e.g., Should I take this 0030 ORB?"
    )

    if st.button("Ask", type="primary") or session_state.get('quick_question'):
        question = session_state.get('quick_question', user_input)
        session_state['quick_question'] = None  # Clear

        if question and question.strip():
            with st.spinner("Analyzing..."):
                try:
                    # Get AI response focused on current setup
                    # Safely extract evaluation attributes
                    action_obj = getattr(evaluation, 'action', None)
                    state_obj = getattr(evaluation, 'state', None)

                    response = ai_assistant.chat(
                        user_message=question,
                        conversation_history=[],  # Fresh context each time for simplicity
                        session_id=session_state.get('session_id', 'simple'),
                        instrument="MGC",
                        current_price=current_price,
                        strategy_state={
                            'strategy': getattr(evaluation, 'strategy_name', 'None') if evaluation else 'None',
                            'action': action_obj.value if action_obj and hasattr(action_obj, 'value') else 'STAND_DOWN',
                            'state': state_obj.value if state_obj and hasattr(state_obj, 'value') else 'INVALID',
                            'entry_price': getattr(evaluation, 'entry_price', None) if evaluation else None,
                            'stop_price': getattr(evaluation, 'stop_price', None) if evaluation else None,
                            'target_price': getattr(evaluation, 'target_price', None) if evaluation else None,
                            'orb_high': getattr(evaluation, 'orb_high', None) if evaluation else None,
                            'orb_low': getattr(evaluation, 'orb_low', None) if evaluation else None,
                            'direction': getattr(evaluation, 'direction', None) if evaluation else None,
                            'reasons': getattr(evaluation, 'reasons', []) if evaluation else [],
                            'tier': getattr(evaluation, 'setup_tier', None) if evaluation else None,
                            'rr': getattr(evaluation, 'rr', None) if evaluation else None,
                            'win_rate': getattr(evaluation, 'win_rate', None) if evaluation else None,
                            'avg_r': getattr(evaluation, 'avg_r', None) if evaluation else None
                        },
                        orb_data=orb_data or {}
                    )

                    st.markdown("**AI Response:**")
                    st.markdown(response)

                except Exception as e:
                    st.error(f"Error: {e}")


def render_simple_mode_toggle():
    """Render mode toggle at top of app."""

    col1, col2 = st.columns([3, 1])

    with col2:
        if 'simple_mode' not in st.session_state:
            st.session_state['simple_mode'] = True

        mode = st.toggle("Simple Mode", value=st.session_state['simple_mode'])
        st.session_state['simple_mode'] = mode

    return st.session_state['simple_mode']
