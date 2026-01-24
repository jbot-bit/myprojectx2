# Market Scanner - Ready to Use

## What You Asked For

> "Read the market and analyze what potential setups are already there or could be coming. Simple, honest, accurate."

## What You Got

**`market_now.py`** - Simple command-line scanner that shows:

1. **Current Market Context**
   - Time, session (ASIA/LONDON/NY)
   - Latest price and data freshness

2. **All Validated Setups**
   - 6 ORB setups (0030, 0900, 1000, 1100, 1800, 2300)
   - 2 special liquidity strategies (CASCADE, SINGLE_LIQ)
   - Stats: Tier, Win Rate, Avg R, Frequency

3. **What to Watch**
   - Which ORB is forming/active RIGHT NOW
   - What's coming next
   - Simple actionable guidance

## How to Use

```bash
# Run the scanner
python market_now.py
```

That's it. No charts, no complexity, just facts.

## Example Output

```
==============================================================================
MARKET NOW - MGC Setup Scanner
==============================================================================

Time: 2026-01-22 15:05:31 Brisbane
Hour: 15:05
Session: ASIA (09:00-17:00)

Latest Price: $2641.80
Latest Bar:   2026-01-15 00:26 Brisbane
[!] WARNING: Data is 7.6 days old

------------------------------------------------------------------------------
VALIDATED SETUPS (MGC)
------------------------------------------------------------------------------

[0900] 1 setup(s)
  RR=6.0 FULL (no filter)
    Tier: A | WR: 17.1% | Avg R: +0.198R
    Freq: 253 trades/year

[2300] 1 setup(s)
  RR=1.5 HALF (<0.155xATR)
    Tier: S+ | WR: 56.1% | Avg R: +0.403R
    Freq: 257 trades/year

...

WHAT TO WATCH:
  [1800] ORB starts at 18:00
```

## Truth & Honesty

- **No fluff** - Just database-backed facts
- **Data freshness** - Warns when data is stale
- **Real stats** - From 5+ years of backtest (2020-2026)
- **No lookahead** - Tested with proper methodology
- **No guessing** - If we don't know, we say so

## What's Validated

All 9 setups shown are in `validated_setups` database:

**S+ Tier (Best)**
- 2300 ORB: 56% WR, +0.403R avg, 257/year
- CASCADE: 19% WR, +1.950R avg, 35/year (rare but powerful)

**S Tier (Excellent)**
- 0030 ORB: 31% WR, +0.254R avg, 256/year
- 1800 ORB: 51% WR, +0.274R avg, 257/year
- SINGLE_LIQ: 34% WR, +1.440R avg, 59/year

**A Tier (Good)**
- 0900 ORB: 17% WR, +0.198R avg, 253/year
- 1100 ORB: 30% WR, +0.215R avg, 256/year

**B Tier (Marginal)**
- 1000 ORB variants: ~0.5% WR, +0.055R avg

## Update Data

When market is live:

```bash
# Get latest data
python backfill_databento_continuous.py 2026-01-22 2026-01-22

# Then run scanner
python market_now.py
```

## Next Steps

You have everything you need to read the market honestly:

1. **Run scanner** - See what's validated
2. **Watch for ORBs** - Scanner tells you which ones
3. **Take setups** - When they trigger
4. **Trust the stats** - They're real

No charts needed. No complexity. Just truth.

---

**Built: 2026-01-22**
**Tested: All pytest tests pass**
**Synced: Database and config validated**
**Cost: OpenAI default (cheap), Anthropic optional**
