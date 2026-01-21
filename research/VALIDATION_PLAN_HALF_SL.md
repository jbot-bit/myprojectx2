# VALIDATION PLAN - HALF SL MODE IMPLEMENTATION

**Date**: 2026-01-21
**Status**: READY TO EXECUTE

---

## OBJECTIVE

Validate that implementing HALF SL mode + extended windows + optimal RR values reproduces the promoted edge results:
- 2300: +0.403R (56.1% WR)
- 0030: +0.254R (31.3% WR)

---

## STEP 1: Update candidate_backtest_engine.py

### Change 1: Add HALF SL Mode to CandidateSpec

```python
@dataclass
class CandidateSpec:
    # ... existing fields ...
    sl_mode: str  # 'HALF' or 'FULL'
```

### Change 2: Update parse_candidate_spec()

```python
def parse_candidate_spec(candidate_dict):
    # ... existing parsing ...

    # Extract SL mode from test_config_json
    # Default to HALF for 2300/0030, FULL for others
    sl_mode = test_config.get("sl_mode", "HALF" if orb_time in ("2300", "0030") else "FULL")

    return CandidateSpec(
        # ... existing fields ...
        sl_mode=sl_mode,
    )
```

### Change 3: Update simulate_trade() Stop Calculation

```python
def simulate_trade(entry_bar, direction, orb, remaining_bars, spec):
    entry_price = entry_bar['close']
    entry_ts = entry_bar['ts_local']

    # Calculate stop based on SL mode
    if spec.sl_mode == 'HALF':
        stop_price = orb['midpoint']  # HALF: use ORB midpoint
    else:  # FULL
        stop_price = orb['low'] if direction == 'long' else orb['high']

    # Calculate risk from entry to stop
    if direction == 'long':
        risk = entry_price - stop_price
        target_price = entry_price + (risk * spec.rr)
    else:  # short
        risk = stop_price - entry_price
        target_price = entry_price - (risk * spec.rr)

    # ... rest of simulation ...
```

---

## STEP 2: Update Edge Candidates for 2300/0030

Update test_config_json for the 2300 and 0030 extended candidates:

```sql
-- 2300 ORB Extended - RR1.5
UPDATE edge_candidates
SET test_config_json = json('{
    "orb_time": "2300",
    "orb_minutes": 5,
    "entry_rule": "First 1m close outside 2300 ORB",
    "stop_rule": "ORB midpoint (HALF mode)",
    "sl_mode": "HALF",
    "target_rule": "1.5R",
    "rr": 1.5,
    "scan_window": "23:05 → 09:00 (10 hours)"
}')
WHERE name = '2300 ORB Extended - RR1.5';

-- 0030 ORB Extended - RR3.0
UPDATE edge_candidates
SET test_config_json = json('{
    "orb_time": "0030",
    "orb_minutes": 5,
    "entry_rule": "First 1m close outside 0030 ORB",
    "stop_rule": "ORB midpoint (HALF mode)",
    "sl_mode": "HALF",
    "target_rule": "3.0R",
    "rr": 3.0,
    "scan_window": "00:35 → 09:00 (8.5 hours)"
}')
WHERE name = '0030 ORB Extended - RR3.0';
```

---

## STEP 3: Re-run Phase 3 Backtest

```bash
cd research
python run_phase3_proper.py
```

---

## STEP 4: Validate Results

### Success Criteria

**2300 ORB Extended - RR1.5 (HALF SL)**:
- ✅ Trades: 522 (±5)
- ✅ Win Rate: 56.1% (±2%)
- ✅ Avg R: +0.403R (±0.02R)

**0030 ORB Extended - RR3.0 (HALF SL)**:
- ✅ Trades: 520 (±5)
- ✅ Win Rate: 31.3% (±2%)
- ✅ Avg R: +0.254R (±0.02R)

### If Results Match

1. Update PHASE3_PROPER_CRITICAL_FINDINGS.md with resolution
2. Mark promoted edges as VALIDATED ✓
3. Proceed with applying ORB size filters (Phase 2 of validation)

### If Results Don't Match

1. Add detailed trade logging to candidate_backtest_engine.py
2. Compare first 10 trades against expected outcomes
3. Identify specific divergence point (entry, stop, target calculation)
4. Debug and iterate

---

## STEP 5: Apply ORB Size Filters (Phase 2)

Once baseline HALF SL results match, add filter logic:

```python
def apply_filters(orb, day_features, spec):
    # ... existing filter parsing ...

    # ORB size filter
    if spec.filters.get('orb_size_filter'):
        if spec.orb_time == "2300":
            threshold = 0.155
        elif spec.orb_time == "0030":
            threshold = 0.112
        else:
            return True

        atr_20 = day_features.get("atr_20")
        if atr_20 is None or atr_20 <= 0:
            return True

        orb_size_norm = orb["size"] / atr_20

        if orb_size_norm > threshold:
            return False  # REJECT

    return True  # PASS
```

**Expected Results with Filters**:
- 2300: +0.447R (188 trades)
- 0030: +0.373R (67 trades)

---

## TIMELINE

- **Step 1-2**: 30 minutes (code updates)
- **Step 3**: 5 minutes (backtest run)
- **Step 4**: 10 minutes (validation)
- **Step 5**: 30 minutes (filter implementation + test)

**Total**: ~75 minutes to complete validation

---

## RISK MITIGATION

### Risk 1: Small Calculation Differences

**Mitigation**: Use tolerance bands (±0.02R, ±2% WR)

### Risk 2: Data Differences

**Mitigation**: Verify ORB calculations match daily_features_v2 (already done ✓)

### Risk 3: Edge Case Handling

**Mitigation**: Handle zero-risk trades, missing data, weekend gaps consistently

---

## OUTPUTS

Upon completion:
- Updated `research/phase3_proper_results.csv` with HALF SL results
- Updated `research/PHASE3_PROPER_CRITICAL_FINDINGS.md` with resolution
- New `research/VALIDATION_RESULTS_HALF_SL.md` with detailed comparison

---

**Status**: READY TO EXECUTE
**Confidence**: VERY HIGH (logic fully reconstructed from old project)
