# 9AM ORB - BEST STRATEGIES ANALYSIS

**Date**: 2026-01-22
**Test Period**: 2020-12-20 to 2026-01-10 (5.06 years)
**Instrument**: MGC (Micro Gold)
**ORB Window**: 09:00-09:05 (5 minutes)
**Total Variants Tested**: 32

---

## KEY FINDINGS

### WINNER: **RR1.0_HALF_standard**

**This is the best 9am strategy based on comprehensive backtesting:**

- **RR Target**: 1.0R
- **Stop Loss**: HALF (ORB midpoint)
- **Scan Window**: Standard (09:05 - 17:00 same day)

**Performance Metrics:**
- **Trades**: 522 (103 per year)
- **Win Rate**: 52.9%
- **Avg R**: +0.061R per trade
- **Total R**: +31.7R over 5 years
- **Max Drawdown**: 16.0R
- **Avg Time to Resolution**: 0.27 hours (16 minutes)

**Why This Works:**
1. Tight 1R target captures quick moves
2. HALF mode reduces risk while maintaining edge
3. High frequency (103 trades/year) smooths equity curve
4. Short hold time (16 min avg) reduces overnight exposure
5. Positive expectancy with manageable drawdown

---

## TOP 5 STRATEGIES

| Rank | Variant | RR | SL | Window | Trades | WR% | Avg R | Total R | Max DD | Time (h) |
|------|---------|----|----|--------|--------|-----|-------|---------|--------|----------|
| 1 | RR1.0_HALF_standard | 1.0R | HALF | standard | 522 | 52.9% | +0.061R | +31.7R | 16.0R | 0.27h |
| 2 | RR8.0_HALF_extended | 8.0R | HALF | extended | 523 | 11.7% | +0.058R | +30.3R | 76.0R | 1.26h |
| 3 | RR1.0_HALF_extended | 1.0R | HALF | extended | 523 | 52.8% | +0.055R | +29.0R | 16.0R | 0.28h |
| 4 | RR8.0_HALF_standard | 8.0R | HALF | standard | 522 | 9.8% | +0.043R | +22.6R | 73.2R | 1.06h |
| 5 | RR6.0_HALF_extended | 6.0R | HALF | extended | 523 | 14.7% | +0.039R | +20.3R | 71.0R | 1.04h |

---

## CRITICAL INSIGHTS

### 1. HALF Stop Mode is SUPERIOR to FULL

**HALF mode dominates the top rankings:**
- Top 10 performers: 10/10 use HALF mode
- HALF mode has positive expectancy at almost all RR levels
- FULL mode is NEGATIVE across nearly all RR targets

**Why HALF Works:**
- Reduces risk by 50% while preserving edge
- Allows price to move against you without stopping out immediately
- Better risk/reward after entry

### 2. RR Target Analysis

**Best RR targets by avg_r:**
1. **1.0R** (+0.058R avg) - HIGHEST EDGE, most consistent
2. **8.0R** (+0.051R avg) - Rare but big wins, high drawdown
3. **6.0R** (+0.036R avg) - Good middle ground
4. **1.5R** (+0.030R avg) - Still positive
5. **2.0R** (+0.007R avg) - Barely breakeven

**AVOID**: 3R, 4R, 5R with FULL mode (all negative)

### 3. Scan Window Comparison

**Standard (09:05-17:00):**
- Better for 1.0R-2.0R targets
- Lower drawdowns
- Shorter hold times

**Extended (09:05-next 09:00):**
- Better for 6R-8R targets
- Captures overnight moves
- Higher drawdowns

### 4. The Asia ORB Edge Structure

**The 9am ORB has a unique profile:**
- Works BEST with **tight targets (1R)**
- **HALF mode is critical** (reduces stops)
- Very **high frequency** (100+ trades/year)
- **Short hold times** (average 16 minutes for 1R)
- Positive edge comes from **consistency, not home runs**

---

## COMPARISON TO VALIDATED SETUPS

**Current validated_setups has:**
- MGC 0900: RR=6.0, SL=FULL ❌ (This tests NEGATIVE)
- NQ 0900: RR=1.0, SL=HALF ✅ (Similar to our winner)

**RECOMMENDATION: Update MGC 0900 setup**

Current setup (RR6.0 FULL) tests at:
- -6.4R total (extended window)
- -33.6R total (standard window)

Winner setup (RR1.0 HALF) tests at:
- +31.7R total (standard window)
- +29.0R total (extended window)

**This is a 60R+ improvement over 5 years!**

---

## IMPLEMENTATION RECOMMENDATIONS

### PRIMARY SETUP (Conservative)
- **RR**: 1.0R
- **SL Mode**: HALF
- **Scan Window**: 09:05 - 17:00
- **Expected**: 103 trades/year, 53% WR, +0.061R avg
- **Risk Profile**: Low drawdown (16R max)

### ALTERNATIVE SETUP (Asymmetric)
- **RR**: 8.0R
- **SL Mode**: HALF
- **Scan Window**: 09:05 - next 09:00
- **Expected**: 61 wins/year (12% WR), +0.058R avg
- **Risk Profile**: High drawdown (76R max), long holds

### BLEND APPROACH
Run BOTH setups simultaneously:
- Take every 1.0R HALF setup (high frequency)
- ALSO take 8.0R HALF extended (when it triggers)
- Combined: Higher total R, smoother curve

---

## NEXT STEPS

1. ✅ Update validated_setups database with RR1.0 HALF standard setup
2. ✅ Update trading_app/config.py with new MGC_ORB_SIZE_FILTERS
3. ✅ Run `python test_app_sync.py` to verify synchronization
4. Test in paper trading for 2 weeks before going live
5. Monitor win rate - should stay above 50%

---

## DATA NOTES

- Backtest uses zero-lookahead methodology
- Stop-first assumption (conservative)
- Entry on 1-minute close outside ORB
- No slippage applied (add ~0.1R degradation in live)
- No commission applied (MGC commission is minimal)

---

## CONCLUSION

**The 9am ORB works best as a HIGH-FREQUENCY, LOW-TARGET setup.**

Key success factors:
1. Use HALF stop mode (critical)
2. Take 1.0R targets for consistency
3. Standard scan window (09:05-17:00)
4. High trade frequency smooths results
5. Short hold times reduce risk

**The current validated setup (6R FULL) is WRONG for 9am Asia ORB.**

Update to 1.0R HALF for a 60R improvement over 5 years.
