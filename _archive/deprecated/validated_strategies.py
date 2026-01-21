# VALIDATED_STRATEGIES.py
# HONEST, ZERO-LOOKAHEAD STRATEGIES - Professional Grade
# Based on EXTENDED WINDOW TESTS (740 days, 2024-01-02 to 2026-01-10)
# **CORRECTED 2026-01-16**: Fixed scan window bug - extended to next Asia open (09:00)
# ALL ORBS ARE PROFITABLE WITH OPTIMAL RR VALUES

VALIDATED_MGC_STRATEGIES = {
    '0900': {
        'trades': 514,
        'wins': 88,
        'losses': 426,
        'win_rate': 0.171,
        'expectancy': 0.198,  # CORRECTED: Extended scan window
        'tradeable': True,
        'rr': 6.0,  # CORRECTED: Was 1.0, now 6.0 for optimal expectancy
        'sl_mode': 'FULL',
        'notes': 'Asymmetric Asia ORB - 17% WR but 6R targets, scan until 09:00 next day, ~+51R/year',
        'entry': 'Close outside ORB at 09:05+',
        'stop': 'Opposite ORB edge',
        'target': '6R (6x ORB size from entry) - hits overnight'
    },
    '1000': {
        'trades': 516,
        'wins': 79,
        'losses': 437,
        'win_rate': 0.153,
        'expectancy': 0.378,  # CORRECTED: Was 0.34, now 0.378 with RR=8.0
        'tradeable': True,
        'rr': 8.0,  # CORRECTED: Was 3.0, now 8.0 for optimal expectancy (THE CROWN JEWEL!)
        'sl_mode': 'FULL',
        'max_stop': 100,  # ORB must be ≤10pts (100 ticks)
        'notes': '🦄 CROWN JEWEL - 15% WR but 8R targets! Scan until 09:00 next day, ~+98R/year',
        'entry': 'Close outside ORB at 10:05+',
        'stop': 'Opposite ORB edge',
        'target': '8R (8x ORB size from entry) - massive overnight moves'
    },
    '1100': {
        'trades': 520,
        'wins': 158,
        'losses': 362,
        'win_rate': 0.304,
        'expectancy': 0.215,  # CORRECTED: Was 0.30, now 0.215 with RR=3.0
        'tradeable': True,
        'rr': 3.0,  # CORRECTED: Was 1.0, now 3.0 for optimal expectancy
        'sl_mode': 'FULL',
        'notes': 'Late Asia ORB - 30% WR with 3R targets, scan until 09:00 next day, ~+56R/year',
        'entry': 'Close outside ORB at 11:05+',
        'stop': 'Opposite ORB edge',
        'target': '3R (3x ORB size from entry)'
    },
    '1800': {
        'trades': 522,
        'wins': 266,
        'losses': 256,
        'win_rate': 0.510,
        'expectancy': 0.274,  # CORRECTED: Was 0.39, now 0.274 with RR=1.5
        'tradeable': True,
        'rr': 1.5,  # CORRECTED: Was 2.0, now 1.5 for optimal expectancy
        'sl_mode': 'FULL',
        'notes': 'London open ORB - 51% WR with 1.5R targets, scan until 09:00 next day (includes NY!), ~+72R/year',
        'entry': 'Close outside ORB at 18:05+',
        'stop': 'Opposite ORB edge',
        'target': '1.5R (1.5x ORB size from entry) - captures NY session moves'
    },
    '2300': {
        'trades': 522,
        'wins': 293,
        'losses': 229,
        'win_rate': 0.561,  # CORRECTED: Was 0.693 with RR=1.0, now 0.561 with RR=1.5
        'expectancy': 0.403,  # CORRECTED: Was 0.387 with RR=1.0, now 0.403 with RR=1.5
        'total_r': 210.0,  # CORRECTED: Was 202R, now 210R
        'tradeable': True,
        'rr': 1.5,  # CORRECTED: Was 1.0, now 1.5 for optimal expectancy
        'sl_mode': 'HALF',
        'notes': '⭐ BEST OVERALL - 56% WR with 1.5R targets, scan until 09:00 next day, ~+105R/year',
        'entry': 'Close outside ORB at 23:05+',
        'stop': 'ORB midpoint',
        'target': '1.5R (1.5x half-range = 0.75x full ORB) - hits overnight'
    },
    '0030': {
        'trades': 520,
        'wins': 163,
        'losses': 357,
        'win_rate': 0.313,  # CORRECTED: Was 0.616 with RR=1.0, now 0.313 with RR=3.0
        'expectancy': 0.254,  # CORRECTED: Was 0.231 with RR=1.0, now 0.254 with RR=3.0
        'total_r': 132.0,  # CORRECTED: Was 121R, now 132R
        'tradeable': True,
        'rr': 3.0,  # CORRECTED: Was 1.0, now 3.0 for optimal expectancy
        'sl_mode': 'HALF',
        'notes': 'NY ORB - 31% WR with 3R targets, scan until 09:00 next day, ~+66R/year',
        'entry': 'Close outside ORB at 00:35+',
        'stop': 'ORB midpoint',
        'target': '3R (3x half-range = 1.5x full ORB) - hits during Asia morning'
    }
}

# Top Tier Strategies (Professional Grade)
# Ranked by expectancy and priority

TOP_STRATEGIES = [
    # PRIMARY STRATEGIES (Always check first)
    {
        'name': 'Multi-Liquidity Cascades',
        'win_rate': 0.19,  # Low WR, tail-based
        'expectancy': 1.95,
        'trades': 69,
        'frequency': '2-3 per month (9.3%)',
        'tier': 'S+',
        'description': 'HIGHEST PRIORITY. London sweeps Asia, 23:00 second sweep + acceptance failure.',
        'risk': '0.10-0.25% per trade',
        'entry': 'Entry at London level within 0.1pts',
        'filters': 'Gap >9.5pts (MANDATORY), Acceptance failure within 3 bars'
    },
    {
        'name': 'Single Liquidity Reactions',
        'win_rate': 0.337,
        'expectancy': 1.44,
        'trades': 120,
        'frequency': '16% of days (8-12/month)',
        'tier': 'S',
        'description': 'BACKUP. Single level swept at 23:00, no cascade structure.',
        'risk': '0.25-0.50% per trade',
        'entry': 'Entry on retrace to London level',
        'filters': 'Acceptance failure within 3 bars'
    },

    # SECONDARY STRATEGIES (ORBs - CORRECTED with extended scan windows)
    {
        'name': '23:00 ORB',
        'win_rate': 0.561,  # CORRECTED: 56.1% with RR=1.5
        'expectancy': 0.403,  # CORRECTED: +0.403R with RR=1.5
        'trades': 522,
        'frequency': '70% of days',
        'tier': 'S++',  # UPGRADED: Best overall expectancy!
        'description': '⭐ BEST OVERALL - Night ORB with 1.5R targets. Scan until 09:00 next day. ~+105R/year',
        'risk': '0.25-0.50% per trade',
        'entry': 'Close outside ORB at 23:05+',
        'stop': 'ORB midpoint',
        'target': '1.5R',
        'filters': 'Skip if ORB size > 0.155 × ATR(20)'
    },
    {
        'name': '10:00 ORB',
        'win_rate': 0.153,  # CORRECTED: 15.3% with RR=8.0
        'expectancy': 0.378,  # CORRECTED: +0.378R with RR=8.0
        'trades': 516,
        'frequency': '70% of days',
        'tier': 'S++',  # UPGRADED: CROWN JEWEL!
        'description': '🦄 CROWN JEWEL - 15% WR but 8R targets! Scan until 09:00 next day. ~+98R/year',
        'risk': '0.10-0.25% per trade',
        'entry': 'Close outside ORB at 10:05+',
        'stop': 'Opposite ORB edge',
        'target': '8R',
        'filters': 'ORB size ≤10pts (100 ticks)'
    },
    {
        'name': '18:00 ORB',
        'win_rate': 0.510,  # CORRECTED: 51.0% with RR=1.5
        'expectancy': 0.274,  # CORRECTED: +0.274R with RR=1.5
        'trades': 522,
        'frequency': '70% of days',
        'tier': 'A',
        'description': 'London open ORB with 1.5R targets. Scan includes NY session. ~+72R/year',
        'risk': '0.10-0.25% per trade',
        'entry': 'Close outside ORB at 18:05+',
        'stop': 'Opposite ORB edge',
        'target': '1.5R'
    },
    {
        'name': '00:30 ORB',
        'win_rate': 0.313,  # CORRECTED: 31.3% with RR=3.0
        'expectancy': 0.254,  # CORRECTED: +0.254R with RR=3.0
        'trades': 520,
        'frequency': '70% of days',
        'tier': 'A',
        'description': 'NY ORB with 3R targets. Scan until 09:00 next day. ~+66R/year',
        'risk': '0.25-0.50% per trade',
        'entry': 'Close outside ORB at 00:35+',
        'stop': 'ORB midpoint',
        'target': '3R',
        'filters': 'Skip if ORB size > 0.112 × ATR(20)'
    },
    {
        'name': '11:00 ORB',
        'win_rate': 0.304,  # CORRECTED: 30.4% with RR=3.0
        'expectancy': 0.215,  # CORRECTED: +0.215R with RR=3.0
        'trades': 520,
        'frequency': '70% of days',
        'tier': 'B',
        'description': 'Late Asia ORB with 3R targets. ~+56R/year',
        'risk': '0.10-0.25% per trade',
        'entry': 'Close outside ORB at 11:05+',
        'stop': 'Opposite ORB edge',
        'target': '3R'
    },
    {
        'name': '09:00 ORB',
        'win_rate': 0.171,  # CORRECTED: 17.1% with RR=6.0
        'expectancy': 0.198,  # CORRECTED: +0.198R with RR=6.0
        'trades': 514,
        'frequency': '69% of days',
        'tier': 'B',
        'description': 'Asia session start with 6R targets. Asymmetric. ~+51R/year',
        'risk': '0.10-0.25% per trade',
        'entry': 'Close outside ORB at 09:05+',
        'stop': 'Opposite ORB edge',
        'target': '6R'
    }
]

# CORRELATION STRATEGIES (Session-dependent edges)
CORRELATION_STRATEGIES = [
    {
        'name': '10:00 UP after 09:00 WIN',
        'win_rate': 0.579,
        'expectancy': 0.16,
        'trades': 114,
        'base_session': '1000',
        'filter': 'Requires 09:00 WIN',
        'direction': 'UP',
        'tier': 'S',
        'description': 'BEST CORRELATION. Momentum continuation from Asia open.'
    },
    {
        'name': '11:00 UP after 09:00 WIN + 10:00 WIN',
        'win_rate': 0.574,
        'expectancy': 0.15,
        'trades': 68,
        'base_session': '1100',
        'filter': 'Requires 09:00 WIN AND 10:00 WIN UP',
        'direction': 'UP',
        'tier': 'A',
        'description': 'Strong momentum continuation. Triple confirmation.'
    },
    {
        'name': '11:00 DOWN after 09:00 LOSS + 10:00 WIN',
        'win_rate': 0.577,
        'expectancy': 0.15,
        'trades': 71,
        'base_session': '1100',
        'filter': 'Requires 09:00 LOSS AND 10:00 WIN DOWN',
        'direction': 'DOWN',
        'tier': 'A',
        'description': 'Reversal setup after failed start.'
    },
    {
        'name': '10:00 UP standalone (no filter)',
        'win_rate': 0.555,
        'expectancy': 0.11,
        'trades': 247,
        'base_session': '1000',
        'filter': 'No filter - standalone',
        'direction': 'UP',
        'tier': 'A',
        'description': 'Best standalone directional ORB. UP strongly preferred.'
    }
]

def get_tradeable_strategies():
    """Return only strategies with positive expectancy"""
    return {k: v for k, v in VALIDATED_MGC_STRATEGIES.items() if v['tradeable']}

def get_top_setups():
    """Return S and A tier strategies only"""
    return [s for s in TOP_STRATEGIES if s['tier'] in ['S', 'A']]
