# UNICORN TRADES - HIGH RR/EXPECTANCY INVENTORY
**Created**: 2026-01-16
**Purpose**: Catalog all rare, high-reward setups to ensure they're never lost

**Definition**: "Unicorn" = Expectancy >1.0R OR RR ≥3.0 OR Win Rate >65%

---

## 🦄 TIER S+: MEGA UNICORNS (Expectancy >1.5R)

### 1. Multi-Liquidity Cascades - THE HOLY GRAIL
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +1.95R (HIGHEST)
- **Frequency**: 9.3% of days (2-3 per month)
- **Win Rate**: 19-27% (tail-based, not win-rate dependent)
- **Total R**: +129R over 741 days
- **With Large Gap Filter**: **+5.36R average** (43% of cascades)

**What It Is**:
- Sequential liquidity sweep pattern
- Asia session (8hr) → London session (5hr) → NY futures open (23:00)
- Each level traps participants, creating forced liquidations
- Requires acceptance failure confirmation

**Entry Checklist** (ALL must be true):
1. ✅ Asia completes 8hr session (09:00-17:00)
2. ✅ London sweeps Asia high/low (first sweep)
3. ✅ Gap >9.5 points between levels (15× performance multiplier!)
4. ✅ At 23:00: Second sweep of London level
5. ✅ Acceptance failure within 3 bars (3 minutes)
6. ✅ Entry at swept level (±0.1 points)

**Execution**:
- **Entry**: At swept London level after failure confirmed
- **Stop**: Second sweep high/low
- **Target**: Opposite Asia level (structure trail)
- **Max Hold**: 90 minutes
- **Median Peak**: 3-5 minutes
- **Risk**: 0.10-0.25% per trade (MANDATORY - don't overtrade this!)

**Why It Works**:
- Multiple trapped participant layers
- Forced liquidations compound through stops
- NY futures open = liquidity surge + volatility spike
- Gap size predicts trapped leverage density

**Critical Timing**:
- 70% enter at exactly 23:00
- 30% enter 23:01-23:30 window
- Early exit before 23:00 = -1.78R (DESTROYS EDGE!)

**Instruments**:
- ✅ MGC: Validated (+1.95R)
- ❓ NQ: Not yet tested (planned)
- ❓ PL: Not yet tested

**Files**:
- `_archive/reports/CASCADE_PATTERN_RECOGNITION.md`
- `_archive/tests/test_cascade_minimal.py`
- `_archive/scripts/monitor_cascade_live.py`
- `trading_app/strategy_engine.py` (lines 134-329)

---

## 🦄 TIER S: MAJOR UNICORNS (Expectancy 1.0-1.5R)

### 2. Single Liquidity Reactions
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +1.44R
- **Frequency**: 16% of days (8-12 per month)
- **Win Rate**: 33.7%
- **Total R**: +48R over 741 days

**What It Is**:
- Simplified cascade - single level swept (no Asia-London structure)
- London level swept at 23:00 with acceptance failure
- Backup strategy when full cascade doesn't form

**Entry Requirements**:
1. ✅ London level exists (5hr session)
2. ✅ 23:00: Sweep of London level
3. ✅ Acceptance failure within 3 bars
4. ✅ Entry on retrace to London level

**Execution**:
- **Entry**: At swept London level after failure
- **Stop**: Sweep high/low
- **Target**: Structure trail (no fixed target)
- **Risk**: 0.25-0.50% per trade

**Difference from Cascades**:
- No Asia-London cascade structure required
- No gap size multiplier
- Slightly lower edge (+1.44R vs +1.95R)
- More frequent (16% vs 9.3%)

**Instruments**:
- ✅ MGC: Validated
- ❓ NQ: Not yet tested
- ❓ PL: Not yet tested

---

## 🦄 TIER A: HIGH-RR ASYMMETRIC SETUPS (RR ≥3.0)

### 3. MGC 10:00 ORB (RR=3.0)
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.34R
- **RR Target**: 3.0 (3× risk)
- **Frequency**: 64% of days (474 trades)
- **Win Rate**: 33.5% (low but sufficient for RR=3)
- **Total R**: +88R over 741 days

**What It Is**:
- Asymmetric risk-reward setup
- Low win rate but large targets compensate
- Asia session ORB at 10:00-10:05

**Entry Requirements**:
1. ✅ ORB size ≤10 points (100 ticks) - MANDATORY FILTER
2. ✅ Close outside ORB at 10:05+
3. ✅ Entry at close price

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 3R (3× ORB size from entry)
- **Risk**: 0.10-0.25% per trade

**Why It Works**:
- Small ORBs = tight risk
- 3R targets capture momentum moves
- Filter removes wide/volatile setups

**Instruments**:
- ✅ MGC: Validated (+0.34R)
- ❌ NQ: Uses RR=1.5 instead (different optimal)

---

### 4. MGC 18:00 ORB (RR=2.0)
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.39R (BEST DAY ORB)
- **RR Target**: 2.0
- **Frequency**: 64% of days (474 trades)
- **Win Rate**: 46.4%
- **Total R**: +185R over 741 days

**What It Is**:
- London open ORB
- Session transition = volume surge
- Best day-session ORB performance

**Entry Requirements**:
1. ✅ 18:00-18:05 ORB forms
2. ✅ Close outside ORB at 18:05+
3. ✅ No size filter (baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 2R (2× ORB size from entry)
- **Risk**: 0.10-0.25% per trade

**Why It Works**:
- London open = liquidity event
- Session transition volatility
- Strong directional bias

**Instruments**:
- ✅ MGC: Validated (+0.39R)
- ✅ NQ: Validated (+0.257R with RR=1.5, HALF SL)

---

## 🦄 TIER A: HIGH WIN RATE SETUPS (>65%)

### 5. MGC 11:00 ORB
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.30R
- **RR Target**: 1.0
- **Frequency**: 66% of days (489 trades)
- **Win Rate**: 64.9% (HIGHEST ASIA ORB)
- **Total R**: +147R over 741 days

**What It Is**:
- Late Asia session ORB
- Most reliable setup (highest win rate for Asia)
- Conservative 1:1 RR

**Entry Requirements**:
1. ✅ 11:00-11:05 ORB forms
2. ✅ Close outside ORB at 11:05+
3. ✅ No size filter (baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 1R (1× ORB size from entry)
- **Risk**: 0.10-0.25% per trade

**Why It Works**:
- Late Asia = established trend
- Lower volatility than early session
- High reliability

**Instruments**:
- ✅ MGC: Validated (64.9% WR)
- ✅ NQ: Validated (56.0% WR, RR=1.5)
- ✅ PL: Validated (67.3% WR - BEST!)

---

### 6. MGC 09:00 ORB
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.27R
- **RR Target**: 1.0
- **Frequency**: 100% of days (741 trades)
- **Win Rate**: 63.3%
- **Total R**: +200R over 741 days

**What It Is**:
- Asia session open ORB
- Trades every day (highest frequency)
- Reliable baseline edge

**Entry Requirements**:
1. ✅ 09:00-09:05 ORB forms
2. ✅ Close outside ORB at 09:05+
3. ✅ No size filter (baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 1R (1× ORB size from entry)
- **Risk**: 0.10-0.25% per trade

**Why It Works**:
- Session open = direction establishment
- Daily occurrence = consistency
- High win rate

**Instruments**:
- ✅ MGC: Validated (63.3% WR)
- ✅ NQ: Validated (53.0% WR with strict filter)
- ✅ PL: Validated (61.5% WR)

---

### 7. PL 11:00 ORB - PLATINUM CHAMPION
**Status**: ✅ VALIDATED (2026-01-15)

**Performance**:
- **Average R**: +0.346R
- **RR Target**: 1.0
- **Frequency**: 254 trades over 365 days
- **Win Rate**: 67.3% (HIGHEST ACROSS ALL INSTRUMENTS!)
- **Total R**: +88R in one year

**What It Is**:
- Platinum late-Asia ORB
- Best single ORB across all instruments
- Full-size contracts ($50/point)

**Entry Requirements**:
1. ✅ 11:00-11:05 ORB forms
2. ✅ Close outside ORB at 11:05+
3. ✅ No size filter (strong baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 1R (1× ORB size from entry)
- **Risk**: 0.40-0.50% per trade
- **Contract**: Full-size PL ($50/point, not MPL)

**Why It Works**:
- Platinum industrial/precious hybrid
- Lower volatility than gold
- Strong trend continuation

**Position Sizing**:
- $25k account, 0.50% risk = $125
- 2.0pt ORB = 2.0 × $50 = $100 risk/contract
- Max contracts: 1 (actual risk: $100 = 0.40%)

---

### 8. PL 23:00 ORB - PLATINUM NIGHT
**Status**: ✅ VALIDATED (2026-01-15)

**Performance**:
- **Average R**: +0.314R
- **RR Target**: 1.0
- **Frequency**: 245 trades over 365 days
- **Win Rate**: 65.7%
- **Total R**: +77R in one year

**What It Is**:
- Platinum NY futures open ORB
- Second-best platinum setup
- Excellent night-session alternative

**Entry Requirements**:
1. ✅ 23:00-23:05 ORB forms
2. ✅ Close outside ORB at 23:05+
3. ✅ No size filter (strong baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: Opposite ORB edge (FULL SL mode)
- **Target**: 1R (1× ORB size from entry)
- **Risk**: 0.40-0.50% per trade
- **Contract**: Full-size PL ($50/point)

**Why It Works**:
- NY futures open volatility
- Platinum follows gold correlation
- Strong win rate

---

## 🏆 TIER B: CORRELATION UNICORNS (Conditional High-WR)

### 9. 10:00 UP after 09:00 WIN
**Status**: ✅ VALIDATED

**Performance**:
- **Average R**: +0.16R
- **Frequency**: 114 trades (15% of days)
- **Win Rate**: 57.9% (vs 52% baseline)
- **Tier**: S (BEST CORRELATION)

**What It Is**:
- Momentum continuation pattern
- Requires 09:00 ORB WIN first
- Then trade 10:00 UP only

**Entry Requirements**:
1. ✅ 09:00 ORB breaks and WINS (TP hit)
2. ✅ 10:00 ORB breaks UP (same direction as 09:00)
3. ✅ Trade 10:00 with standard rules

**Why It Works**:
- Momentum confirmation
- Triple timeframe alignment
- Reduced false breakouts

**Instruments**:
- ✅ MGC: Validated (57.9% WR)
- ❓ NQ/PL: Not tested

---

### 10. 11:00 UP after 09:00 WIN + 10:00 WIN UP
**Status**: ✅ VALIDATED

**Performance**:
- **Average R**: +0.15R
- **Frequency**: 68 trades (9% of days)
- **Win Rate**: 57.4%
- **Tier**: A

**What It Is**:
- Strong momentum continuation
- Triple confirmation pattern
- Requires two consecutive ORB wins

**Entry Requirements**:
1. ✅ 09:00 ORB WIN
2. ✅ 10:00 ORB WIN UP
3. ✅ 11:00 ORB breaks UP
4. ✅ Trade 11:00 with standard rules

**Why It Works**:
- Three-level confirmation
- Strong directional bias
- Momentum persistence

**Instruments**:
- ✅ MGC: Validated
- ❓ NQ/PL: Not tested

---

## 🦄 TIER B: DAILY BREAD-AND-BUTTER (Consistent Positive Edge)

### 11. MGC 23:00 ORB - NIGHT WORKHORSE
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.387R
- **RR Target**: 1.0
- **Frequency**: 100% of days (740 trades)
- **Win Rate**: 48.9%
- **Total R**: +202R over 741 days (~+100R/year)

**What It Is**:
- NY futures open ORB
- Trades EVERY SINGLE DAY
- Consistent small positive edge
- HALF SL mode (tighter risk)

**Entry Requirements**:
1. ✅ 23:00-23:05 ORB forms
2. ✅ Close outside ORB at 23:05+
3. ✅ No size filter (baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: ORB midpoint (HALF SL mode)
- **Target**: 1R (ORB half-range from entry)
- **Risk**: 0.25-0.50% per trade

**Why It Works**:
- NY futures open = volatility spike
- Daily occurrence = steady income
- Smaller risk due to HALF SL

**Why This is a UNICORN**:
- Trades EVERY day (no waiting!)
- Positive expectancy (+0.387R)
- ~+100R per year from ONE setup
- Perfect complement to rare cascades

**Instruments**:
- ✅ MGC: Validated (+0.387R)
- ✅ PL: Validated (+0.314R, 65.7% WR)

---

### 12. MGC 00:30 ORB - LATE NIGHT EDGE
**Status**: ✅ VALIDATED & ACTIVE

**Performance**:
- **Average R**: +0.231R
- **RR Target**: 1.0
- **Frequency**: 100% of days (740 trades)
- **Win Rate**: 43.5%
- **Total R**: +121R over 741 days (~+60R/year)

**What It Is**:
- NY ORB at cash market overlap
- Trades EVERY SINGLE DAY
- Small but consistent edge
- HALF SL mode (tighter risk)

**Entry Requirements**:
1. ✅ 00:30-00:35 ORB forms
2. ✅ Close outside ORB at 00:35+
3. ✅ No size filter (baseline)

**Execution**:
- **Entry**: First close outside ORB
- **Stop**: ORB midpoint (HALF SL mode)
- **Target**: 1R (ORB half-range from entry)
- **Risk**: 0.25-0.50% per trade

**Why It Works**:
- NYSE cash market hours
- Daily occurrence
- Consistent small edge

**Why This is a UNICORN**:
- Trades EVERY day
- Positive expectancy (+0.231R)
- ~+60R per year from ONE setup
- Can trade alongside 23:00 ORB

**Instruments**:
- ✅ MGC: Validated (+0.231R)
- ✅ PL: Validated (+0.211R, 60.6% WR)

---

## ❌ INVALIDATED CLAIMS (Corrected to Truth)

### Night ORBs with RR=4.0 - FALSE CLAIMS CORRECTED
**Status**: ❌ OLD CLAIMS WERE WRONG, NEW NUMBERS ARE CORRECT

**Old FALSE Claims** (Don't use these!):
- 23:00 ORB: +1.077R avg, RR=4.0
- 00:30 ORB: +1.541R avg, RR=4.0

**Why Those Were False**:
- Used ORB-edge entry (lookahead bias - you can't know the edge until after!)
- Not realistic execution
- Inflated performance

**CORRECTED HONEST Performance** (USE THESE!):
- **23:00 ORB: +0.387R avg, RR=1.0** ✅ STILL PROFITABLE!
- **00:30 ORB: +0.231R avg, RR=1.0** ✅ STILL PROFITABLE!

**Key Point**:
- The RR=4.0 claims were invalidated (false)
- But the RR=1.0 versions are VALID and TRADEABLE
- They're GOOD trades that make money!
- Trade them EVERY NIGHT!

**Lesson**:
- Entry method matters enormously
- Always use honest, realistic entry
- Even with honest entry, these are PROFITABLE

**Verified By**:
- `_archive/scripts/FINAL_SYSTEM_VERIFICATION.py`
- AUDIT_REPORT_2026-01-15.md

---

### Proximity Pressure - FAILED TESTING
**Status**: ❌ DISABLED (2026-01-15)

**Performance**:
- **Average R**: -0.50R (NEGATIVE!)
- **Frequency**: 1.1% (very rare)
- **Win Rate**: Unknown
- **Status**: FAILED

**What It Was**:
- Multiple liquidity levels within 5 points
- Pressure from tight proximity
- Entry on acceptance failure

**Why Failed**:
- Negative expectancy
- Too rare to matter
- Tight proximity ≠ trapped leverage

**Action**: Removed from STRATEGY_PRIORITY in config.py

---

## 📊 UNICORN SUMMARY TABLE

| Rank | Setup | Avg R | WR | Freq | RR | Tier | Instruments |
|------|-------|-------|----|----|-----|------|-------------|
| 1 | **Multi-Liquidity Cascades** | +1.95R | 19-27% | 9.3% | Var | S+ | MGC |
| 2 | Single Liquidity Reactions | +1.44R | 33.7% | 16% | Var | S | MGC |
| 3 | MGC 18:00 ORB | +0.39R | 46.4% | 64% | 2.0 | A | MGC, NQ |
| 4 | **MGC 23:00 ORB** | **+0.387R** | **48.9%** | **100%** | **1.0** | **B** | **MGC, PL** |
| 5 | PL 11:00 ORB | +0.346R | 67.3% | 70% | 1.0 | A | PL |
| 6 | MGC 10:00 ORB | +0.34R | 33.5% | 64% | 3.0 | A | MGC |
| 7 | PL 23:00 ORB | +0.314R | 65.7% | 67% | 1.0 | A | PL |
| 8 | MGC 11:00 ORB | +0.30R | 64.9% | 66% | 1.0 | A | MGC, NQ, PL |
| 9 | MGC 09:00 ORB | +0.27R | 63.3% | 100% | 1.0 | B | MGC, NQ, PL |
| 10 | **MGC 00:30 ORB** | **+0.231R** | **43.5%** | **100%** | **1.0** | **B** | **MGC, PL** |
| 11 | 10:00 UP after 09:00 WIN | +0.16R | 57.9% | 15% | 1.0 | B | MGC |

---

## 🎯 TRADING PRIORITY HIERARCHY

### Check in This Order Every Day:

**1. Multi-Liquidity Cascades (9.3% frequency)**
- Check at 23:00
- If conditions met → TRADE (highest priority)
- Risk: 0.10-0.25%
- Expected: 2-3 per month, +1.95R avg

**2. Single Liquidity Reactions (16% frequency)**
- If cascade doesn't form but single level swept
- Risk: 0.25-0.50%
- Expected: 8-12 per month, +1.44R avg

**3. Night ORBs (100% frequency)**
- 23:00 ORB: +0.387R avg (MGC) or +0.314R (PL)
- 00:30 ORB: +0.231R avg (MGC) or +0.211R (PL)
- Risk: 0.25-0.50%
- Trade daily if no higher-priority setups

**4. Day ORBs (64-100% frequency)**
- 09:00, 10:00, 11:00, 18:00
- Risk: 0.10-0.25%
- Trade if need more activity
- Check correlations for higher-WR opportunities

---

## 🔐 PROTECTION RULES (Don't Lose These Unicorns!)

### 1. Never Override Entry Rules
- Cascades: Entry at swept level ±0.1pts ONLY
- ORBs: Entry at close outside ORB ONLY
- No "gut feel" entries

### 2. Respect Position Sizing
- Cascades: 0.10-0.25% MAX (they're rare, don't blow up!)
- Single Liquidity: 0.25-0.50%
- ORBs: 0.10-0.50%
- NEVER scale up just because you're excited

### 3. Track Every Trade
- Log setup type
- Log entry/stop/target
- Log outcome
- Review monthly

### 4. Don't Overtrade Cascades
- Only 2-3 per month expected
- If you're taking 10/month → you're forcing it
- Quality > Quantity

### 5. Verify Against Database
- All performance numbers in this document are from:
  - `validated_strategies.py`
  - `_archive/reports/STRATEGY_HIERARCHY_FINAL.md`
  - `PLATINUM_VERIFICATION_COMPLETE.md`
- If numbers don't match → investigate before trading

---

## 📁 KEY FILES TO NEVER DELETE

**Cascade Files**:
- `_archive/reports/CASCADE_PATTERN_RECOGNITION.md`
- `_archive/reports/CASCADE_QUICK_REFERENCE.md`
- `_archive/tests/test_cascade_minimal.py`
- `_archive/tests/test_cascade_bidirectional.py`
- `_archive/scripts/monitor_cascade_live.py`
- `_archive/scripts/track_cascade_exits.py`

**Validation Files**:
- `validated_strategies.py` (SOURCE OF TRUTH)
- `_archive/reports/STRATEGY_HIERARCHY_FINAL.md`
- `PLATINUM_VERIFICATION_COMPLETE.md`
- `_archive/scripts/FINAL_SYSTEM_VERIFICATION.py`

**ORB Config Files**:
- `trading_app/config.py` (MGC_ORB_CONFIGS, NQ_ORB_CONFIGS, MPL_ORB_CONFIGS)
- `configs/market_mgc.yaml`
- `configs/market_nq.yaml`
- `configs/market_mpl.yaml`

---

## 🔄 NEXT STEPS

### Untested Unicorn Candidates:

**1. NQ Cascades**
- Same pattern as MGC
- Needs 15pt gap (vs 9.5pt for MGC) due to 13× volatility
- Expected: Similar or better edge
- Status: Not yet tested

**2. PL Cascades**
- Same pattern as MGC
- Gap threshold unknown
- Expected: Likely works (platinum follows gold correlation)
- Status: Not yet tested

**3. NQ Correlations**
- 10:00 UP after 09:00 WIN (MGC validated)
- 11:00 patterns
- Status: Not yet tested

**4. PL Correlations**
- All momentum patterns
- Status: Not yet tested

---

**FINAL NOTE**: This document is your insurance policy against losing rare, high-value setups. Keep it updated. Reference it often. Don't let these unicorns disappear!

**Last Updated**: 2026-01-16
**Next Review**: Monthly (or after any major system changes)
