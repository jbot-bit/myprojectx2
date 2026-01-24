# TODO: Session Logic Extensions (For Later)

**Status**: DEFERRED - Focus on AI memory unification first
**Created**: 2026-01-23

---

## Deferred Tasks

### 1. Add SessionLiquidity Display Panel
- [ ] Add expander to app_trading_hub.py
- [ ] Display sweep status and cascade patterns
- [ ] Show directional bias with reasoning
- [ ] Display only (no automated decisions)
- **Effort**: 1-2 days
- **Risk**: Low

### 2. Implement london_bias Condition
- [ ] Add get_london_bias() to market_state.py
- [ ] Import london_bias setups to database
- [ ] Update setup_detector.get_conditional_setups()
- [ ] Add UI rendering in render_conditional_edges.py
- [ ] Test with test_conditional_edges.py
- **Effort**: 3-5 days
- **Risk**: Medium

### 3. Implement pre_orb_trend Condition
- [ ] Add get_pre_orb_trend() to market_state.py
- [ ] Handle intraday bar loading
- [ ] Verify zero lookahead (timing sensitive)
- [ ] Import pre_orb_trend setups
- [ ] Backtest extensively
- **Effort**: 1-2 weeks
- **Risk**: Medium-High

### 4. Advanced Integration
- [ ] Use sweeps for position sizing hints
- [ ] Add cascade pattern alerts
- [ ] Multi-condition setups (asia_bias + london_bias + pre_orb_trend)
- **Effort**: 2-4 weeks
- **Risk**: High

---

## Reference Documentation

See `SAFE_SESSION_EXTENSION_STRATEGY.md` for:
- Current integration state
- Safe extension patterns
- Critical safety rules
- Verification procedures
- What NOT to do

---

## Notes

- All session logic infrastructure exists and works
- asia_bias conditional edges working in production (38 setups)
- SessionLiquidity class built but unused
- Focus on AI memory unification before extending session logic
- When resuming: Start with SessionLiquidity display (lowest risk)
