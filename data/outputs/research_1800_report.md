# 1800 SESSION EDGE RESEARCH REPORT

**Date**: 2026-01-13 15:01

---

## DATA SUMMARY

- Total days: 522
- Date range: 2024-01-02 00:00:00 to 2026-01-09 00:00:00
- Instrument: MGC
- Session: 1800 (18:00 local UTC+10)

---

## STAGE 1 RESULTS (BROAD SCAN)

**Filter**: avgR > 0 AND N >= 80 trades

| Rank | Template | Trades | Win Rate | Avg R | Total R | Pass |
|------|----------|--------|----------|-------|---------|------|
| 1 | ORB_Breakout_RR1 | 522 | 71.3% | +0.425R | +222.0R | PASS |
| 2 | ORB_Breakout_RR2 | 522 | 71.3% | +0.425R | +222.0R | PASS |
| 3 | ORB_Breakout_RR3 | 522 | 71.3% | +0.425R | +222.0R | PASS |
| 7 | Asia_Rejection_20stop | 449 | 71.0% | +0.421R | +189.0R | PASS |
| 6 | ORB_SmallOnly_30pct_RR1 | 491 | 70.5% | +0.409R | +201.0R | PASS |
| 4 | ORB_SmallOnly_50pct_RR1 | 500 | 70.4% | +0.408R | +204.0R | PASS |
| 5 | ORB_SmallOnly_40pct_RR1 | 498 | 70.3% | +0.406R | +202.0R | PASS |

---

## TOP CANDIDATES

### ORB_Breakout_RR1

**Parameters**: {'rr': 1.0}

**Performance**:
- Trades: 522
- Win Rate: 71.3%
- Avg R: +0.425R
- Total R: +222.0R

---

### ORB_Breakout_RR2

**Parameters**: {'rr': 2.0}

**Performance**:
- Trades: 522
- Win Rate: 71.3%
- Avg R: +0.425R
- Total R: +222.0R

---

### ORB_Breakout_RR3

**Parameters**: {'rr': 3.0}

**Performance**:
- Trades: 522
- Win Rate: 71.3%
- Avg R: +0.425R
- Total R: +222.0R

---

### Asia_Rejection_20stop

**Parameters**: {'min_asia_pct_atr': 0.3, 'max_asia_pct_atr': 1.5, 'stop_pct': 0.2}

**Performance**:
- Trades: 449
- Win Rate: 71.0%
- Avg R: +0.421R
- Total R: +189.0R

---

### ORB_SmallOnly_30pct_RR1

**Parameters**: {'max_orb_pct_atr': 0.3, 'rr': 1.0}

**Performance**:
- Trades: 491
- Win Rate: 70.5%
- Avg R: +0.409R
- Total R: +201.0R

---

### ORB_SmallOnly_50pct_RR1

**Parameters**: {'max_orb_pct_atr': 0.5, 'rr': 1.0}

**Performance**:
- Trades: 500
- Win Rate: 70.4%
- Avg R: +0.408R
- Total R: +204.0R

---

### ORB_SmallOnly_40pct_RR1

**Parameters**: {'max_orb_pct_atr': 0.4, 'rr': 1.0}

**Performance**:
- Trades: 498
- Win Rate: 70.3%
- Avg R: +0.406R
- Total R: +202.0R

---

## NOTES

**NO LOOKAHEAD**: All features computed at or before entry timestamp

**CONSERVATIVE EXECUTION**: Next-bar entry after signal

**VALIDATION PENDING**: Stage 2 (stability) and Stage 3 (realism) checks not yet complete

**DO NOT TRADE**: These results are preliminary research only

