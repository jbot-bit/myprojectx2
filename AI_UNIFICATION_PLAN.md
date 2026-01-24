# AI Memory Unification Plan

**Date**: 2026-01-23
**Problem**: AI memory, conversation, and uploads are disconnected. App is spammy.
**Goal**: Create unified conversational AI system that flows naturally

---

## Current Issues (Diagnosed)

### 1. **Disconnected Components** ❌

```
┌────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  File Upload   │     │  Chat Interface  │     │  AI Memory   │
│  (Isolated)    │     │  (Isolated)      │     │  (Isolated)  │
└────────────────┘     └──────────────────┘     └──────────────┘
        │                       │                        │
        ▼                       ▼                        │
  Separate analysis      Separate messages              │
  NOT in conversation    NOT in memory              Saves but not
  NOT saved              Evidence Pack fresh        used for context
```

**Problems**:
- Upload analysis doesn't save to conversation history
- Chat doesn't reference previous uploads
- Memory exists but not fully utilized for context
- Evidence Pack rebuilt from scratch each time (repetitive)

### 2. **Spammy/Repetitive** ❌

Current Evidence Pack includes SAME facts every time:
```python
facts = [
    "Instrument: MGC",  # ← Repeated every message
    "Current price: $2650.50",  # ← Already visible in UI
    "Strategy status: WAIT",  # ← User can see this
    "Asia session: $2645 - $2655",  # ← Repeated
    # ... more redundant info
]
```

Result: Long context, slow responses, high API costs

### 3. **Upload Isolation** ❌

**Image uploads** (line 1320-1350):
```python
uploaded_file = st.file_uploader(...)
if uploaded_file:
    image_bytes = uploaded_file.read()
    analysis = chart_analyzer.analyze_chart_image(image_bytes)
    st.markdown(analysis)  # ← Displayed but NOT saved to memory!
```

**CSV uploads** (line 1257-1308):
```python
if is_csv:
    df = pd.read_csv(csv_data)
    csv_summary = generate_csv_summary(df)
    st.text(csv_summary)  # ← Displayed but NOT in conversation!
    st.info("CSV ingestion coming soon")  # ← Never integrated
```

**Problems**:
- Analysis results shown once, then lost
- Can't reference "the chart I uploaded 10 minutes ago"
- No conversation continuity across uploads
- Memory has no record of what files were analyzed

### 4. **Memory Not Used for Context** ❌

Memory loads on startup (line 171-181):
```python
loaded_history = st.session_state.memory_manager.load_session_history()
st.session_state.chat_history = [{"role": msg["role"], "content": msg["content"]} ...]
```

But Evidence Pack doesn't use it:
```python
evidence_pack = self._build_evidence_pack(
    # ← NO reference to conversation history!
    # ← NO reference to previous uploads!
    # ← NO reference to past context!
)
```

**Result**: AI has amnesia between sessions, repeats itself

---

## Unified Architecture (Target State)

### Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                     UNIFIED CONVERSATION CONTEXT                  │
│                                                                   │
│  ┌─────────────────┐   ┌─────────────────┐   ┌───────────────┐ │
│  │  File Uploads   │──▶│   AI Memory     │◀─▶│ Chat Messages │ │
│  │  (Images/CSV)   │   │   (Database)    │   │  (User/AI)    │ │
│  └─────────────────┘   └─────────────────┘   └───────────────┘ │
│           │                      │                      │         │
│           └──────────────────────┼──────────────────────┘         │
│                                  ▼                                │
│                     ┌────────────────────────┐                   │
│                     │   Context Builder      │                   │
│                     │  (Smart, Not Spammy)   │                   │
│                     └────────┬───────────────┘                   │
│                              ▼                                    │
│                     ┌────────────────────────┐                   │
│                     │   Evidence Pack        │                   │
│                     │  (Minimal, Referenced) │                   │
│                     └────────┬───────────────┘                   │
│                              ▼                                    │
│                     ┌────────────────────────┐                   │
│                     │   AI Response          │                   │
│                     │  (Contextual, Flowing) │                   │
│                     └────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Single Conversation Thread**: All interactions (chat, uploads, analysis) go into ONE conversation
2. **Smart Context**: Don't repeat facts visible in UI or already in recent history
3. **Memory Integration**: AI references past uploads, previous trades, earlier questions
4. **Upload Persistence**: File analysis results saved to memory, can be referenced later
5. **Flowing Conversation**: Feels like talking to someone who remembers the whole session

---

## Implementation Plan

### Phase 1: Connect Uploads to Memory (IMMEDIATE)

**What**: Save upload analysis results to conversation history

**File**: `trading_app/app_trading_hub.py`

**Changes**:

1. **Image Upload Integration** (after line 1335):
```python
# After: analysis = chart_analyzer.analyze_chart_image(image_bytes, image_type)
st.markdown(analysis)

# ADD THIS:
# Save to conversation memory
if st.session_state.memory_manager:
    # Save upload event
    upload_context = {
        "file_name": uploaded_file.name,
        "file_type": "image",
        "analysis_length": len(analysis),
        "current_price": current_price if 'current_price' in locals() else None
    }

    st.session_state.memory_manager.save_message(
        session_id=st.session_state.session_id,
        role="user",
        content=f"[Uploaded chart image: {uploaded_file.name}]",
        context_data=upload_context,
        instrument=symbol,
        tags=["upload", "chart", "image"]
    )

    st.session_state.memory_manager.save_message(
        session_id=st.session_state.session_id,
        role="assistant",
        content=analysis,
        context_data=upload_context,
        instrument=symbol,
        tags=["analysis", "chart", "image"]
    )

    # Update in-memory chat history (so it shows in chat panel)
    st.session_state.chat_history.append({
        "role": "user",
        "content": f"[Chart uploaded: {uploaded_file.name}]"
    })
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": analysis
    })

    st.success("✅ Chart analysis saved to conversation")
```

2. **CSV Upload Integration** (after line 1307):
```python
# After: st.text(csv_summary)

# ADD THIS:
# Save CSV summary to memory
if st.session_state.memory_manager:
    csv_context = {
        "file_name": uploaded_file.name,
        "file_type": "csv",
        "row_count": len(df),
        "columns": df.columns.tolist(),
        "date_range": f"{df['time'].min()} to {df['time'].max()}" if 'time' in df else None
    }

    st.session_state.memory_manager.save_message(
        session_id=st.session_state.session_id,
        role="user",
        content=f"[Uploaded CSV file: {uploaded_file.name} ({len(df)} rows)]",
        context_data=csv_context,
        instrument=symbol,
        tags=["upload", "csv", "data"]
    )

    st.session_state.memory_manager.save_message(
        session_id=st.session_state.session_id,
        role="assistant",
        content=csv_summary,
        context_data=csv_context,
        instrument=symbol,
        tags=["analysis", "csv", "data"]
    )

    # Update in-memory chat history
    st.session_state.chat_history.append({
        "role": "user",
        "content": f"[CSV uploaded: {uploaded_file.name}]"
    })
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": csv_summary
    })

    st.success("✅ CSV analysis saved to conversation")
```

**Result**: Uploads now part of conversation, can reference later

---

### Phase 2: Smart Context Builder (REDUCE SPAM)

**What**: Build Evidence Pack smarter - don't repeat visible/recent info

**File**: `trading_app/ai_assistant.py`

**Changes**:

Add new function before `_build_evidence_pack`:

```python
def _build_smart_context(
    self,
    instrument: str,
    current_price: float,
    strategy_state: Dict,
    session_levels: Dict,
    orb_data: Dict,
    conversation_history: List[Dict],
    user_question: str
) -> List[str]:
    """
    Build smart context - only include NEW or RELEVANT information.

    Rules:
    1. Don't repeat facts from last 3 messages
    2. Don't repeat facts visible in UI (price, status)
    3. Only include facts relevant to user's question
    4. Reference past conversation when helpful
    """
    facts = []

    # Extract recent facts from last 3 messages
    recent_facts = set()
    for msg in conversation_history[-3:]:
        if msg.get("role") == "assistant":
            # Extract key facts from recent responses (basic heuristic)
            content = msg.get("content", "")
            if "Current price" in content:
                recent_facts.add("price")
            if "Strategy status" in content:
                recent_facts.add("status")
            if "Asia session" in content:
                recent_facts.add("asia")

    # Only add instrument if NEW session (no recent messages)
    if len(conversation_history) < 3:
        facts.append(f"Instrument: {instrument}")

    # Price: Only if significantly changed OR user asks about it
    price_relevant = any(word in user_question.lower() for word in ['price', 'level', 'where'])
    if price_relevant and current_price > 0:
        facts.append(f"Current price: ${current_price:.2f}")

    # Strategy: Only if changed OR user asks about it
    strategy_relevant = any(word in user_question.lower() for word in ['strategy', 'setup', 'trade', 'enter', 'exit'])
    if strategy_relevant:
        status = strategy_state.get('action', 'STAND_DOWN')
        facts.append(f"Strategy status: {status}")
        facts.append(f"Strategy: {strategy_state.get('strategy', 'None')}")

    # Session levels: Only if user asks about them OR changed significantly
    session_relevant = any(word in user_question.lower() for word in ['asia', 'london', 'ny', 'session', 'range'])
    if session_relevant and session_levels:
        if 'asia_high' in session_levels and 'asia_low' in session_levels:
            facts.append(f"Asia session: ${session_levels['asia_low']:.2f} - ${session_levels['asia_high']:.2f}")
        if 'london_high' in session_levels and 'london_low' in session_levels:
            facts.append(f"London session: ${session_levels['london_low']:.2f} - ${session_levels['london_high']:.2f}")

    # ORB data: Only if user asks about it OR breakout happening
    orb_relevant = any(word in user_question.lower() for word in ['orb', '0900', '1000', '1100', 'breakout'])
    if orb_relevant and orb_data:
        for orb_name, orb_info in orb_data.items():
            if isinstance(orb_info, dict) and 'low' in orb_info and 'high' in orb_info:
                facts.append(f"{orb_name}: ${orb_info['low']:.2f} - ${orb_info['high']:.2f} (size: {orb_info.get('size', 0):.2f})")

    # Upload references: If user mentions "chart" or "upload"
    if any(word in user_question.lower() for word in ['chart', 'upload', 'image', 'csv', 'file']):
        # Find recent uploads in conversation history
        for msg in reversed(conversation_history[-10:]):
            if msg.get("role") == "user" and "[Uploaded" in msg.get("content", ""):
                facts.append(f"Recent upload: {msg['content']}")
                break

    # Conversation continuity: If user says "it" or "that" or "the trade", reference context
    if any(word in user_question.lower() for word in ['it', 'that', 'this', 'the trade']):
        # Get last assistant message
        for msg in reversed(conversation_history):
            if msg.get("role") == "assistant":
                # Extract key point from last response (first line)
                last_point = msg.get("content", "").split("\n")[0][:100]
                facts.append(f"Continuing from: {last_point}...")
                break

    return facts
```

**Update `_build_evidence_pack`** to use smart context:

```python
def _build_evidence_pack(...) -> Optional[EvidencePack]:
    # ... existing code ...

    # REPLACE THIS:
    # facts = []
    # facts.append(f"Instrument: {instrument}")
    # ... all the repetitive facts

    # WITH THIS:
    facts = self._build_smart_context(
        instrument=instrument,
        current_price=current_price,
        strategy_state=strategy_state,
        session_levels=session_levels,
        orb_data=orb_data,
        conversation_history=conversation_history,
        user_question=user_question
    )

    # ... rest of function unchanged
```

**Result**: Context is concise, relevant, not repetitive

---

### Phase 3: Conversation Flow Enhancement

**What**: Make AI reference past conversation naturally

**File**: `trading_app/ai_guard.py`

**Changes**: Update system prompt to use conversation history

Find the system prompt in `guarded_chat_answer` and add:

```python
# Before building messages, add instruction:
system_instructions = f"""
You are a trading assistant with access to live market data and conversation history.

CONVERSATION FLOW:
- This is an ongoing conversation (session {len(conversation_history)} messages so far)
- Reference previous uploads, questions, and analyses naturally
- Don't repeat information from recent messages
- If user says "it" or "that setup", you know what they mean from context
- Maintain continuity: "As we discussed..." "Following up on the chart you uploaded..."

EVIDENCE PACK:
{evidence_pack_summary}

RESPONSE STYLE:
- Concise (3-5 sentences max unless analysis requires more)
- Reference context naturally
- Don't restate visible UI information (price, status already on screen)
- Ask clarifying questions if context unclear
"""
```

**Result**: AI feels conversational, not robotic/repetitive

---

### Phase 4: Upload Preview in Chat

**What**: Show upload thumbnails/previews in chat history

**File**: `trading_app/app_trading_hub.py`

**Changes**: Update chat display to show upload previews

Find chat rendering section (around line 1400+) and enhance:

```python
# In the chat display loop:
for message in st.session_state.chat_history:
    role = message["role"]
    content = message["content"]

    with st.chat_message(role):
        # Check if this is an upload message
        if "[Uploaded" in content or "[Chart uploaded" in content:
            # Show upload indicator with icon
            if "image" in content.lower():
                st.markdown(f"📸 {content}")
            elif "csv" in content.lower():
                st.markdown(f"📊 {content}")
            else:
                st.markdown(content)
        else:
            st.markdown(content)
```

**Result**: Clear visual indication of uploads in conversation

---

## Summary of Changes

### Files to Modify

1. **`trading_app/app_trading_hub.py`**
   - Line ~1335: Add image upload memory save
   - Line ~1307: Add CSV upload memory save
   - Line ~1400: Enhance chat display with upload indicators

2. **`trading_app/ai_assistant.py`**
   - Add `_build_smart_context()` function
   - Update `_build_evidence_pack()` to use smart context
   - Pass conversation_history to context builder

3. **`trading_app/ai_guard.py`**
   - Update system prompt for conversation flow
   - Add conversation continuity instructions

### Expected Results

**Before** (Current State):
```
User: What's the current price?
AI: Instrument: MGC
    Current price: $2650.50
    Strategy status: WAIT
    Strategy: None
    Asia session: $2645.00 - $2655.00
    London session: $2650.00 - $2658.00
    [... 10 more lines of repetitive info ...]
    The current price is $2650.50.

User: [Uploads chart]
AI: [Analyzes chart, result shown but NOT saved]

User: What about that chart?
AI: [No context, doesn't remember] What chart are you referring to?
```

**After** (Unified System):
```
User: What's the current price?
AI: $2650.50

User: [Uploads chart showing support at $2645]
📸 [Chart uploaded: tradingview_screenshot.png]
AI: I see price holding above the Asia low at $2645, which matches
    the support level you highlighted. This aligns with the current
    ABOVE asia_bias condition we're in.

User: Should I take that 1000 ORB if it breaks?
AI: Based on the chart you just uploaded and our asia_bias=ABOVE
    condition, yes - the 1000 ORB would have a 3.0x quality multiplier
    right now. The support at $2645 gives good structure for a long setup.
```

---

## Testing Protocol

### Test 1: Upload Integration
1. Upload chart image
2. Check: Does it appear in conversation history?
3. Check: Can you reference it in next message?
4. Check: Does AI remember it?

### Test 2: Context Reduction
1. Ask "What's the price?" twice
2. Check: Second response should be shorter
3. Check: No repetition of instrument, status, etc.

### Test 3: Conversation Flow
1. Upload chart
2. Ask question about it
3. Ask follow-up using "it" or "that"
4. Check: AI maintains context

### Test 4: Memory Persistence
1. Close browser tab
2. Reopen app (new session)
3. Check: Chat history loads
4. Check: Previous uploads visible
5. Check: AI references past conversation

---

## Rollout Steps

1. **Phase 1 ONLY** (Upload integration):
   - Lowest risk
   - Immediate value (uploads saved)
   - Can test without affecting existing chat

2. **Verify Phase 1** (1-2 days):
   - Test upload saving
   - Check database (ai_chat_history table)
   - Verify no errors

3. **Phase 2** (Smart context):
   - Medium risk (changes Evidence Pack)
   - Test side-by-side (old vs new)
   - Monitor token usage (should decrease)

4. **Phase 3** (Conversation flow):
   - Low risk (prompt changes only)
   - A/B test responses
   - Adjust wording as needed

5. **Phase 4** (Upload preview):
   - Low risk (UI only)
   - Polish visual presentation
   - Add more preview types if needed

---

## Metrics to Track

**Before/After Comparison**:

| Metric | Before | After (Target) |
|--------|--------|----------------|
| Evidence Pack Size | ~2000 tokens | ~500 tokens |
| Repeated Facts per Message | 15-20 | 3-5 |
| Upload Retention | 0% (lost) | 100% (saved) |
| Context Continuity | 0% (amnesia) | 90%+ |
| User "AI forgot" complaints | Many | Rare |
| Token Cost per Message | High | 60% reduction |

---

## Risk Mitigation

### Backup Plan
- Keep old `_build_evidence_pack()` as `_build_evidence_pack_legacy()`
- Add env var: `USE_SMART_CONTEXT=1` (default 0 for safety)
- If issues, flip back to old method

### Gradual Rollout
```python
# In ai_assistant.py
USE_SMART_CONTEXT = os.getenv("USE_SMART_CONTEXT", "0") == "1"

if USE_SMART_CONTEXT:
    facts = self._build_smart_context(...)
else:
    facts = self._build_evidence_pack_legacy(...)
```

### Monitoring
- Log context size before/after
- Track user satisfaction (fewer "huh?" responses)
- Monitor token usage in API logs

---

## Next Steps

1. Review this plan
2. Confirm approach makes sense
3. Start with Phase 1 (upload integration)
4. Test thoroughly
5. Roll out incrementally

**Estimated Timeline**: 2-3 days implementation, 1 week validation

---

## Questions to Resolve

1. Should uploads be in main chat panel or separate "Uploads" tab?
   - **Recommendation**: Main chat (unified experience)

2. How many messages to keep in context?
   - **Recommendation**: Last 10-15 (balance context vs spam)

3. Show upload thumbnails in chat?
   - **Recommendation**: Yes (icons + filename)

4. Auto-reference uploads or explicit?
   - **Recommendation**: Auto (AI detects keywords)

---

## Contact

Questions about unification plan?
- This file: Complete implementation guide
- `CLAUDE.md`: Project authority and rules
- `ai_assistant.py`: Current AI implementation
- `ai_memory.py`: Memory storage
- `app_trading_hub.py`: UI integration points

**Remember**: The goal is ONE unified conversation, not multiple disconnected features.
