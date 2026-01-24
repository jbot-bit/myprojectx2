# Master TODO: App Improvements

**Date**: 2026-01-23
**Status**: Prioritized action items

---

## CRITICAL (Do First)

### 1. Fix ORB Timing Display ⚡ HIGH PRIORITY
**Problem**: At 23:10, can't see 2300 ORB strategies (disappears after 23:00)
**Impact**: Users miss trades, confusion about what's active
**File**: `TIMING_DISPLAY_FIX.md`
**Effort**: 4-6 hours
**Risk**: Medium (changes strategy engine evaluation logic)

**Tasks**:
- [ ] Add `_get_active_orb_windows()` to strategy_engine.py
- [ ] Update `_evaluate_night_orb()` to use window detection
- [ ] Update `_evaluate_day_orb()` to use window detection
- [ ] Test overnight transitions (23:00 → 00:30)
- [ ] Test 3-hour expiration logic
- [ ] Add time remaining display to UI
- [ ] Test with multiple overlapping ORBs

**Validation**:
```bash
# Test at different times
# 23:10 - Should show 2300 ORB
# 00:35 - Should show both 2300 and 0030 ORBs
# 09:15 - Should show 0900 ORB (not disappeared)
```

---

### 2. AI Memory Unification 🔧 HIGH PRIORITY
**Problem**: Uploads, chat, memory are disconnected. App is spammy/repetitive.
**Impact**: Poor user experience, high token costs, conversation doesn't flow
**File**: `AI_UNIFICATION_PLAN.md`
**Effort**: 1-2 days (phased approach)
**Risk**: Low-Medium (incremental changes)

**Phase 1: Upload Integration** (2-3 hours):
- [ ] Save image upload analysis to conversation memory (app_trading_hub.py line ~1335)
- [ ] Save CSV upload analysis to conversation memory (app_trading_hub.py line ~1307)
- [ ] Update chat history in UI to show uploads
- [ ] Test: Upload → Close app → Reopen → Should see upload in history

**Phase 2: Smart Context** (4-5 hours):
- [ ] Add `_build_smart_context()` to ai_assistant.py
- [ ] Update `_build_evidence_pack()` to use smart context
- [ ] Test token reduction (measure before/after)
- [ ] Verify no information loss

**Phase 3: Conversation Flow** (2-3 hours):
- [ ] Update ai_guard.py system prompt for continuity
- [ ] Test: "What about that chart?" should work
- [ ] Test: AI references past conversation naturally

**Phase 4: Upload Preview** (1-2 hours):
- [ ] Add upload icons to chat messages (📸 for images, 📊 for CSV)
- [ ] Polish visual presentation
- [ ] Test on mobile

**Validation**:
```bash
# Test conversation continuity
1. Upload chart
2. Ask question about it
3. Ask follow-up using "it" or "that"
4. AI should maintain context

# Test memory persistence
1. Close browser
2. Reopen app
3. Past uploads should be visible
```

---

## IMPORTANT (Do Soon)

### 3. Database Lock Issue 🔒
**Problem**: test_app_sync.py fails (PID 36612 holding lock)
**Impact**: Can't verify database/config synchronization
**File**: N/A (operational issue)
**Effort**: 5 minutes
**Risk**: None

**Tasks**:
- [ ] Close process PID 36612 (likely Streamlit app or Jupyter)
- [ ] Run `python test_app_sync.py` to verify system health
- [ ] Document which processes lock database

**Validation**:
```bash
python test_app_sync.py
# Should pass all tests
```

---

### 4. Session Logic Extensions 📅 DEFERRED
**Problem**: SessionLiquidity built but not integrated
**Impact**: Missing advanced features (cascades, sweeps)
**File**: `TODO_SESSION_LOGIC.md`, `SAFE_SESSION_EXTENSION_STRATEGY.md`
**Effort**: 1-2 weeks (multiple phases)
**Risk**: Medium (needs careful integration)

**Deferred until**: After timing fix and AI unification complete

**Future Tasks**:
- [ ] Add SessionLiquidity display panel (display only)
- [ ] Implement london_bias condition
- [ ] Implement pre_orb_trend condition
- [ ] Advanced cascade pattern integration

---

## NICE TO HAVE (Backlog)

### 5. Documentation Updates 📝
**Tasks**:
- [ ] Update CLAUDE.md with ORB window logic
- [ ] Document AI memory architecture
- [ ] Add troubleshooting guide for database locks
- [ ] Create user guide for uploads

### 6. Performance Optimization ⚡
**Tasks**:
- [ ] Measure Evidence Pack token usage (before/after smart context)
- [ ] Add caching for session ranges (avoid repeated queries)
- [ ] Optimize database queries (add indexes if needed)
- [ ] Profile app startup time

### 7. UI Polish 🎨
**Tasks**:
- [ ] Add loading skeletons (better than spinners)
- [ ] Improve mobile responsiveness
- [ ] Add keyboard shortcuts
- [ ] Dark mode support

---

## Implementation Order

### Week 1 (Critical Fixes)
**Days 1-2**: ORB Timing Fix
- Implement active window detection
- Test thoroughly (overnight transitions, multiple ORBs)
- Deploy to production

**Days 3-4**: AI Memory Phase 1 (Upload Integration)
- Connect uploads to memory
- Test persistence
- Verify no regressions

**Day 5**: Validation & Testing
- Run full test suite
- User acceptance testing
- Fix any issues found

### Week 2 (AI Improvements)
**Days 1-2**: AI Memory Phase 2 (Smart Context)
- Implement context reduction
- Measure token savings
- A/B test responses

**Days 3-4**: AI Memory Phase 3 (Conversation Flow)
- Update prompts
- Test continuity
- Polish user experience

**Day 5**: Documentation & Cleanup
- Update docs
- Code cleanup
- Prepare for next phase

### Week 3+ (Future Enhancements)
- Session logic extensions
- Performance optimization
- UI polish
- Additional features

---

## Success Metrics

### After ORB Timing Fix:
- [ ] 2300 ORB visible at 23:10 ✓
- [ ] Multiple ORBs display at 00:35 ✓
- [ ] Time remaining shown in UI ✓
- [ ] No missed trades due to disappearing strategies ✓

### After AI Unification:
- [ ] Uploads persist in conversation ✓
- [ ] Token usage reduced by 50%+ ✓
- [ ] AI references past context ✓
- [ ] No "AI forgot" complaints ✓
- [ ] Conversation flows naturally ✓

### After Database Fix:
- [ ] test_app_sync.py passes ✓
- [ ] Config matches database ✓
- [ ] No lock errors ✓

---

## Daily Checklist

Before starting work:
- [ ] Close any Streamlit processes
- [ ] Run `python test_app_sync.py` to check system health
- [ ] Check git status for uncommitted changes

After making changes:
- [ ] Run relevant tests
- [ ] Check app starts without errors
- [ ] Commit with clear message
- [ ] Update relevant documentation

Before deploying:
- [ ] Full test suite passes
- [ ] Manual testing in UI
- [ ] No errors in logs
- [ ] User acceptance complete

---

## Risk Management

### Rollback Plan
If ORB timing fix causes issues:
1. Revert strategy_engine.py changes
2. Return to exact-hour matching logic
3. Document issue for future attempt

If AI unification causes issues:
1. Disable smart context with env var: `USE_SMART_CONTEXT=0`
2. Revert to legacy Evidence Pack building
3. Investigate specific failure

### Backup Strategy
- Keep `_build_evidence_pack_legacy()` as fallback
- Feature flags for gradual rollout
- Monitor error logs closely
- User feedback channels open

---

## Questions to Resolve

1. **ORB Window Duration**: 3 hours correct? Or adjust per ORB?
   - **Answer pending**: Test with real trading, adjust if needed

2. **AI Context Size**: How many messages to keep?
   - **Recommendation**: 10-15 recent messages (balance context vs spam)

3. **Upload Thumbnails**: Show in chat or separate section?
   - **Recommendation**: Show in main chat (unified experience)

4. **Session Logic**: When to integrate?
   - **Answer**: After critical fixes complete (Week 3+)

---

## Communication

### Daily Standup (Optional)
- What did I complete yesterday?
- What am I working on today?
- Any blockers?

### Weekly Review
- What shipped this week?
- What metrics improved?
- What's planned for next week?
- Any learnings or issues?

---

## Reference Files

- `TIMING_DISPLAY_FIX.md` - Complete ORB window specification
- `AI_UNIFICATION_PLAN.md` - AI memory unification guide
- `SAFE_SESSION_EXTENSION_STRATEGY.md` - Session logic integration strategy
- `TODO_SESSION_LOGIC.md` - Deferred session tasks
- `CLAUDE.md` - Project authority and guidelines
- `test_app_sync.py` - Critical validation script

---

## Notes

- Follow CLAUDE.md as authority for all decisions
- Always run test_app_sync.py after database changes
- Gradual rollout > big bang deployment
- User feedback is critical
- Document everything

---

**Last Updated**: 2026-01-23
**Next Review**: After Week 1 completion
