# 0030 ORB (NYSE Opening Range) - Quick Scan Results

**Date Generated**: 2026-01-20
**Data Source**: NIGHT_ORB_0030_half_EXTENDED.csv (Jan 16, 2026)
**Session**: 0030 (00:30 Brisbane time, NYSE ORB)
**Stop Loss Mode**: HALF (ORB midpoint)
**Scan Window**: Extended to next Asia open (09:00) - captures full overnight moves

---

## Key Findings

✅ **POSITIVE EDGE CONFIRMED**

**Optimal Setup**: RR=3.0
- Win Rate: 31.3%
- Avg R: +0.254R per trade
- Total R: +132.0R over 520 trades
- Estimated Annual: ~+66R/year

---

## Full Results by RR Ratio

| RR | Trades | Win Rate | Avg R | Total R | Ann. R (est) | Notes |
|----|--------|----------|-------|---------|--------------|-------|
| 1.0 | 522 | 61.7% | +0.234 | +122.0 | +61/yr | High WR, decent edge |
| 1.5 | 522 | 48.1% | +0.202 | +105.5 | +53/yr | Still positive |
| 2.0 | 522 | 40.4% | +0.213 | +111.0 | +56/yr | Still positive |
| 2.5 | 521 | 34.9% | +0.223 | +116.0 | +58/yr | Getting better |
| **3.0** | **520** | **31.3%** | **+0.254** | **+132.0** | **+66/yr** | **OPTIMAL** ⭐ |
| 4.0 | 518 | 23.7% | +0.187 | +97.0 | +49/yr | Drops off |
| 5.0 | 513 | 18.3% | +0.099 | +51.0 | +26/yr | Weak |
| 6.0 | 511 | 16.0% | +0.123 | +63.0 | +32/yr | Weak |
| 8.0 | 496 | 11.7% | +0.052 | +26.0 | +13/yr | Very weak |

---

## Trading Rules (Optimal Setup)

### Entry
- Wait for 0030 ORB to form (00:30-00:35 Brisbane)
- Wait for first 1-minute close outside ORB (break direction)
- Enter at that close price

### Stop Loss
- HALF mode: ORB midpoint (halfway between ORB high and low)
- Distance from entry to stop = 1R

### Target
- 3.0R from entry (3x the stop distance)

### Scan Window
- Extended: Continue scanning until next Asia open (09:00)
- Captures overnight moves that can take hours to develop

### Direction
- Trade the break direction (UP or DOWN)
- No directional bias - take both sides

---

## Key Observations

1. **Extended scan window is critical**: Original 85-minute window missed most moves
2. **Half-SL mode works**: Tighter stop appropriate for overnight volatility
3. **Higher RR optimal (3.0 vs 1.5)**: 0030 moves run further than 2300
4. **Weaker than 2300**: Lower avg R (+0.254 vs +0.403)
5. **Still profitable**: Positive across RR 1.0-4.0
6. **Sample size**: 520-522 trades over 2 years (very robust)

---

## Comparison to 2300 ORB

| Metric | 2300 (RR=1.5) | 0030 (RR=3.0) | Winner |
|--------|---------------|---------------|--------|
| Win Rate | 56.1% | 31.3% | 2300 |
| Avg R | +0.403 | +0.254 | 2300 |
| Total R | +210.5 | +132.0 | 2300 |
| Ann. R | ~+105R/yr | ~+66R/yr | 2300 |
| Optimal RR | 1.5 | 3.0 | Different |

**Conclusion**: 2300 ORB is the stronger setup (~60% better performance)

---

## Regime Considerations

**No temporal stability analysis run yet** - would need to check:
- Performance by quarter/year
- Performance by volatility regime
- Consistency across market conditions

**Recommendation**: Run temporal stability test if deploying to production.

---

## Next Steps

1. ✅ Confirm edge exists (DONE)
2. ⏳ Test temporal stability (RECOMMENDED)
3. ⏳ Consider prioritizing 2300 over 0030 (stronger edge)
4. ⏳ Deploy to edge_candidates for approval workflow

---

## Safety Notes

- This is a NIGHT session trade (overnight risk)
- Extended scan window = overnight position
- Stop is HALF ORB (tighter than full ORB)
- Target is 3.0R (larger than 2300, reflects bigger moves)
- **0030 is NYSE open - can be volatile**

**DO NOT USE WITHOUT PROPER RISK MANAGEMENT**

---

## Source Files

- Test script: `test_night_orb_extended_windows.py` (legacy repo)
- Results CSV: `NIGHT_ORB_0030_half_EXTENDED.csv` (legacy repo, Jan 16)
- Database: gold.db (daily_features_v2, bars_1m)
- Date range: 2024-01-02 to 2026-01-10

---

**Conclusion**: 0030 ORB shows positive edge with extended scan window. **TRADEABLE** with RR=3.0, but **2300 ORB is stronger**.
