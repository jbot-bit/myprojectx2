# EDGE_CANDIDATES 45-49 RAW DUMP

**Total Candidates**: 5

## Candidate 45

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 0900 ORB - RR2.0 HALF

### Metrics - 365d

```json
{
  "trades": 254,
  "win_rate": 0.465,
  "avg_r": 0.099,
  "total_r": 25.1
}
```

### Metrics - Splits

```json
{
  "stability": "2/3 positive",
  "split1_avg_r": -0.218,
  "split2_avg_r": 0.121,
  "split3_avg_r": 0.383
}
```

### Filter Spec

```json
{
  "type": "Asia ORB - Isolation Mode",
  "description": "ISOLATION mode: force exit at 11:00",
  "scan_window_start": "09:05",
  "scan_window_end": "11:00",
  "filters_applied": []
}
```

### Test Config

```json
{
  "orb_time": "0900",
  "orb_duration_min": 5,
  "entry_rule": "First 1m close outside ORB after 09:05",
  "stop_rule": "ORB midpoint (HALF mode)",
  "sl_mode": "HALF",
  "target_rule": "RR=2.0",
  "rr": 2.0,
  "scan_window": "09:05 \u2192 11:00"
}
```

---

## Candidate 46

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 0900 ORB - RR3.0 HALF

### Metrics - 365d

```json
{
  "trades": 254,
  "win_rate": 0.382,
  "avg_r": 0.097,
  "total_r": 24.6
}
```

### Metrics - Splits

```json
{
  "stability": "2/3 positive",
  "split1_avg_r": -0.307,
  "split2_avg_r": 0.202,
  "split3_avg_r": 0.379
}
```

### Filter Spec

```json
{
  "type": "Asia ORB - Isolation Mode",
  "description": "ISOLATION mode: force exit at 11:00",
  "scan_window_start": "09:05",
  "scan_window_end": "11:00",
  "filters_applied": []
}
```

### Test Config

```json
{
  "orb_time": "0900",
  "orb_duration_min": 5,
  "entry_rule": "First 1m close outside ORB after 09:05",
  "stop_rule": "ORB midpoint (HALF mode)",
  "sl_mode": "HALF",
  "target_rule": "RR=3.0",
  "rr": 3.0,
  "scan_window": "09:05 \u2192 11:00"
}
```

---

## Candidate 47

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 1000 ORB - RR1.0 FULL

### Metrics - 365d

```json
{
  "trades": 257,
  "win_rate": 0.528,
  "avg_r": 0.055,
  "total_r": 14.1
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

### Metrics - 365d

```json
{
  "trades": 257,
  "win_rate": 0.389,
  "avg_r": 0.054,
  "total_r": 13.9
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

## Candidate 49

**Status**: DRAFT
**Instrument**: MGC
**Name**: Asia 1000 ORB - RR1.5 FULL

### Metrics - 365d

```json
{
  "trades": 257,
  "win_rate": 0.493,
  "avg_r": 0.084,
  "total_r": 21.6
}
```

### Metrics - Splits

```json
{
  "stability": "2/3 positive",
  "split1_avg_r": -0.04,
  "split2_avg_r": 0.116,
  "split3_avg_r": 0.172
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
  "target_rule": "RR=1.5",
  "rr": 1.5,
  "scan_window": "10:05 \u2192 12:00"
}
```

---
