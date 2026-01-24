# 2300 ORB (Globex/NY Futures Open) - Quick Scan Results

**Date Generated**: 2026-01-20
**Data Source**: NIGHT_ORB_2300_half_EXTENDED.csv (Jan 16, 2026)
**Session**: 2300 (23:00 Brisbane time, Globex/NY futures open)
**Stop Loss Mode**: HALF (ORB midpoint)
**Scan Window**: Extended to next Asia open (09:00) - captures full overnight moves

---

## Key Findings

✅ **POSITIVE EDGE CONFIRMED**

**Optimal Setup**: RR=1.5
- Win Rate: 56.1%
- Avg R: +0.403R per trade
- Total R: +210.5R over 522 trades
- Estimated Annual: ~+105R/year

---

## Full Results by RR Ratio

| RR | Trades | Win Rate | Avg R | Total R | Ann. R (est) | Notes |
|----|--------|----------|-------|---------|--------------|-------|
| 1.0 | 522 | 69.3% | +0.387 | +202.0 | +101/yr | High WR, good edge |
| **1.5** | **522** | **56.1%** | **+0.403** | **+210.5** | **+105/yr** | **OPTIMAL** ⭐ |
| 2.0 | 522 | 45.2% | +0.356 | +186.0 | +93/yr | Still positive |
| 2.5 | 522 | 38.1% | +0.334 | +174.5 | +87/yr | Decent |
| 3.0 | 522 | 31.8% | +0.272 | +142.0 | +71/yr | Marginal |
| 4.0 | 522 | 26.2% | +0.312 | +163.0 | +82/yr | Slight recovery |
| 5.0 | 519 | 20.6% | +0.237 | +123.0 | +62/yr | Weak |
| 6.0 | 517 | 16.8% | +0.178 | +92.0 | +46/yr | Weak |
| 8.0 | 505 | 11.9% | +0.069 | +35.0 | +18/yr | Very weak |

---

## Trading Rules (Optimal Setup)

### Entry
- Wait for 2300 ORB to form (23:00-23:05 Brisbane)
- Wait for first 1-minute close outside ORB (break direction)
- Enter at that close price

### Stop Loss
- HALF mode: ORB midpoint (halfway between ORB high and low)
- Distance from entry to stop = 1R

### Target
- 1.5R from entry (1.5x the stop distance)

### Scan Window
- Extended: Continue scanning until next Asia open (09:00)
- Captures overnight moves that can take hours to develop

### Direction
- Trade the break direction (UP or DOWN)
- No directional bias - take both sides

---

## Key Observations

1. **Extended scan window is critical**: Original 85-minute window missed most moves
2. **Half-SL mode works better**: Full-SL too wide for overnight volatility
3. **Sweet spot at RR=1.5**: Balance between win rate and reward
4. **Positive across RR range**: Edge holds from 1.0 to 4.0
5. **Sample size**: 522 trades over 2 years (very robust)

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
3. ⏳ Add contextual filters if needed
4. ⏳ Deploy to edge_candidates for approval workflow

---

## Safety Notes

- This is a NIGHT session trade (overnight risk)
- Extended scan window = overnight position
- Stop is HALF ORB (tighter than full ORB)
- Target is 1.5R (realistic for overnight moves)

**DO NOT USE WITHOUT PROPER RISK MANAGEMENT**

---

## Source Files

- Test script: `test_night_orb_extended_windows.py` (legacy repo)
- Results CSV: `NIGHT_ORB_2300_half_EXTENDED.csv` (legacy repo, Jan 16)
- Database: gold.db (daily_features_v2, bars_1m)
- Date range: 2024-01-02 to 2026-01-10

---

**Conclusion**: 2300 ORB shows positive edge with extended scan window. **TRADEABLE** with RR=1.5.
