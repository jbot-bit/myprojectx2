# SLIPPAGE TRACKING SYSTEM

**Purpose**: Measure actual execution slippage vs intended prices.

**Philosophy**: Don't assume fixed slippage. Measure it.

---

## Quick Start

### 1. Initialize (one-time)

```bash
python scripts/init_slippage_tracker.py
```

Creates `slippage_log` table in database.

### 2. Log Fills

**Entry fill**:
```bash
python scripts/log_fill.py entry <trade_id> <direction> <intended> <actual>
```

**Exit fill**:
```bash
python scripts/log_fill.py exit <trade_id> <intended> <actual>
```

**Examples**:
```bash
# LONG entry: intended 2650.5, filled at 2650.6 (0.1 higher = 1 tick worse)
python scripts/log_fill.py entry TRADE_001 LONG 2650.5 2650.6 --setup_id MGC_1800_BOTH_TIER1

# Exit: intended 2653.0, filled at 2652.8 (0.2 lower = 2 ticks worse for LONG exit)
python scripts/log_fill.py exit TRADE_001 2653.0 2652.8
```

### 3. View Statistics

**All fills**:
```bash
python scripts/slippage_stats.py
```

**Filter by instrument**:
```bash
python scripts/slippage_stats.py --instrument MGC
```

**Filter by setup**:
```bash
python scripts/slippage_stats.py --setup_id MGC_1800_BOTH_TIER1
```

**Last 30 days only**:
```bash
python scripts/slippage_stats.py --days 30
```

---

## Understanding Slippage Direction

### Entry Slippage

**LONG entry**:
- Positive slippage = filled HIGHER than intended (worse)
- Negative slippage = filled LOWER than intended (better)

**SHORT entry**:
- Positive slippage = filled LOWER than intended (worse)
- Negative slippage = filled HIGHER than intended (better)

### Exit Slippage

**LONG exit**:
- Positive slippage = filled LOWER than intended (worse)
- Negative slippage = filled HIGHER than intended (better)

**SHORT exit**:
- Positive slippage = filled HIGHER than intended (worse)
- Negative slippage = filled LOWER than intended (better)

**Convention**: Positive slippage = costs you money (always worse)

---

## Example Workflow

### Paper Trading Day 1

```bash
# Trade 1: 1800 ORB LONG
python scripts/log_fill.py entry PT_001 LONG 2650.5 2650.7 --setup_id MGC_1800_BOTH_TIER1
# ... trade runs ...
python scripts/log_fill.py exit PT_001 2653.0 2652.9

# Trade 2: 2300 ORB SHORT
python scripts/log_fill.py entry PT_002 SHORT 2655.0 2654.8 --setup_id MGC_2300_BOTH_TIER1
# ... trade runs ...
python scripts/log_fill.py exit PT_002 2652.0 2652.2

# View stats
python scripts/slippage_stats.py
```

### After 30 Trades

```bash
# Comprehensive analysis
python scripts/slippage_stats.py

# Check specific setup
python scripts/slippage_stats.py --setup_id MGC_1800_BOTH_TIER1
```

**Output shows**:
- Median slippage (typical trade)
- 75th percentile (above-average slippage)
- 90th percentile (worst-case for conservative modeling)

**Use 90th percentile for backtest cost assumptions** (conservative).

---

## Statistics Explained

### Key Metrics

**Median**: Typical slippage for a normal trade
- Use this for expected slippage

**75th Percentile**: Above-average slippage
- 25% of trades will be worse than this

**90th Percentile**: Conservative worst-case
- 10% of trades will be worse than this
- **Use this for backtesting** (conservative assumption)

### Interpreting Results

**Median round-trip slippage**:
- <0.5 ticks: Excellent execution
- 0.5-1.0 ticks: Good execution
- 1.0-1.5 ticks: Acceptable
- 1.5-2.0 ticks: Marginal (review execution)
- >2.0 ticks: Poor (fix execution issues)

**Action based on results**:
- If median <1.0: Use SLIPPAGE_TICKS = 1.0 in backtest
- If median 1.0-1.5: Use SLIPPAGE_TICKS = 1.5 in backtest
- If median >1.5: Use SLIPPAGE_TICKS = 2.0 in backtest (worst-case)

---

## Database Schema

```sql
CREATE TABLE slippage_log (
    trade_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    instrument VARCHAR NOT NULL,
    setup_id VARCHAR,

    -- Entry
    entry_direction VARCHAR NOT NULL,  -- 'LONG' or 'SHORT'
    intended_entry_price DOUBLE NOT NULL,
    actual_entry_price DOUBLE NOT NULL,
    entry_slippage_ticks DOUBLE NOT NULL,

    -- Exit
    intended_exit_price DOUBLE,
    actual_exit_price DOUBLE,
    exit_slippage_ticks DOUBLE,

    -- Round-trip
    roundtrip_slippage_ticks DOUBLE,

    -- Metadata
    notes VARCHAR,
    logged_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
```

---

## Integration with Strategy Logic

**Separation of Concerns**:
- Slippage tracking is **separate** from strategy execution
- Strategy logic doesn't know about slippage tracking
- You manually log fills after each trade

**Why manual?**:
- Deterministic (you control when fills are logged)
- No assumptions (measure actual fills)
- Simple (no integration complexity)
- Flexible (works with any execution method)

**Future**: Could automate by parsing broker execution logs.

---

## Workflow Summary

```
1. Initialize tracker (one-time)
   python scripts/init_slippage_tracker.py

2. Trade executes
   - Note intended entry price (from strategy rule)
   - Note actual fill price (from broker)

3. Log entry fill
   python scripts/log_fill.py entry <id> <dir> <intended> <actual>

4. Trade exits
   - Note intended exit price (stop/target)
   - Note actual fill price (from broker)

5. Log exit fill
   python scripts/log_fill.py exit <id> <intended> <actual>

6. Review stats periodically (daily/weekly)
   python scripts/slippage_stats.py

7. Adjust backtest assumptions based on actual data
   SLIPPAGE_TICKS = <90th percentile from stats>
```

---

## Files

**Created**:
- `scripts/init_slippage_tracker.py` - Initialize database table
- `scripts/log_fill.py` - Log entry/exit fills
- `scripts/slippage_stats.py` - Analyze slippage statistics
- `SLIPPAGE_TRACKING_README.md` - This file

**Database**:
- `slippage_log` table in `data/db/gold.db`

---

## Design Principles

1. **Minimal**: Simple scripts, no complex integration
2. **Deterministic**: Manual logging, no assumptions
3. **Separate**: Independent from strategy logic
4. **Measurable**: Real data, not estimates
5. **Actionable**: Stats inform backtest assumptions

---

## Next Steps

1. **Initialize tracker** (run init script)
2. **Start paper trading** and log every fill
3. **After 20-30 trades**: Review stats
4. **Update backtest costs** with actual 90th percentile
5. **Re-validate setups** with real execution costs
6. **Go live** with accurate cost expectations

---

**Remember**: Don't assume 0.5 or 2.0 ticks slippage. **Measure it.**
