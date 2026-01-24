# ORB Institutional Audit - Next Steps

**Date**: 2026-01-24
**Status**: Audit Complete - Action Items Identified

---

## Quick Summary

✅ **GOOD NEWS**: Your codebase has strong foundations (zero-lookahead, UTC storage, explicit conversions)

⚠️ **CRITICAL GAPS**: Missing tests and validation frameworks create unacceptable risk for live trading

**Verdict**: NOT safe for live trading YET - complete Phase 1 actions first

---

## Immediate Actions (Complete Today)

### 1. Run Temporal Integrity Tests

```bash
# Test DST handling and ORB alignment
pytest tests/test_temporal_integrity.py -v
```

**Expected**: All tests pass (Brisbane time remains stable despite US DST)

### 2. Run Edge Case Tests

```bash
# Test missing bars, duplicates, out-of-order data
pytest tests/test_edge_cases.py -v
```

**Expected**: System handles edge cases gracefully (returns None, no crashes)

### 3. Run Timestamp Probe (Manual Validation)

```bash
# Validate ORB alignment for a normal day
python scripts/timestamp_probe.py 2025-06-15

# Validate during US DST start
python scripts/timestamp_probe.py 2025-03-09

# Validate during US DST end
python scripts/timestamp_probe.py 2025-11-02
```

**Expected**: All validation checks pass, ORB windows align to Brisbane time

### 4. Run Determinism Tests

```bash
# Verify identical results on repeated runs
pytest tests/test_determinism.py -v
```

**Expected**: All tests pass (feature building is deterministic)

---

## Phase 2: Add Cost Modeling (Tomorrow)

### 1. Add Commission and Slippage Constants

Edit `pipeline/build_daily_features_v2.py` and add:

```python
# Add near top of file
COMMISSION_RT = 2.0  # $2 round-trip commission
SLIPPAGE_TICKS = 0.5  # 0.5 ticks average slippage
TICK_VALUE = 0.10  # MGC tick value

def apply_costs(gross_r: float, risk_ticks: float) -> float:
    """Apply commission and slippage to R multiple."""
    cost_dollars = COMMISSION_RT + (SLIPPAGE_TICKS * TICK_VALUE * 2)  # entry + exit
    risk_dollars = risk_ticks * TICK_VALUE
    cost_in_r = cost_dollars / risk_dollars if risk_dollars > 0 else 0
    return gross_r - cost_in_r
```

### 2. Update R Calculation

In `calculate_orb_1m_exec()` function, apply costs to outcome:

```python
# After calculating r_multiple (around line 260-270)
if outcome == "WIN":
    r_multiple = rr
elif outcome == "LOSS":
    r_multiple = -1.0

# Apply costs
r_multiple_net = apply_costs(r_multiple, risk_ticks)
```

### 3. Re-run Feature Building

```bash
# Rebuild features with costs
python build_daily_features_v2.py 2024-01-01 2026-01-10
```

---

## Phase 3: Out-of-Sample Validation (Next Week)

### 1. Define Research Cutoff

Choose a date (e.g., 2025-12-31) where ALL parameters were locked.

### 2. Generate Profitability Report

Create script that outputs:

```
=== PROFITABILITY REPORT ===
Research Cutoff: 2025-12-31 (NO PARAMS CHANGED AFTER THIS)

IN-SAMPLE (2024-01-01 to 2025-12-31):
  Trades: XXX
  Win Rate: XX%
  Avg R: X.XX
  Max DD: XX R

OUT-OF-SAMPLE (2026-01-01 to 2026-01-10):
  Trades: XX
  Win Rate: XX%
  Avg R: X.XX
  Max DD: XX R
```

### 3. Verify Out-of-Sample Performance

If out-of-sample metrics match in-sample (within reasonable variance), you have honest validation.

---

## When Can You Trade Live?

### ✅ Paper Trading: After Phase 1 + Phase 2 Complete

- All temporal integrity tests pass
- All edge case tests pass
- Determinism validated
- Commission/slippage modeled

**Timeline**: 1-2 days from now

### ✅ Live Trading: After Phase 3 Complete

- Walk-forward validation framework implemented
- Out-of-sample metrics generated
- Performance verified on unseen data

**Timeline**: 1 week from now

---

## Files Created by This Audit

1. **ORB_INSTITUTIONAL_AUDIT_REPORT.md** - Full audit findings
2. **tests/test_temporal_integrity.py** - DST and timezone tests
3. **tests/test_edge_cases.py** - Missing bars, duplicates, etc.
4. **tests/test_determinism.py** - Repeatability validation
5. **scripts/timestamp_probe.py** - Manual ORB alignment checker
6. **AUDIT_NEXT_STEPS.md** - This file

---

## Key Findings Recap

### ✅ Strengths

1. **Zero-lookahead architecture** - Entry logic uses only past data
2. **UTC storage** - All timestamps stored in UTC, converted at boundaries
3. **Conservative execution** - Stop-first on same bar (realistic)
4. **Guardrail assertions** - Prevents entry at ORB edge

### ❌ Critical Gaps

1. **No temporal integrity tests** - DST bugs possible
2. **No edge case tests** - Silent failures possible
3. **No out-of-sample validation** - Profitability unproven
4. **No commission/slippage modeling** - Results inflated

---

## Questions?

Review the full audit report: **ORB_INSTITUTIONAL_AUDIT_REPORT.md**

Run the tests and see if they all pass. If any fail, stop and fix before proceeding.

**DO NOT trade live until ALL Phase 1 + Phase 2 + Phase 3 actions are complete.**
