# Timing Display Fix: Show Active ORB Window

**Date**: 2026-01-23
**Problem**: At 23:10, app doesn't show 2300 ORB strategies (only shows at exactly 23:00)
**Root Cause**: Display logic uses exact time match, not active window logic

---

## Problem Analysis

### Current Behavior ❌

```
Time: 23:00  ← Shows 2300 ORB strategies ✓
Time: 23:01  ← Shows nothing ✗
Time: 23:10  ← Shows nothing ✗
Time: 23:30  ← Shows nothing ✗
Time: 00:00  ← Shows nothing ✗
```

**Why this is wrong**:
- 2300 ORB forms 23:00-23:05 (5 minutes)
- After 23:05, you're watching for breakout (could happen anytime in next 1-2 hours)
- At 23:10, you NEED to see 2300 ORB strategies (active window)
- At 00:30, 2300 ORB might still be valid (hasn't hit target or stop yet)

### Expected Behavior ✓

```
Time: 23:00  ← Shows 2300 ORB (FORMING)
Time: 23:01  ← Shows 2300 ORB (FORMING)
Time: 23:05  ← Shows 2300 ORB (READY - watching for break)
Time: 23:10  ← Shows 2300 ORB (READY/ACTIVE - still valid)
Time: 00:00  ← Shows 2300 ORB (READY/ACTIVE - still valid)
Time: 00:30  ← Shows 2300 ORB + 0030 ORB (both active)
Time: 02:00  ← Shows 2300 + 0030 (if not hit yet)
```

---

## ORB Window Logic (What Should Display When)

### ORB Lifecycle Stages

Each ORB has multiple stages, each should be displayed:

1. **FORMING** (0-5 min): ORB range forming
   - Display: "2300 ORB FORMING (3/5 min complete)"
   - Duration: 23:00-23:05

2. **READY** (5 min - breakout): Watching for first close outside range
   - Display: "2300 ORB READY - Watching for breakout"
   - Duration: 23:05 - until breakout occurs

3. **ACTIVE** (breakout - exit): Position open, managing trade
   - Display: "2300 ORB ACTIVE - Long from $2650 (target $2658)"
   - Duration: Entry until target/stop/timeout

4. **EXPIRED** (timeout): ORB didn't break or took too long
   - Display: "2300 ORB EXPIRED" (grayed out)
   - Duration: After 2-3 hours if no breakout

### Display Window Rules

**Rule**: Show ORB strategies if:
- Current time is AFTER ORB start time
- Current time is BEFORE ORB expiration (default: 3 hours after ORB start)
- Strategy state is NOT INVALID (filters not passed = don't show)

**Example: 2300 ORB**
```
Display from: 23:00 (ORB start)
Display until: 02:00 (3 hours later, or until EXITED)
Current state: FORMING → READY → ACTIVE → EXITED/EXPIRED
```

**Example: 0030 ORB**
```
Display from: 00:30 (ORB start)
Display until: 03:30 (3 hours later, or until EXITED)
Overlaps with 2300 ORB window (both can be active!)
```

---

## Current Implementation Issues

### Issue 1: Strategy Engine Uses Exact Hour Match

**File**: `trading_app/strategy_engine.py` line 738-756

**Current code**:
```python
def _evaluate_day_orb(self) -> StrategyEvaluation:
    now_local = datetime.now(TZ_LOCAL)
    current_hour = now_local.hour

    # Check each day ORB
    for orb_name in ["0900", "1000", "1100"]:
        orb_hour = int(orb_name[:2])
        if current_hour == orb_hour:  # ← EXACT MATCH ONLY!
            orb_result = self._check_orb(orb_name)
            if orb_result:
                return orb_result

    return StrategyEvaluation(
        strategy_name="DAY_ORB",
        state=StrategyState.INVALID,  # ← Returns INVALID if not exact hour!
        ...
    )
```

**Problem**: Only checks ORBs if current hour exactly matches ORB hour
- At 09:30, doesn't check 0900 ORB (not hour 9 anymore)
- At 10:05, doesn't check 1000 ORB
- At 23:10, doesn't check 2300 ORB

### Issue 2: Night ORB Has Same Problem

**File**: `trading_app/strategy_engine.py` line 547-583

**Current code** (similar exact-match logic):
```python
def _evaluate_night_orb(self) -> StrategyEvaluation:
    now = datetime.now(TZ_LOCAL)
    current_hour = now.hour
    current_min = now.minute

    # Check 23:00 ORB
    if current_hour == 23:  # ← EXACT HOUR MATCH
        return self._check_orb("2300")

    # Check 00:30 ORB
    if current_hour == 0 and current_min >= 30:  # ← LIMITED WINDOW
        return self._check_orb("0030")

    return StrategyEvaluation(
        state=StrategyState.INVALID,  # ← INVALID outside exact windows
        ...
    )
```

**Problem**: Same issue, plus 0030 only checked if >= 30 min (not after 01:00)

---

## Solution: Active Window Detection

### New Helper Function

Add to `strategy_engine.py`:

```python
def _get_active_orb_windows(self, current_time: datetime) -> List[str]:
    """
    Get list of ORB windows that should be active/displayed right now.

    Returns ORB names (e.g., ["2300", "0030"]) that are currently:
    - Forming (in 0-5 min window)
    - Ready (formed, watching for break)
    - Active (position open)
    - Not yet expired (within 3-hour window)

    Args:
        current_time: Current local time

    Returns:
        List of ORB names that should be evaluated/displayed
    """
    active_orbs = []

    # Define ORB expiration window (how long to keep showing it)
    EXPIRATION_HOURS = 3

    for orb_time in ORB_TIMES:
        orb_name = orb_time["name"]
        orb_hour = orb_time["hour"]
        orb_min = orb_time["min"]

        # Calculate ORB start time (today or yesterday)
        orb_start = current_time.replace(
            hour=orb_hour,
            minute=orb_min,
            second=0,
            microsecond=0
        )

        # Handle overnight ORBs (00:30 might be "today" relative to 23:00 "yesterday")
        if orb_hour < 12 and current_time.hour >= 12:
            # Early morning ORB, but we're in afternoon = yesterday's ORB expired
            pass
        elif orb_hour >= 12 and current_time.hour < 12:
            # Evening ORB, but we're in morning = yesterday's ORB might still be active
            orb_start = orb_start - timedelta(days=1)

        # Calculate expiration time
        orb_expiration = orb_start + timedelta(hours=EXPIRATION_HOURS)

        # Check if we're in active window
        if orb_start <= current_time < orb_expiration:
            active_orbs.append(orb_name)
            logger.debug(f"ORB {orb_name} active: started {orb_start}, expires {orb_expiration}")
        else:
            logger.debug(f"ORB {orb_name} NOT active: current={current_time}, start={orb_start}, expire={orb_expiration}")

    return active_orbs
```

### Updated _evaluate_night_orb

```python
def _evaluate_night_orb(self) -> StrategyEvaluation:
    """
    Evaluate Night ORB strategies (23:00, 00:30).

    FIXED: Now checks active window, not just exact hour.
    """
    now_local = datetime.now(TZ_LOCAL)

    # Get active ORB windows
    active_orbs = self._get_active_orb_windows(now_local)

    # Check night ORBs (2300, 0030)
    night_orbs = ["2300", "0030"]
    for orb_name in night_orbs:
        if orb_name in active_orbs:
            orb_result = self._check_orb(orb_name)
            if orb_result:
                return orb_result

    # No active night ORBs
    return StrategyEvaluation(
        strategy_name="NIGHT_ORB",
        priority=2,
        state=StrategyState.INVALID,
        action=ActionType.STAND_DOWN,
        reasons=["Outside night ORB windows (23:00-02:00, 00:30-03:30)"],
        next_instruction="Wait for 23:00 or 00:30"
    )
```

### Updated _evaluate_day_orb

```python
def _evaluate_day_orb(self) -> StrategyEvaluation:
    """
    Evaluate Day ORB strategies (09:00, 10:00, 11:00).

    FIXED: Now checks active window, not just exact hour.
    """
    now_local = datetime.now(TZ_LOCAL)

    # Get active ORB windows
    active_orbs = self._get_active_orb_windows(now_local)

    # Check day ORBs (0900, 1000, 1100)
    day_orbs = ["0900", "1000", "1100"]
    for orb_name in day_orbs:
        if orb_name in active_orbs:
            orb_result = self._check_orb(orb_name)
            if orb_result:
                return orb_result

    # No active day ORBs
    return StrategyEvaluation(
        strategy_name="DAY_ORB",
        priority=4,
        state=StrategyState.INVALID,
        action=ActionType.STAND_DOWN,
        reasons=["Outside day ORB windows"],
        next_instruction="Wait for 09:00, 10:00, or 11:00"
    )
```

---

## Display Enhancements

### Show Time Remaining in Window

**In UI** (app_trading_hub.py), show how long ORB window is valid:

```python
# After displaying strategy evaluation
if evaluation.state in [StrategyState.PREPARING, StrategyState.READY]:
    # Calculate time remaining in window
    orb_name = evaluation.strategy_name.split("_")[0]  # "2300" from "2300_ORB"
    orb_config = ORB_TIMES[orb_name]

    orb_start = now.replace(hour=orb_config["hour"], minute=orb_config["min"])
    orb_expiration = orb_start + timedelta(hours=3)

    time_remaining = (orb_expiration - now).total_seconds() / 60  # minutes

    if evaluation.state == StrategyState.PREPARING:
        # Forming phase
        orb_end = orb_start + timedelta(minutes=5)
        formation_remaining = (orb_end - now).total_seconds() / 60
        st.caption(f"⏱️ ORB forming: {formation_remaining:.1f} min remaining")
    elif evaluation.state == StrategyState.READY:
        # Ready phase (watching for break)
        st.caption(f"⏱️ Window active for {time_remaining:.0f} more minutes")
```

### Show Multiple Active ORBs

**Enhancement**: Display ALL active ORBs, not just highest priority

```python
# Get all active ORBs
active_orbs = strategy_engine._get_active_orb_windows(datetime.now(TZ_LOCAL))

if len(active_orbs) > 1:
    st.info(f"📊 Multiple ORB windows active: {', '.join(active_orbs)}")

    # Show each ORB in separate card
    for orb_name in active_orbs:
        orb_eval = strategy_engine._check_orb(orb_name)
        if orb_eval:
            with st.expander(f"{orb_name} ORB - {orb_eval.state.value}", expanded=(orb_eval.state == StrategyState.READY)):
                st.markdown(f"**Status**: {orb_eval.state.value}")
                for reason in orb_eval.reasons:
                    st.markdown(f"- {reason}")
```

---

## Edge Cases to Handle

### Case 1: Multiple Overlapping ORBs

**Scenario**: At 00:40
- 2300 ORB started at 23:00 (active for 1h 40m, still valid)
- 0030 ORB started at 00:30 (active for 10m)
- Both should display!

**Solution**: Show both, prioritize based on state
- If 2300 is ACTIVE (position open), show it prominently
- If 0030 is READY (breakout detected), show it prominently
- Otherwise show both equally

### Case 2: Day Transition (23:00 → 00:30)

**Scenario**: At 00:45
- Yesterday's 2300 ORB (started 1h 45m ago) - still active
- Today's 0030 ORB (started 15m ago) - also active

**Solution**: Use adjusted date calculation in `_get_active_orb_windows`
- Check if ORB started "yesterday" but still in 3-hour window
- Label appropriately: "2300 ORB (1h 45m ago)"

### Case 3: Weekend/Holiday Gaps

**Scenario**: Friday 23:00 → Monday 02:00 (market closed weekend)
- 2300 ORB expired (not valid after 3 hours)
- Don't show stale ORBs from Friday

**Solution**: Already handled by 3-hour expiration
- Friday 23:00 + 3h = Saturday 02:00 (expired)
- Monday 02:00 = no active ORBs (correct)

---

## Testing Scenarios

### Test 1: 2300 ORB Lifecycle
```
23:00 - Should show "2300 ORB FORMING"
23:02 - Should show "2300 ORB FORMING (2/5 min)"
23:05 - Should show "2300 ORB READY"
23:15 - Should show "2300 ORB READY" (still valid)
00:00 - Should show "2300 ORB READY" (still valid)
00:30 - Should show BOTH "2300 ORB" and "0030 ORB"
02:00 - Should show BOTH (if not expired)
02:01 - Should show only "0030 ORB" (2300 expired at 02:00)
```

### Test 2: Day ORB Lifecycle
```
09:00 - Should show "0900 ORB FORMING"
09:10 - Should show "0900 ORB READY" (not disappeared!)
10:00 - Should show BOTH "0900 ORB" and "1000 ORB"
11:00 - Should show 0900, 1000, 1100 (if all still valid)
12:00 - Should show only 1100 (0900 expired at 12:00, 1000 at 13:00)
```

### Test 3: Overnight Transition
```
23:00 - Show 2300 ORB
23:59 - Show 2300 ORB (still valid)
00:00 - Show 2300 ORB (still valid, 1h elapsed)
00:30 - Show 2300 ORB + 0030 ORB (both)
01:00 - Show both (still in windows)
02:00 - Show only 0030 (2300 expired)
03:30 - Show nothing (0030 expired)
```

---

## Implementation Checklist

- [ ] Add `_get_active_orb_windows()` to strategy_engine.py
- [ ] Update `_evaluate_night_orb()` to use active windows
- [ ] Update `_evaluate_day_orb()` to use active windows
- [ ] Add time remaining display to UI
- [ ] Handle multiple active ORBs in UI
- [ ] Test overnight transition (23:00 → 00:30)
- [ ] Test 3-hour expiration
- [ ] Test day ORB persistence (09:00 ORB visible at 09:30)
- [ ] Add logging for active window detection
- [ ] Update tests (test_app_sync.py) to cover window logic
- [ ] Document new behavior in CLAUDE.md

---

## Rollout Strategy

### Phase 1: Add Window Detection (No UI Changes Yet)
1. Add `_get_active_orb_windows()` function
2. Add logging to see what it returns
3. Test in various time scenarios
4. **Don't change evaluation logic yet** (just observe)

### Phase 2: Update Strategy Engine
1. Change `_evaluate_night_orb()` to use windows
2. Change `_evaluate_day_orb()` to use windows
3. Test that strategies persist correctly
4. Verify no regressions (existing behavior still works)

### Phase 3: UI Enhancements
1. Add time remaining display
2. Add multiple ORB display
3. Polish visual presentation
4. User testing

### Phase 4: Documentation
1. Update CLAUDE.md with window logic
2. Add examples to user docs
3. Update test suite

---

## Expected Behavior After Fix

**User at 23:10**:
```
┌─────────────────────────────────────────────────┐
│ 2300 ORB - READY                               │
│ ⏱️ Window active for 170 more minutes          │
│                                                 │
│ Status: READY - Watching for breakout          │
│ - 2300 ORB formed (High: $2655, Low: $2650)   │
│ - ORB size filter PASSED                       │
│ - Waiting for first close outside range        │
│ - B tier setup (72% win rate, +0.34R avg)     │
│                                                 │
│ Next: Enter long if close > $2655             │
│ Or: Enter short if close < $2650              │
└─────────────────────────────────────────────────┘
```

**User at 00:35** (overlapping windows):
```
┌─────────────────────────────────────────────────┐
│ 📊 Multiple ORB windows active: 2300, 0030     │
└─────────────────────────────────────────────────┘

▼ 2300 ORB - READY (1h 35m ago)
  Status: READY - Watching for breakout
  ...

▼ 0030 ORB - FORMING (5 min remaining)
  Status: FORMING - ORB building
  ...
```

---

## Priority

**HIGH** - This is a critical usability issue

Without this fix:
- User misses trades (doesn't see active setups)
- Confusion ("Where did my setup go?")
- Wrong impression (thinks strategy engine isn't working)

With this fix:
- Clear visibility of all active ORB windows
- User knows when to act
- Multiple ORBs handled correctly
- Time pressure visible ("170 min remaining")

---

## Contact

Questions about timing logic?
- This file: Complete timing fix specification
- `strategy_engine.py`: Current implementation
- `config.py`: ORB_TIMES definition
- `CLAUDE.md`: ORB window definitions

**Remember**: ORBs are active for 3 hours, not just at exact start time!
