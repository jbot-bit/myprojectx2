"""
SETUP SCORING - Explain WHY setups rank the way they do

Minimal addition to existing architecture.
Shows scoring breakdown for transparency.
"""

from typing import Dict, List


def explain_setup_score(setup: Dict) -> Dict:
    """
    Explain why a setup scores the way it does.

    Returns breakdown of scoring factors.
    """
    tier = setup.get('tier', 'C')
    avg_r = setup.get('avg_r', 0.0)
    win_rate = setup.get('win_rate', 0.0)
    annual_trades = setup.get('annual_trades', 0)

    # Tier scoring (existing system)
    tier_scores = {'S+': 100, 'S': 80, 'A': 60, 'B': 40, 'C': 20}
    tier_score = tier_scores.get(tier, 0)

    # Quality metrics
    expectancy_score = avg_r * 100  # Scale to 0-100
    frequency_score = min(annual_trades / 3, 100)  # Cap at 300 trades/year = 100
    consistency_score = win_rate  # Already 0-100

    # Combined score (weighted)
    total_score = (
        tier_score * 0.40 +          # 40% weight on tier
        expectancy_score * 0.30 +     # 30% weight on avg R
        consistency_score * 0.20 +    # 20% weight on WR
        frequency_score * 0.10        # 10% weight on frequency
    )

    return {
        'total_score': round(total_score, 2),
        'breakdown': {
            'tier': {'value': tier, 'score': tier_score, 'weight': '40%'},
            'expectancy': {'value': f'+{avg_r:.3f}R', 'score': round(expectancy_score, 2), 'weight': '30%'},
            'consistency': {'value': f'{win_rate:.1f}%', 'score': round(consistency_score, 2), 'weight': '20%'},
            'frequency': {'value': f'{annual_trades}/year', 'score': round(frequency_score, 2), 'weight': '10%'}
        },
        'rank_factors': {
            'primary': f"{tier} tier",
            'secondary': f"+{avg_r:.3f}R avg"
        }
    }


def compare_setups(setup1: Dict, setup2: Dict) -> str:
    """
    Compare two setups and explain which wins and why.
    """
    score1 = explain_setup_score(setup1)
    score2 = explain_setup_score(setup2)

    name1 = f"{setup1.get('instrument', 'MGC')} {setup1.get('orb_time', '????')}"
    name2 = f"{setup2.get('instrument', 'MGC')} {setup2.get('orb_time', '????')}"

    if score1['total_score'] > score2['total_score']:
        winner = name1
        loser = name2
        winner_setup = setup1
        loser_setup = setup2
        winner_score = score1
        loser_score = score2
    else:
        winner = name2
        loser = name1
        winner_setup = setup2
        loser_setup = setup1
        winner_score = score2
        loser_score = score1

    explanation = f"""
SETUP COMPARISON
================

WINNER: {winner}
Score: {winner_score['total_score']:.2f}/100

LOSER: {loser}
Score: {loser_score['total_score']:.2f}/100

WHY {winner} WINS:
------------------
Primary: {winner_score['rank_factors']['primary']}
Secondary: {winner_score['rank_factors']['secondary']}

Breakdown:
- Tier: {winner_setup['tier']} ({winner_score['breakdown']['tier']['score']} pts × 40% = {winner_score['breakdown']['tier']['score'] * 0.4:.1f})
- Expectancy: {winner_score['breakdown']['expectancy']['value']} ({winner_score['breakdown']['expectancy']['score']:.1f} pts × 30% = {winner_score['breakdown']['expectancy']['score'] * 0.3:.1f})
- Win Rate: {winner_score['breakdown']['consistency']['value']} ({winner_score['breakdown']['consistency']['score']:.1f} pts × 20% = {winner_score['breakdown']['consistency']['score'] * 0.2:.1f})
- Frequency: {winner_score['breakdown']['frequency']['value']} ({winner_score['breakdown']['frequency']['score']:.1f} pts × 10% = {winner_score['breakdown']['frequency']['score'] * 0.1:.1f})

{loser} LOST BECAUSE:
------------------
- Tier: {loser_setup['tier']} vs {winner_setup['tier']}
- Avg R: {loser_setup['avg_r']:+.3f}R vs {winner_setup['avg_r']:+.3f}R
"""

    return explanation


def rank_all_setups(setups: List[Dict]) -> List[Dict]:
    """
    Rank all setups with scoring breakdown.
    Uses EXISTING ranking logic: tier first, then avg_r.
    """
    # Add scores to each setup
    scored_setups = []
    for setup in setups:
        score_breakdown = explain_setup_score(setup)
        setup_with_score = setup.copy()
        setup_with_score['_score'] = score_breakdown['total_score']
        setup_with_score['_score_breakdown'] = score_breakdown
        scored_setups.append(setup_with_score)

    # Sort by existing logic: tier first, then avg_r
    tier_order = {'S+': 0, 'S': 1, 'A': 2, 'B': 3, 'C': 4}

    sorted_setups = sorted(
        scored_setups,
        key=lambda x: (tier_order.get(x.get('tier', 'C'), 99), -x.get('avg_r', 0))
    )

    return sorted_setups


if __name__ == "__main__":
    # Test scoring system

    # Example setups from validated_setups
    setup_1000 = {
        'instrument': 'MGC',
        'orb_time': '1000',
        'tier': 'S+',
        'win_rate': 15.3,
        'avg_r': 0.378,
        'annual_trades': 254,
        'rr': 8.0,
        'sl_mode': 'FULL'
    }

    setup_2300 = {
        'instrument': 'MGC',
        'orb_time': '2300',
        'tier': 'S+',
        'win_rate': 56.1,
        'avg_r': 0.403,
        'annual_trades': 257,
        'rr': 1.5,
        'sl_mode': 'HALF'
    }

    setup_0900 = {
        'instrument': 'MGC',
        'orb_time': '0900',
        'tier': 'A',
        'win_rate': 17.1,
        'avg_r': 0.198,
        'annual_trades': 253,
        'rr': 6.0,
        'sl_mode': 'FULL'
    }

    print("="*80)
    print("SCORING BREAKDOWN EXAMPLES")
    print("="*80)

    for setup in [setup_1000, setup_2300, setup_0900]:
        score = explain_setup_score(setup)
        print(f"\n{setup['instrument']} {setup['orb_time']} ORB [{setup['tier']} tier]")
        print(f"Total Score: {score['total_score']:.2f}/100")
        print(f"Rank by: {score['rank_factors']['primary']} -> {score['rank_factors']['secondary']}")
        print("Breakdown:")
        for factor, details in score['breakdown'].items():
            print(f"  {factor.capitalize()}: {details['value']} = {details['score']:.1f} pts (weight: {details['weight']})")

    print("\n" + "="*80)
    print("COMPARISON: Why 2300 beats 1000")
    print("="*80)
    print(compare_setups(setup_2300, setup_1000))

    print("\n" + "="*80)
    print("RANKING ALL SETUPS")
    print("="*80)

    all_setups = [setup_1000, setup_2300, setup_0900]
    ranked = rank_all_setups(all_setups)

    for i, setup in enumerate(ranked, 1):
        print(f"\n#{i}: {setup['instrument']} {setup['orb_time']} (Score: {setup['_score']:.2f})")
        print(f"     Tier: {setup['tier']} | Avg R: +{setup['avg_r']:.3f}R | WR: {setup['win_rate']:.1f}%")
