# NQ DATA INTEGRITY AUDIT

**Generated**: 2026-01-13 16:08:05
**Database**: gold.db
**Symbol**: NQ

---

## SUMMARY

- bars_1m_nq: **306,243** rows
- bars_5m_nq: **61,252** rows
- Date range: **2025-01-13 09:00:00+10:00** to **2025-11-21 12:00:00+10:00**
- Total days: **313**
- Unique contracts: **4**

## INTEGRITY CHECKS

### 1. 5-Minute Aggregation

[OK] Expected ~61,248 bars, found 61,252

### 2. Duplicates

[OK] Found 0 duplicate timestamps

### 3. Time Gaps

Found 20 gaps > 2 minutes

Largest gaps (minutes):
  - 2025-04-18 06:59:00+10:00 -> 2025-04-21 08:00:00+10:00: 4381 minutes
  - 2025-07-05 02:59:00+10:00 -> 2025-07-07 08:00:00+10:00: 3181 minutes
  - 2025-11-01 06:59:00+10:00 -> 2025-11-03 09:00:00+10:00: 3001 minutes
  - 2025-10-25 06:59:00+10:00 -> 2025-10-27 08:00:00+10:00: 2941 minutes
  - 2025-09-27 06:59:00+10:00 -> 2025-09-29 08:00:00+10:00: 2941 minutes
  - 2025-10-18 06:59:00+10:00 -> 2025-10-20 08:00:00+10:00: 2941 minutes
  - 2025-07-12 06:59:00+10:00 -> 2025-07-14 08:00:00+10:00: 2941 minutes
  - 2025-05-24 06:59:00+10:00 -> 2025-05-26 08:00:00+10:00: 2941 minutes
  - 2025-11-15 07:59:00+10:00 -> 2025-11-17 09:00:00+10:00: 2941 minutes
  - 2025-03-15 06:59:00+10:00 -> 2025-03-17 08:00:00+10:00: 2941 minutes

### 4. Price Sanity

[OK] Bad prices (<=0): 0
  - Min: 16460.00
  - Max: 26399.00
  - Avg: 22365.99
  - StdDev: 2084.66

### 5. Volume Sanity

[OK] Zero volume bars: 0 (0.0%)
  - Min: 1
  - Max: 18,557
  - Avg: 402

### 6. Data Coverage

[WARN] Coverage: 70.9% of expected bars
  - Expected: ~431,940 bars (conservative)
  - Actual: 306,243 bars

## CONTRACT ROLLS

Unique contracts: 4

Contracts found:
  - NQH5
  - NQM5
  - NQU5
  - NQZ5

## TIMEZONE VERIFICATION

Sample timestamps (UTC -> Brisbane UTC+10):

  - UTC: 2025-01-13 09:00:00+10:00 -> Local: 2025-01-13 09:00:00 (hour=9)
  - UTC: 2025-01-13 09:01:00+10:00 -> Local: 2025-01-13 09:01:00 (hour=9)
  - UTC: 2025-01-13 09:02:00+10:00 -> Local: 2025-01-13 09:02:00 (hour=9)
  - UTC: 2025-01-13 09:03:00+10:00 -> Local: 2025-01-13 09:03:00 (hour=9)
  - UTC: 2025-01-13 09:04:00+10:00 -> Local: 2025-01-13 09:04:00 (hour=9)

## SAMPLE DATA

First 5 bars:

  - 2025-01-13 09:00:00+10:00 | NQH5 | O=21027.50 H=21027.50 L=20959.25 C=20992.50 V=880
  - 2025-01-13 09:01:00+10:00 | NQH5 | O=20993.75 H=21000.75 L=20981.25 C=20981.50 V=267
  - 2025-01-13 09:02:00+10:00 | NQH5 | O=20982.25 H=20986.00 L=20970.75 C=20977.75 V=182
  - 2025-01-13 09:03:00+10:00 | NQH5 | O=20977.75 H=20985.75 L=20977.50 C=20985.25 V=102
  - 2025-01-13 09:04:00+10:00 | NQH5 | O=20986.00 H=20987.50 L=20973.00 C=20975.00 V=110

---

## VERDICT

[OK] DATA INTEGRITY VERIFIED

All checks passed. Data is ready for feature engineering and backtesting.
