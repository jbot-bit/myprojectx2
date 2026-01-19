# NQ (Micro E-mini Nasdaq) Validation Plan

**Created:** 2026-01-13
**Status:** IN PROGRESS
**Objective:** Validate all MGC strategies on NQ and create production-ready NQ configuration

---

## Executive Summary

This plan validates whether the MGC trading strategies work on NQ (Micro E-mini Nasdaq). NQ has different characteristics than Gold:
- **Higher volatility** (typically 2-3x Gold's movement)
- **Different liquidity patterns**
- **Tech-driven vs commodity**
- **Different session behaviors**

We'll test all 5 strategies with MGC parameters, then optimize for NQ-specific characteristics.

---

## Phase 1: Data Preparation

### Step 1.1: Check Existing NQ Data
```bash
python -c "
import duckdb
con = duckdb.connect('gold.db')
result = con.execute('''
    SELECT COUNT(*), MIN(ts_utc), MAX(ts_utc)
    FROM bars_1m
    WHERE symbol = 'NQ'
''').fetchone()
print(f'NQ bars: {result[0]}')
print(f'Range: {result[1]} to {result[2]}')
con.close()
"
```

### Step 1.2: Backfill NQ Data (if needed)
**Goal:** Minimum 2 years (2024-01-01 to 2026-01-13)

**Method:**
```bash
python backfill_databento_continuous.py 2024-01-01 2026-01-13 --symbol NQ
```

**Expected:**
- ~500,000 bars (700 days × ~720 bars/day)
- Continuous front-month contract stitching
- Gaps on weekends/holidays

### Step 1.3: Build NQ Features
```bash
python build_daily_features_v2.py --symbol NQ
```

**Creates:** `daily_features_v2_nq` table with:
- All 6 ORBs (0900, 1000, 1100, 1800, 2300, 0030)
- Session high/low (Asia, London, NY)
- PRE blocks
- ATR(20) for filters

---

## Phase 2: Baseline ORB Testing

### Objective
Test all 6 ORBs with **MGC parameters** to establish baseline.

### Step 2.1: Configure Test Parameters
**Use MGC settings as starting point:**

| ORB | RR | SL Mode | Current MGC Result |
|-----|----|---------|--------------------|
| 0900 | 1.0 | FULL | +0.431R, 57.2% WR |
| 1000 | 3.0 | FULL | +0.342R, 56.8% WR |
| 1100 | 1.0 | FULL | +0.449R, 58.1% WR |
| 1800 | 1.0 | HALF | +0.425R, 56.9% WR |
| 2300 | 1.0 | HALF | +0.387R, 48.9% WR |
| 0030 | 1.0 | HALF | +0.231R, 43.5% WR |

### Step 2.2: Run Baseline Backtests
```bash
# Test with 1-minute execution, no filters
python backtest_orb_exec_1m_nq.py --rr-grid "1.0,1.5,2.0,2.5,3.0" --no-filters
```

**Expected Output:**
- Win rates by ORB
- Expectancy (R) by ORB
- Frequency (% days with valid setups)
- MAE/MFE distributions

**Success Criteria:**
- Overall expectancy > +0.20R (acceptable)
- Overall expectancy > +0.35R (good, similar to MGC)
- Win rates 50-60% range
- No single ORB with < -0.10R (losing badly)

---

## Phase 3: ORB Size Filter Optimization

### Objective
NQ moves differently than Gold - need to test exhaustion filters.

### Step 3.1: Analyze ORB Size Distributions
```python
# For each ORB, analyze:
# - ORB size vs ATR(20)
# - Win rate by ORB size quintile
# - Expectancy by ORB size quintile
```

### Step 3.2: Test Filter Thresholds
**For each ORB, test exclusion if:**
- `orb_size > threshold * ATR(20)`

**Test thresholds:** 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20

### Step 3.3: Validate Improvements
**Keep filter only if:**
1. Improvement > +5% expectancy
2. Frequency > 10% (not over-filtering)
3. No lookahead bias (ATR computed before ORB)

**Expected Result:**
- NQ likely needs HIGHER thresholds (more volatile)
- Example: MGC 0030 uses 0.112, NQ might use 0.15-0.20

---

## Phase 4: Cascade Strategy Validation

### Objective
Test multi-liquidity cascade on NQ.

### Step 4.1: Analyze Gap Distributions
```sql
-- Count days with large gaps
SELECT
    COUNT(*) as total_days,
    SUM(CASE WHEN london_high - asia_high > 9.5 THEN 1 ELSE 0 END) as upside_cascades,
    SUM(CASE WHEN asia_low - london_low > 9.5 THEN 1 ELSE 0 END) as downside_cascades,
    AVG(london_high - asia_high) as avg_upside_gap,
    AVG(asia_low - london_low) as avg_downside_gap
FROM daily_features_v2_nq
WHERE london_high > asia_high OR london_low < asia_low
```

### Step 4.2: Test Cascade Parameters
**MGC uses:**
- Min gap: 9.5 points
- Stop: 0.5 × gap
- Target: 2.0 × gap (effective 4R)

**NQ test:**
- Min gap: Test 10, 15, 20, 25 points
- Stop/Target ratios: Same (0.5/2.0) or adjust
- Acceptance failure: 3 bars (same as MGC)

### Step 4.3: Expected Results
**Success:**
- Frequency 5-15% (similar to MGC 9.3%)
- Expectancy > +1.0R (MGC is +1.95R)
- Win rate irrelevant (risk/reward driven)

**Failure:**
- Frequency < 3% (too rare to trade)
- Expectancy < +0.50R (not worth complexity)

---

## Phase 5: Single Liquidity Validation

### Objective
Test London level sweeps at 23:00.

### Step 5.1: Test Current Parameters
```python
# Pattern: NY sweeps London high/low at 23:00, fails to hold
# Stop: 2pts beyond sweep
# Target: Opposite London level
```

### Step 5.2: Analyze Results
**MGC baseline:**
- +1.44R avg
- 16% frequency
- 33.7% win rate

**NQ expectations:**
- May need wider stops (2pts → 3-4pts)
- Frequency likely similar (session structure same)
- Win rate may be lower (higher volatility)

---

## Phase 6: Parameter Optimization

### Step 6.1: RR Grid Search
For each ORB, test RR targets:
- 1.0, 1.5, 2.0, 2.5, 3.0, 4.0

**Find optimal:**
- Max expectancy (R per trade)
- Acceptable win rate (> 40%)

### Step 6.2: Stop Loss Mode Testing
Test FULL vs HALF for each ORB:
- FULL: Stop at opposite ORB boundary
- HALF: Stop at ORB midpoint

**NQ may prefer FULL** (higher volatility = wider stops)

---

## Phase 7: Create NQ Configuration

### Step 7.1: Document Optimal Parameters
Create `NQ_OPTIMAL_PARAMS.md` with:
- Best RR by ORB
- SL mode by ORB
- ORB size filters (if beneficial)
- Cascade parameters
- Single liquidity parameters

### Step 7.2: Update config.py
Add NQ-specific settings:
```python
# Instrument-specific parameters
INSTRUMENT_CONFIGS = {
    "MGC": {
        "orbs": {...},
        "filters": {...},
        "cascade_min_gap": 9.5,
        "tick_value": 10.0,
        "tick_size": 0.1
    },
    "NQ": {
        "orbs": {...},  # From testing
        "filters": {...},  # From testing
        "cascade_min_gap": 15.0,  # Example, from testing
        "tick_value": 2.0,
        "tick_size": 0.25
    }
}
```

### Step 7.3: Update App
Modify app to load instrument-specific configs:
```python
# app_trading_hub.py
config = INSTRUMENT_CONFIGS[symbol]
```

---

## Phase 8: Validation Testing

### Step 8.1: Out-of-Sample Test
**Hold out last 60 days (Dec 2025 - Jan 2026)**

Test optimized parameters on held-out data:
- Expected: 80-90% of in-sample performance
- If < 70%, parameters overfit

### Step 8.2: Conservative Execution Test
**Same as MGC:**
- +2 minute entry delay
- Conservative same-bar resolution
- Expected decline: 10-15%

### Step 8.3: Robustness Tests
- Parameter sensitivity (±20% on thresholds)
- Rolling window analysis (quarterly results)
- Drawdown analysis

---

## Phase 9: Production Deployment

### Step 9.1: Update Trading App
- [x] Data loader supports NQ
- [ ] Config loads NQ-specific parameters
- [ ] UI displays NQ contract specs correctly
- [ ] Position sizing uses NQ tick value ($2/tick)

### Step 9.2: Create NQ Documentation
- Strategy performance summary
- Parameter rationale
- Risk limits
- Trade management rules

### Step 9.3: Live Testing Checklist
- [ ] NQ data backfilled
- [ ] Features built
- [ ] Strategies validated
- [ ] App tested with NQ
- [ ] Position sizing verified
- [ ] Risk limits appropriate

---

## Success Criteria

### Minimum Viable (Go/No-Go Decision)
- [ ] Overall expectancy > +0.20R per trade
- [ ] At least 3 ORBs with positive expectancy
- [ ] Cascade OR Single Liquidity works (one higher-tier strategy)
- [ ] No critical lookahead bias detected
- [ ] Out-of-sample validation > 70% of in-sample

### Production Ready
- [ ] Overall expectancy > +0.35R (similar to MGC)
- [ ] At least 4 ORBs with positive expectancy
- [ ] Both Cascade AND Single Liquidity work
- [ ] Conservative execution test passes (> 85% in-sample)
- [ ] Robustness tests show stable performance

### Ideal Target
- [ ] Overall expectancy > +0.50R (better than MGC)
- [ ] All 6 ORBs positive or breakeven
- [ ] Cascade strategy > +1.0R
- [ ] ORB size filters improve > 10%
- [ ] Ready for live trading

---

## Timeline Estimate

| Phase | Task | Est. Time |
|-------|------|-----------|
| 1 | Data preparation | 2-4 hours |
| 2 | Baseline ORB tests | 1-2 hours |
| 3 | Filter optimization | 2-3 hours |
| 4 | Cascade validation | 1-2 hours |
| 5 | Single liq validation | 1 hour |
| 6 | Parameter optimization | 2-3 hours |
| 7 | Configuration | 1 hour |
| 8 | Validation testing | 2 hours |
| 9 | Production deployment | 1-2 hours |
| **Total** | | **13-20 hours** |

---

## Risk Assessment

### High Risk Areas
1. **NQ volatility too high** → Stops get hit too often → Poor win rates
2. **Different session characteristics** → MGC patterns don't translate
3. **Overfitting** → In-sample great, out-of-sample fails

### Mitigation
1. Test wider stops (FULL SL mode)
2. Test different RR ratios (may need lower targets)
3. Strict out-of-sample validation
4. Parameter sensitivity analysis

### Fallback Plan
If NQ doesn't validate:
- Continue with MGC only (proven edge)
- Consider ES (S&P 500) instead
- Test on other gold contracts (GC full-size)

---

## Expected Differences: NQ vs MGC

| Aspect | MGC | NQ (Expected) |
|--------|-----|---------------|
| Volatility | Moderate | High (2-3x) |
| ORB Size | 2-8 ticks | 5-20 ticks |
| Cascade Gaps | 9.5+ pts (10+ ticks) | 15-25 pts (15-25 ticks) |
| Win Rates | 50-58% | 45-55% (wider stops) |
| Best Session | London (1800) | NY (2300/0030) likely |
| Filter Thresholds | 0.08-0.15 × ATR | 0.12-0.20 × ATR |
| Optimal RR | 1.0-3.0 | 1.5-2.0 (balance) |

---

## Deliverables

1. **NQ_BASELINE_RESULTS.md** - Phase 2 results
2. **NQ_FILTER_ANALYSIS.md** - Phase 3 optimization
3. **NQ_CASCADE_VALIDATION.md** - Phase 4 results
4. **NQ_OPTIMAL_PARAMS.md** - Phase 7 configuration
5. **NQ_VALIDATION_REPORT.md** - Phase 8 final report
6. Updated **config.py** with NQ settings
7. Updated **APP_PRODUCTION_STATUS.md** with NQ

---

## Next Steps

1. ✅ Create this validation plan
2. ⏳ Check if NQ data exists in gold.db
3. ⏳ Backfill NQ data if needed
4. ⏳ Run baseline backtests
5. ⏳ Continue through phases

**Status:** Ready to execute Phase 1
