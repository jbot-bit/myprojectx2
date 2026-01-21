# EDGE_CANDIDATES 47-48 RAW DUMP

**Total Candidates**: 2
**Purpose**: Verification for testfix2.txt

## Candidate 47

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 1000 ORB - RR1.0 FULL

### Hypothesis

1000 ORB breakout with FULL SL mode. Entry: First 1m close outside ORB after 10:05. Stop: Opposite ORB edge (FULL mode). Target: RR=1.0. Scan window: 10:05 → 12:00 (ISOLATION mode: force exit at 12:00). Expected: 0.055R avg (257 trades), 3/3 positive split stability.

### Metrics - 365d

```json
{
  "trades": 257,
  "win_rate": 0.5291828793774319,
  "avg_r": 0.0550654031387859,
  "total_r": 14.151808606667998
}
```

### Metrics - Splits

```json
{
  "stability": "3/3 positive",
  "split1_avg_r": 0.042,
  "split2_avg_r": 0.061,
  "split3_avg_r": 0.062
}
```

### Filter Spec

```json
{
  "type": "Asia ORB - Isolation Mode",
  "description": "ISOLATION mode: force exit at 12:00",
  "scan_window_start": "10:05",
  "scan_window_end": "12:00",
  "filters_applied": []
}
```

### Test Config

```json
{
  "orb_time": "1000",
  "orb_duration_min": 5,
  "entry_rule": "First 1m close outside ORB after 10:05",
  "stop_rule": "Opposite ORB edge (FULL mode)",
  "sl_mode": "FULL",
  "target_rule": "RR=1.0",
  "rr": 1.0,
  "scan_window": "10:05 \u2192 12:00"
}
```

---

## Candidate 48

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 1000 ORB - RR2.0 HALF

### Hypothesis

1000 ORB breakout with HALF SL mode. Entry: First 1m close outside ORB after 10:05. Stop: ORB midpoint (HALF mode). Target: RR=2.0. Scan window: 10:05 → 12:00 (ISOLATION mode: force exit at 12:00). Expected: 0.054R avg (257 trades), 3/3 positive split stability.

### Metrics - 365d

```json
{
  "trades": 257,
  "win_rate": 0.3540856031128405,
  "avg_r": 0.0535644706419385,
  "total_r": 13.766068954978214
}
```

### Metrics - Splits

```json
{
  "stability": "3/3 positive",
  "split1_avg_r": 0.13,
  "split2_avg_r": 0.005,
  "split3_avg_r": 0.027
}
```

### Filter Spec

```json
{
  "type": "Asia ORB - Isolation Mode",
  "description": "ISOLATION mode: force exit at 12:00",
  "scan_window_start": "10:05",
  "scan_window_end": "12:00",
  "filters_applied": []
}
```

### Test Config

```json
{
  "orb_time": "1000",
  "orb_duration_min": 5,
  "entry_rule": "First 1m close outside ORB after 10:05",
  "stop_rule": "ORB midpoint (HALF mode)",
  "sl_mode": "HALF",
  "target_rule": "RR=2.0",
  "rr": 2.0,
  "scan_window": "10:05 \u2192 12:00"
}
```

---
