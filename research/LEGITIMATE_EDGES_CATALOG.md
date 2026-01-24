# Legitimate Edges Catalog

**Created**: 2026-01-24
**Authority**: CLAUDE.md, res.txt (verify everything yourself)
**Purpose**: Document ONLY verified edges with statistical evidence

**Criteria for inclusion**:
1. Statistical significance (p < 0.05 or clear visual evidence)
2. Sample size >= 30 per group
3. Makes logical sense (market microstructure)
4. Testable and reproducible

---

## Edge #1: Direction Alignment (VERIFIED)

**Pattern**: Liquidity sweep direction must ALIGN with ORB break direction

**Discovered**: 2026-01-24 (tested from first principles)

### Performance Data (1800 ORB):

| Sweep Type | ORB Direction | Trades | Win Rate | Avg R | Status |
|------------|---------------|--------|----------|-------|--------|
| L1_SWEEP_HIGH (bullish) | UP (aligned) | 155 | 63.2% | +0.273R | ✅ STRONG |
| L1_SWEEP_HIGH (bullish) | DOWN (counter) | 77 | 32.5% | -0.351R | ❌ AVOID |
| L2_SWEEP_LOW (bearish) | DOWN (aligned) | 94 | 63.8% | +0.277R | ✅ STRONG |
| L2_SWEEP_LOW (bearish) | UP (counter) | 71 | 33.8% | -0.314R | ❌ AVOID |

### Key Metrics:
- **Aligned trades**: ~63% WR, +0.27R avg
- **Counter trades**: ~33% WR, -0.33R avg
- **Difference**: 30% WR swing, 0.60R swing
- **Sample size**: 155 + 94 = 249 aligned trades (sufficient)

### Statistical Evidence:
- Clear separation: 63% vs 33% win rate
- Large effect: 0.60R difference between aligned and counter
- Consistent across both directions (high and low sweeps)
- Sample sizes adequate (71-155 trades per group)

### Market Logic:
**Why this works**:
- London sweep high = bullish liquidity grab → bias UP
- London sweep low = bearish liquidity grab → bias DOWN
- ORB breakout WITH bias = higher follow-through
- ORB breakout AGAINST bias = lower follow-through (fighting liquidity)

### Trading Rules:
1. **TAKE**: L1_SWEEP_HIGH + ORB breaks UP (aligned)
2. **TAKE**: L2_SWEEP_LOW + ORB breaks DOWN (aligned)
3. **AVOID**: L1_SWEEP_HIGH + ORB breaks DOWN (counter)
4. **AVOID**: L2_SWEEP_LOW + ORB breaks UP (counter)

### Implementation:
```python
# Check london_type_code and orb_break_dir
if london_type_code == 'L1_SWEEP_HIGH' and orb_break_dir == 'UP':
    # ALIGNED - take trade
    edge = "STRONG"
elif london_type_code == 'L2_SWEEP_LOW' and orb_break_dir == 'DOWN':
    # ALIGNED - take trade
    edge = "STRONG"
elif (london_type_code == 'L1_SWEEP_HIGH' and orb_break_dir == 'DOWN') or \
     (london_type_code == 'L2_SWEEP_LOW' and orb_break_dir == 'UP'):
    # COUNTER - avoid trade
    edge = "NEGATIVE"
else:
    # No clear liquidity signal
    edge = "NEUTRAL"
```

### Status: ✅ VERIFIED
- Tested on: daily_features_v2 (740 MGC days)
- ORB tested: 1800 (London sweep happens AS ORB forms)
- Confidence: HIGH (clear pattern, adequate sample size)
- Authority: First principles testing (res.txt compliant)

---

## Edge #2: [To be discovered]

**Pattern**: TBD

Continue testing hypotheses...

---

## Testing Log

### 2026-01-24: Initial Tests

**TEST 1: London sweep (any) vs no sweep**
- Result: No clear edge (SWEEP: 52.1% WR, CONSOLIDATION: 47.8% WR)
- Conclusion: Direction MATTERS, not just presence of sweep

**TEST 2: Direction alignment** ✅
- Result: STRONG edge when aligned (63% vs 33% WR)
- Conclusion: VERIFIED edge, should be used

**TEST 3: Liquidity freshness (1800 vs 2300 ORB)**
- Result: Marginal difference (1800: 52.1% WR, 2300: 46.6% WR)
- Conclusion: Weak evidence, needs more specific test

**TEST 4: Sequential sweeps (cascade)**
- Result: No clear edge (Sequential: 48.6% WR, Single: 46.9% WR)
- Conclusion: Simple "any sequential sweep" not enough - need specific conditions

---

## Next Hypotheses to Test

1. **Aligned sweep + specific ORB times** (1000, 1800, 2300)
2. **Aligned sweep + volatility regime** (low vol vs high vol)
3. **Aligned sweep + day of week** (Monday vs Friday)
4. **Aligned sweep + liquidity spacing** (close levels vs far levels)
5. **Specific cascade patterns** (not just any sequential sweep)

---

## Implementation Priority

### Tier 1: Ready to Implement
- **Direction Alignment** (Edge #1) - VERIFIED, ready for production

### Tier 2: Needs More Testing
- Liquidity freshness (marginal evidence)
- Cascade patterns (need specific conditions)

### Tier 3: Not Verified
- Simple sweep presence (no evidence)
- Simple sequential sweeps (no evidence)

---

**Authority**: CLAUDE.md (daily_features_v2 canonical)
**Constraint**: res.txt (verify everything yourself)
**Status**: 1 verified edge, continue testing
