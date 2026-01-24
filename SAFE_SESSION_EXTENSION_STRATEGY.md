# Safe Session Logic Extension Strategy

**Date**: 2026-01-23
**Purpose**: How to extend session logic without breaking existing functionality
**Status**: Strategic guide for future development

---

## Current State: What's Already Integrated

### ✅ Working Components

1. **Market State Detection** (`market_state.py`)
   - **Function**: Detects ABOVE/BELOW/INSIDE Asia range
   - **Used by**: Conditional edges (38 setups)
   - **Database dependency**: `daily_features_v2.asia_high`, `asia_low`
   - **Integration point**: `setup_detector.get_conditional_setups()`
   - **Status**: ✅ PRODUCTION, TESTED, WORKING

2. **Session Liquidity Tracker** (`session_liquidity.py`)
   - **Function**: Tracks Asia/London/NY highs/lows, detects sweeps/cascades
   - **Used by**: STANDALONE (not yet integrated into trading app)
   - **Integration point**: None (ready to integrate)
   - **Status**: ⚠️ BUILT BUT UNUSED

3. **Strategy State Machine** (`strategy_engine.py`)
   - **Function**: ORB lifecycle management (INVALID → PREPARING → READY → ACTIVE → EXITED)
   - **Used by**: Trading Hub, all ORB strategies
   - **Integration point**: `app_trading_hub.py` calls `evaluate_all()`
   - **Status**: ✅ PRODUCTION, CORE DEPENDENCY

4. **Conditional Edges** (Phase 1B)
   - **Function**: Asia_bias-based setup filtering
   - **Database**: 38 conditional setups + 8 baseline
   - **Integration point**: `app_trading_hub.py` line 1177
   - **Status**: ✅ PRODUCTION, RECENTLY COMPLETED

---

## Architecture: Integration Points Map

```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING APP (app_trading_hub.py)          │
│                                                              │
│  ┌──────────────┐     ┌────────────────┐                   │
│  │ Price Data   │────▶│ Strategy Engine│                   │
│  │ (data_loader)│     │ evaluate_all() │                   │
│  └──────────────┘     └────────┬───────┘                   │
│                                 │                            │
│                                 ▼                            │
│                       ┌─────────────────┐                   │
│                       │  State Machine  │                   │
│                       │ INVALID→READY   │                   │
│                       └────────┬────────┘                   │
│                                │                            │
│                                ▼                            │
│                       ┌─────────────────┐                   │
│                       │  ORB Filters    │                   │
│                       │  Size/Session   │                   │
│                       └─────────────────┘                   │
│                                                              │
│  ┌────────────────────────────────────────────────┐        │
│  │  Conditional Edges Panel (line 1177)           │        │
│  │  ┌──────────────┐     ┌──────────────────┐   │        │
│  │  │Market State  │────▶│ Setup Detector   │   │        │
│  │  │get_market_   │     │get_conditional_  │   │        │
│  │  │state()       │     │setups()          │   │        │
│  │  └──────────────┘     └──────────────────┘   │        │
│  └────────────────────────────────────────────────┘        │
│                                                              │
│  ⚠️ NOT YET INTEGRATED:                                    │
│  ┌────────────────────────────────────────────────┐        │
│  │  SessionLiquidity (session_liquidity.py)       │        │
│  │  - Sweep detection                              │        │
│  │  - Cascade patterns                             │        │
│  │  - Directional bias                             │        │
│  │  STATUS: Built but unused                       │        │
│  └────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │   Database     │
                  │  gold.db       │
                  │                │
                  │ • bars_1m      │
                  │ • bars_5m      │
                  │ • daily_       │
                  │   features_v2  │
                  │ • validated_   │
                  │   setups       │
                  └────────────────┘
```

---

## Safe Extension Patterns

### Pattern 1: Add New Session-Based Condition (SAFEST)

**What**: Add new condition type like `london_bias` or `pre_orb_trend`
**Risk**: LOW (follows existing pattern)
**Impact**: Database + UI only (no core logic changes)

**Steps**:
1. Add condition data to `validated_setups` (new rows)
2. Extend `market_state.py` with new detection function
3. Update `setup_detector.get_conditional_setups()` to match new condition
4. Add UI display in `render_conditional_edges.py`
5. Test with `test_conditional_edges.py`

**Example: Adding london_bias**:
```python
# Step 1: market_state.py
def get_london_bias(current_price: float, db_path=None, target_date=None):
    """Detect ABOVE/BELOW/INSIDE London range."""
    london_data = get_london_range(db_path, target_date)
    if not london_data:
        return 'UNKNOWN'
    return detect_bias(current_price, london_data['london_high'], london_data['london_low'])

# Step 2: setup_detector.py (add to get_conditional_setups)
if condition_type == 'london_bias':
    london_bias = get_london_bias(current_price, target_date=target_date)
    if condition_value == london_bias:
        matching_setups.append(setup)

# Step 3: Database insert
INSERT INTO validated_setups (
    instrument, setup_id, orb_time, rr, sl_mode,
    condition_type, condition_value, quality_multiplier, ...
) VALUES (
    'MGC', 'MGC_1800_london_bias_ABOVE_001', '1800', 8.0, 'HALF',
    'london_bias', 'ABOVE', 2.5, ...
);

# Step 4: UI rendering (render_conditional_edges.py)
london_bias = get_london_bias(current_price, target_date)
st.metric("London Bias", london_bias)
```

**Safety guarantees**:
- Existing `asia_bias` setups still work (unchanged)
- Database schema already supports this (condition_type VARCHAR)
- No changes to core strategy engine
- Isolated failure (if london_bias breaks, asia_bias still works)

---

### Pattern 2: Integrate SessionLiquidity for Display (MEDIUM RISK)

**What**: Use `SessionLiquidity` class to show sweep alerts in UI
**Risk**: MEDIUM (new real-time component)
**Impact**: UI only, no trading logic changes

**Steps**:
1. Add SessionLiquidity panel to Trading Hub
2. Load bars into SessionLiquidity on each refresh
3. Display sweep status and directional bias
4. **DO NOT** use for automated trading decisions yet (display only)

**Implementation**:
```python
# app_trading_hub.py (add after line 1191)
with st.expander("💧 Session Liquidity Tracker", expanded=False):
    try:
        from session_liquidity import SessionLiquidity
        from datetime import datetime

        tracker = SessionLiquidity()

        # Load today's bars
        bars_df = loader.fetch_latest_bars(lookback_minutes=1440)  # Full day
        if not bars_df.empty:
            current_time = datetime.now(TZ_LOCAL)
            tracker.update_from_bars(bars_df, current_time)

            # Display liquidity report
            report = tracker.format_liquidity_report(current_price, current_time)
            st.text(report)
        else:
            st.warning("No bar data available for liquidity tracking")
    except Exception as e:
        st.error(f"Error loading Session Liquidity: {e}")
```

**Safety guarantees**:
- Display only (no automated trades)
- Isolated in expander (won't break main app if crashes)
- Uses existing data_loader (no new DB queries)
- Can be disabled by collapsing expander

**DON'T DO THIS YET**:
- ❌ Use sweep detection to auto-enter trades
- ❌ Override strategy engine decisions
- ❌ Auto-size positions based on cascades
- First: Display → Validate → Then integrate into decision logic

---

### Pattern 3: Add Session Filter to Strategy Engine (HIGHER RISK)

**What**: Add london_filter, asia_filter logic to strategy engine
**Risk**: MEDIUM-HIGH (modifies core trading logic)
**Impact**: Changes when trades are taken

**Current implementation**: Already exists in `strategy_engine.py` lines 920-960
**Status**: ✅ ALREADY IMPLEMENTED (london_filter, asia_filter)

**Safe extension**: Add NEW filters (e.g., ny_filter)
```python
# strategy_engine.py (in _check_orb method, after line 960)

# Check NY filter (new)
ny_filter = config.get("ny_filter")
if ny_filter and ny_hl:
    ny_range = ny_hl["high"] - ny_hl["low"]
    if ny_range > ny_filter:
        return StrategyEvaluation(
            strategy_name=f"{orb_name}_ORB",
            priority=2 if config["tier"] == "NIGHT" else 4,
            state=StrategyState.INVALID,
            action=ActionType.STAND_DOWN,
            reasons=[
                f"NY RANGE FILTER REJECTED",
                f"NY range ${ny_range:.1f} > ${ny_filter:.1f} limit",
                "Choppy NY = whippy ORB breakout"
            ],
            next_instruction=f"Stand down - NY too volatile for clean {orb_name} break"
        )
```

**Safety protocol**:
1. Add filter to `validated_setups` database first
2. Update `config_generator.py` to export ny_filter
3. Add filter check to strategy_engine.py
4. Test with `test_app_sync.py`
5. Backtest filter performance before using live

**Critical rule**: ALWAYS update both database AND config.py together (per CLAUDE.md sync protocol)

---

### Pattern 4: Add Pre-ORB Trend Condition (COMPLEX)

**What**: Implement `pre_orb_trend` condition (UP/DOWN/NEUTRAL)
**Risk**: MEDIUM (requires intraday bar analysis)
**Impact**: Database + market_state.py + UI

**Status**: Function exists in `session_liquidity.py` line 318 but NOT integrated

**Steps**:
1. Add pre_orb_trend detection to market_state.py
2. Add condition rows to validated_setups
3. Update setup_detector to match pre_orb_trend
4. Test extensively (this requires correct bar timing)

**Implementation sketch**:
```python
# market_state.py
def get_pre_orb_trend(orb_time: str, target_date: date, db_path=None) -> str:
    """
    Get pre-ORB trend (UP/DOWN/NEUTRAL) for specific ORB.

    Returns:
        'UP': Close in upper 40% of pre-ORB range
        'DOWN': Close in lower 40% of pre-ORB range
        'NEUTRAL': Close in middle 20%
        'UNKNOWN': No data available
    """
    from session_liquidity import calculate_pre_orb_trend

    # Load bars from database
    bars_df = load_bars_for_date(target_date, db_path)
    if bars_df.empty:
        return 'UNKNOWN'

    orb_datetime = combine_date_and_time(target_date, orb_time)
    trend = calculate_pre_orb_trend(bars_df, orb_time, orb_datetime)

    return trend or 'NEUTRAL'

# setup_detector.py (in get_conditional_setups)
elif condition_type == 'pre_orb_trend':
    # This condition is ORB-specific (needs orb_time)
    if orb_time:  # Only evaluate if we know which ORB
        trend = get_pre_orb_trend(orb_time, target_date, db_path)
        if condition_value == trend:
            matching_setups.append(setup)
```

**Complexity notes**:
- pre_orb_trend is ORB-specific (1000 ORB has different trend than 1100 ORB)
- Requires loading intraday bars (not in daily_features_v2)
- Timing sensitive (must use bars BEFORE ORB, no lookahead)

**Recommendation**: Start with display-only (show trend in UI) before using for filtering

---

## Critical Safety Rules

### Rule 1: Database-Config Synchronization (NEVER VIOLATE)

**ALWAYS run after ANY changes to validated_setups or config.py**:
```bash
python test_app_sync.py
```

**What it checks**:
- Config.py MGC_ORB_SIZE_FILTERS matches database orb_size_filter column
- SetupDetector can load all instruments
- Data loader filter checking works
- Strategy engine configs load properly

**If it fails**: STOP, fix mismatch, re-run test

**Why**: Mismatches = wrong trades = real money losses

---

### Rule 2: Isolated Testing Before Integration

**Pattern**: Build → Test standalone → Integrate → Test integration

**Example: Adding london_bias**:
```bash
# Step 1: Build london_bias detection
python trading_app/market_state.py 2650.5 2026-01-15  # Test standalone

# Step 2: Add to database
python tools/import_phase1b_setups.py  # Import london_bias setups

# Step 3: Test detection
python test_conditional_edges.py  # Test with new condition

# Step 4: Integrate to UI
streamlit run trading_app/app_trading_hub.py  # Visual check

# Step 5: Verify sync
python test_app_sync.py  # Final verification
```

**Never skip steps**. Each layer tests the one below it.

---

### Rule 3: Display Before Automation

**Principle**: Show data in UI → Validate correctness → Then use for decisions

**Bad approach**:
```python
# ❌ DON'T DO THIS
sweeps = tracker.check_liquidity_sweep(price, time)
if sweeps['directional_bias'] == 'STRONG BULLISH':
    auto_enter_long_trade()  # DANGER: No human validation
```

**Good approach**:
```python
# ✅ DO THIS
sweeps = tracker.check_liquidity_sweep(price, time)
st.metric("Directional Bias", sweeps['directional_bias'])
st.caption(sweeps['bias_reason'])
# Human sees bias, decides whether to trade
```

**Timeline**:
1. Week 1: Display sweep info in UI
2. Week 2-3: Validate against actual price action
3. Week 4: If validated, consider using for position sizing hints
4. Month 2+: If still validated, consider auto-filtering

**Never auto-trade new logic on Day 1.**

---

### Rule 4: Backwards Compatibility

**Principle**: New features should not break existing setups

**Check before deploying**:
```python
# Existing asia_bias setups must still work
detector = SetupDetector()
result = detector.get_active_and_potential_setups('MGC', 2650.5, date.today())

assert len(result['active']) > 0, "Existing conditional setups broken!"
assert len(result['baseline']) == 8, "Baseline setups broken!"
```

**Safe changes**:
- ✅ Add new condition_type (doesn't affect existing)
- ✅ Add new columns to validated_setups (old queries still work)
- ✅ Add new UI panels (existing panels unchanged)

**Unsafe changes**:
- ❌ Rename condition_type values (breaks existing setups)
- ❌ Change market_state.py return format (breaks setup_detector)
- ❌ Modify StrategyState enum (breaks strategy_engine)

---

### Rule 5: Zero Lookahead Enforcement

**Principle**: Only use data available at decision time

**Good**:
```python
# ✅ Asia range is known at 5PM (after Asia close)
if now.hour >= 17:
    asia_high = get_asia_range(today)
    bias = detect_bias(price, asia_high, asia_low)
```

**Bad**:
```python
# ❌ Using today's full range before day ends
if now.hour == 10:  # 10am
    asia_high = get_asia_range(today)  # Asia session not complete yet!
```

**Lookahead checks**:
- ORB filters use ATR_20 (computed at ORB close, not end of day)
- Asia bias only used after 17:00 (Asia close)
- Pre-ORB trend uses bars BEFORE ORB formation only

**Verification**:
```bash
python tools/verify_zero_lookahead.py  # Check all feature calculations
```

---

## Extension Roadmap (Safe Order)

### Phase 1: Low-Risk Display Additions (Week 1)
1. Add SessionLiquidity panel to Trading Hub (display only)
2. Show sweep status and cascade patterns
3. Display directional bias with reasoning
4. **NO automated decisions yet**

### Phase 2: New Conditions (Week 2-3)
1. Add london_bias condition (follows asia_bias pattern)
2. Import london_bias setups to database
3. Update conditional edges UI to show london_bias
4. Test with historical data

### Phase 3: Pre-ORB Trend (Week 4-5)
1. Implement pre_orb_trend detection (complex timing)
2. Validate with backtest (no lookahead)
3. Add pre_orb_trend setups to database
4. Display in UI, validate in paper trading

### Phase 4: Advanced Integration (Month 2+)
1. Use sweep detection for position sizing hints
2. Add cascade pattern alerts
3. Consider auto-filtering based on session bias
4. Multi-condition setups (asia_bias + london_bias + pre_orb_trend)

**Critical**: Each phase requires 1-2 weeks of paper trading validation before live use

---

## Verification Procedures

### Pre-Deployment Checklist

Before any session logic change goes live:

- [ ] Code review: Does it follow safe extension patterns?
- [ ] Unit tests: Do isolated functions work?
- [ ] Integration test: `python test_app_sync.py` passes?
- [ ] Conditional edges test: `python test_conditional_edges.py` passes?
- [ ] Zero lookahead check: No future data used?
- [ ] UI test: Streamlit app starts without errors?
- [ ] Database sync: Config.py matches validated_setups?
- [ ] Backwards compatibility: Existing setups still work?
- [ ] Paper trading: Validate for 1+ weeks before live?
- [ ] Documentation: README updated with new features?

**If ANY checkbox fails**: Fix before deploying.

---

### Continuous Verification

**Daily** (if app running):
```bash
python test_app_sync.py  # Quick health check
```

**After database changes**:
```bash
python test_app_sync.py  # Verify sync
python test_conditional_edges.py  # Verify conditional logic
```

**After code changes**:
```bash
streamlit run trading_app/app_trading_hub.py  # Visual check
# Check browser console for JavaScript errors
# Check terminal for Python exceptions
```

**Weekly**:
```bash
python tools/audit_validated_setups.py  # Check setup integrity
python tools/verify_zero_lookahead.py  # Verify no lookahead
```

---

## Emergency Rollback Procedure

If new session logic breaks production:

1. **Immediate**: Disable new feature in UI (comment out expander)
2. **Quick fix**: Revert to last known good config.py
3. **Database**: Remove broken conditional setups
4. **Verify**: Run `python test_app_sync.py` to confirm fix
5. **Test**: Restart app, verify existing setups work
6. **Post-mortem**: Document what broke, how to prevent

**Example rollback**:
```bash
# Disable SessionLiquidity panel (line 1195 in app_trading_hub.py)
# with st.expander("💧 Session Liquidity Tracker", expanded=False):  # DISABLED 2026-01-24
#     ...

# Revert config.py if needed
git diff trading_app/config.py  # Check what changed
git checkout HEAD~1 trading_app/config.py  # Revert to previous

# Remove broken setups from database
python tools/remove_broken_setups.py  # Custom script

# Verify
python test_app_sync.py
```

---

## What NOT To Do

### ❌ DON'T: Bypass the strategy engine

**Bad**:
```python
# Don't add parallel decision logic outside strategy engine
if session_liquidity.directional_bias == 'BULLISH':
    auto_enter_long()  # Bypasses filters, state machine, risk checks
```

**Why**: Strategy engine has filters, state transitions, risk limits. Bypassing = uncontrolled trades.

### ❌ DON'T: Modify core enums without understanding impact

**Bad**:
```python
# Don't change existing enum values
class StrategyState(Enum):
    INVALID = "INVALID"
    PREPARING = "READY"  # ❌ Changed PREPARING to READY - breaks everything!
```

**Why**: Enums used throughout app. Changing values = cascading failures.

### ❌ DON'T: Add database columns without migration

**Bad**:
```python
# Don't just add columns and hope it works
ALTER TABLE validated_setups ADD COLUMN new_feature DOUBLE;  # ❌ No migration script
```

**Why**: Need to handle NULL values, update queries, test old data compatibility.

**Good**:
```python
# Create migration script
python tools/migrate_add_new_feature.py  # Handles NULLs, tests, rollback
```

### ❌ DON'T: Use session logic for real-time decisions without backtesting

**Bad**:
```python
# Don't use new logic immediately
if get_london_bias(price) == 'ABOVE':
    auto_trade()  # ❌ Never backtested, could be garbage signal
```

**Why**: New logic needs validation. Could be flawed, have lookahead, or just not work.

### ❌ DON'T: Override user decisions

**Bad**:
```python
# Don't force trades
if cascade_detected:
    execute_trade_automatically()  # ❌ User loses control
```

**Why**: This is decision support, not auto-trading. User must confirm.

---

## Summary: The Safe Path

### Current State
- ✅ Market state (asia_bias) working in production
- ✅ Strategy engine state machine working
- ✅ 38 conditional setups validated
- ⚠️ SessionLiquidity built but not integrated

### Safe Extension Strategy
1. **Add new conditions** following asia_bias pattern (low risk)
2. **Display SessionLiquidity** in UI first (medium risk)
3. **Validate extensively** before using for automated decisions
4. **Always maintain sync** between database and config.py
5. **Test at every layer** (unit → integration → UI → paper trade)

### Red Lines (Never Cross)
- ❌ Never skip test_app_sync.py after changes
- ❌ Never bypass strategy engine with parallel logic
- ❌ Never auto-trade new logic without backtesting
- ❌ Never break backwards compatibility with existing setups
- ❌ Never introduce lookahead in feature calculations

### When In Doubt
1. Add feature as **display-only** first
2. Validate for **1-2 weeks** in paper trading
3. Get **user approval** before automation
4. **Document** what you built and why
5. **Test** obsessively before going live

---

## Your Next Steps

Given your current system is working correctly (once you close PID 36612):

### Option A: Add SessionLiquidity Display (Lowest Risk)
- Add liquidity tracker panel to Trading Hub
- Show sweeps and cascades (display only)
- Validate patterns match real market behavior
- Timeline: 1-2 days coding, 1 week validation

### Option B: Add london_bias Condition (Medium Risk)
- Follow asia_bias pattern exactly
- Add london_bias detection to market_state.py
- Import london_bias setups from research
- Update UI to show london_bias
- Timeline: 3-5 days coding, 1 week validation

### Option C: Implement pre_orb_trend (Higher Complexity)
- Requires intraday bar analysis
- Timing-sensitive (no lookahead)
- Need extensive backtesting
- Timeline: 1-2 weeks coding, 2 weeks validation

**Recommendation**: Start with Option A (SessionLiquidity display). Lowest risk, immediate value, teaches you the integration patterns for later options.

---

## Contact

Questions about safe extension?
- This file: Safe extension strategy
- `CONDITIONAL_EDGES_COMPLETE.md`: Current integration details
- `CLAUDE.md`: Database sync protocol (critical!)
- `test_app_sync.py`: Verification script (run obsessively)
- `test_conditional_edges.py`: Integration test examples

**Remember**: Slow is smooth, smooth is fast. Better to extend safely over weeks than break production and lose money.
