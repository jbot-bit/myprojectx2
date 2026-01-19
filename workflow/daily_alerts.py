"""
Daily Setup Alerts - V2 (Zero Lookahead)
==========================================
Recommends tradeable ORB setups using ONLY information available at decision time.

**CRITICAL: NO SESSION TYPE FILTERS**
Session types (EXPANDED, CONSOLIDATION, etc.) are NOT known until after the session closes.
This script uses only PRE blocks, completed ORB outcomes, and completed session data.

Usage:
  python daily_alerts.py           # Today's morning prep
  python daily_alerts.py 2026-01-10   # Specific date

Based on HONEST V2 analysis with zero lookahead bias.
"""

import duckdb
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class SetupRecommendation:
    """Recommendation for an ORB setup"""
    orb_time: str
    orb_label: str
    direction: Optional[str]
    reason: str
    historical_wr: float
    historical_avg_r: float
    confidence: str  # HIGH, MEDIUM, LOW
    sample_size: int
    tradeable_at: str  # What time this setup becomes tradeable


class DailyAlertSystemV2:
    """Analyze daily setups with ZERO LOOKAHEAD"""

    ORB_LABELS = {
        "0900": "09:00 (Asia Open)",
        "1000": "10:00 (Asia Mid)",
        "1100": "11:00 (Asia Late)",
        "1800": "18:00 (London Open)",
        "2300": "23:00 (NY Futures)",
        "0030": "00:30 (NYSE Cash)",
    }

    def __init__(self, db_path: str = "gold.db"):
        self.con = duckdb.connect(db_path, read_only=True)

    def get_pre_asia_data(self, target_date: date) -> Optional[Dict]:
        """Get PRE_ASIA data (available at 09:00)"""
        row = self.con.execute("""
            SELECT
                pre_asia_high,
                pre_asia_low,
                pre_asia_range,
                (pre_asia_range / 0.1) as pre_asia_ticks
            FROM daily_features_v2
            WHERE date_local = ?
        """, [target_date]).fetchone()

        if not row or row[0] is None:
            return None

        return {
            "high": row[0],
            "low": row[1],
            "range": row[2],
            "range_ticks": row[3],
        }

    def get_previous_day_orbs(self, target_date: date) -> Optional[Dict]:
        """Get previous day's ORB outcomes (available at open next day)"""
        prev_date = target_date - timedelta(days=1)
        row = self.con.execute("""
            SELECT
                orb_0900_outcome,
                orb_1000_outcome,
                orb_1100_outcome,
                orb_1800_outcome
            FROM daily_features_v2
            WHERE date_local = ?
        """, [prev_date]).fetchone()

        if not row:
            return None

        return {
            "orb_0900": row[0],
            "orb_1000": row[1],
            "orb_1100": row[2],
            "orb_1800": row[3],
        }

    def get_historical_performance(
        self,
        orb_time: str,
        condition: str,
        params: List
    ) -> Dict:
        """Get historical performance for a setup"""
        query = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN orb_{orb_time}_outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                AVG(orb_{orb_time}_r_multiple) as avg_r,
                SUM(orb_{orb_time}_r_multiple) as total_r
            FROM daily_features_v2
            WHERE orb_{orb_time}_outcome IN ('WIN', 'LOSS')
              AND {condition}
        """

        result = self.con.execute(query, params).fetchone()
        total, wins, avg_r, total_r = result

        return {
            "total_trades": total or 0,
            "wins": wins or 0,
            "win_rate": wins / total if total else 0,
            "avg_r": avg_r or 0,
            "total_r": total_r or 0,
        }

    def analyze_0900(self, pre_asia: Dict) -> List[SetupRecommendation]:
        """Analyze 09:00 ORB (available: PRE_ASIA)"""
        recommendations = []

        if not pre_asia:
            return recommendations

        # Only recommend if PRE_ASIA > 50 ticks
        if pre_asia['range_ticks'] > 50:
            # Check overall performance with this filter
            hist = self.get_historical_performance(
                "0900",
                "(pre_asia_range / 0.1) > 50",
                []
            )

            if hist["total_trades"] >= 20:
                recommendations.append(SetupRecommendation(
                    orb_time="0900",
                    orb_label=self.ORB_LABELS["0900"],
                    direction=None,
                    reason=f"PRE_ASIA = {pre_asia['range_ticks']:.0f} ticks (>50 threshold)",
                    historical_wr=hist["win_rate"],
                    historical_avg_r=hist["avg_r"],
                    confidence="MEDIUM" if hist["win_rate"] > 0.51 else "LOW",
                    sample_size=hist["total_trades"],
                    tradeable_at="09:00",
                ))

        return recommendations

    def analyze_1000(self, pre_asia: Dict, prev_orbs: Optional[Dict]) -> List[SetupRecommendation]:
        """Analyze 10:00 ORB (available: PRE_ASIA, 09:00 ORB outcome if we took it)"""
        recommendations = []

        # 10:00 UP is the best standalone setup
        hist = self.get_historical_performance(
            "1000",
            "orb_1000_break_dir = 'UP'",
            []
        )

        if hist["total_trades"] >= 50:
            recommendations.append(SetupRecommendation(
                orb_time="1000",
                orb_label=self.ORB_LABELS["1000"],
                direction="UP",
                reason="Best standalone ORB (no filters needed)",
                historical_wr=hist["win_rate"],
                historical_avg_r=hist["avg_r"],
                confidence="HIGH",
                sample_size=hist["total_trades"],
                tradeable_at="10:00",
            ))

        # If we know 09:00 outcome (from previous day or if we tracked it today)
        # Note: In practice, this requires tracking 09:00 outcome live or having yesterday's data
        # For now, we'll show the baseline edge

        return recommendations

    def analyze_1100(self, pre_asia: Dict) -> List[SetupRecommendation]:
        """Analyze 11:00 ORB (available: PRE_ASIA, 09:00/10:00 outcomes if tracked)"""
        recommendations = []

        if not pre_asia:
            return recommendations

        # 11:00 UP with PRE_ASIA > 50 ticks
        if pre_asia['range_ticks'] > 50:
            hist = self.get_historical_performance(
                "1100",
                "orb_1100_break_dir = 'UP' AND (pre_asia_range / 0.1) > 50",
                []
            )

            if hist["total_trades"] >= 20:
                recommendations.append(SetupRecommendation(
                    orb_time="1100",
                    orb_label=self.ORB_LABELS["1100"],
                    direction="UP",
                    reason=f"PRE_ASIA = {pre_asia['range_ticks']:.0f} ticks (>50) + UP bias",
                    historical_wr=hist["win_rate"],
                    historical_avg_r=hist["avg_r"],
                    confidence="HIGH" if hist["win_rate"] > 0.54 else "MEDIUM",
                    sample_size=hist["total_trades"],
                    tradeable_at="11:00",
                ))

        # Note: ORB correlation edges (09:00 WIN + 10:00 WIN → 11:00 UP)
        # require tracking outcomes live, which is not in scope for morning prep

        return recommendations

    def analyze_1800(self, target_date: date) -> List[SetupRecommendation]:
        """Analyze 18:00 ORB (available at 18:00: PRE_LONDON, completed ASIA)"""
        recommendations = []

        # Get PRE_LONDON data
        pre_london_row = self.con.execute("""
            SELECT
                pre_london_high,
                pre_london_low,
                pre_london_range,
                (pre_london_range / 0.1) as pre_london_ticks
            FROM daily_features_v2
            WHERE date_local = ?
        """, [target_date]).fetchone()

        if not pre_london_row or pre_london_row[0] is None:
            # PRE_LONDON not available yet (it's only 07:00-09:00 in morning)
            # Baseline 18:00 recommendation
            hist = self.get_historical_performance(
                "1800",
                "1=1",  # No filter
                []
            )

            if hist["total_trades"] >= 50:
                recommendations.append(SetupRecommendation(
                    orb_time="1800",
                    orb_label=self.ORB_LABELS["1800"],
                    direction=None,
                    reason="Tradeable baseline (check PRE_LONDON at 18:00 for refinement)",
                    historical_wr=hist["win_rate"],
                    historical_avg_r=hist["avg_r"],
                    confidence="MEDIUM",
                    sample_size=hist["total_trades"],
                    tradeable_at="18:00",
                ))
            return recommendations

        pre_london_ticks = pre_london_row[3]

        # 18:00 DOWN with PRE_LONDON > 40 ticks
        if pre_london_ticks > 40:
            hist = self.get_historical_performance(
                "1800",
                "orb_1800_break_dir = 'DOWN' AND (pre_london_range / 0.1) > 40",
                []
            )

            if hist["total_trades"] >= 20:
                recommendations.append(SetupRecommendation(
                    orb_time="1800",
                    orb_label=self.ORB_LABELS["1800"],
                    direction="DOWN",
                    reason=f"PRE_LONDON = {pre_london_ticks:.0f} ticks (>40) + DOWN bias",
                    historical_wr=hist["win_rate"],
                    historical_avg_r=hist["avg_r"],
                    confidence="HIGH" if hist["win_rate"] > 0.53 else "MEDIUM",
                    sample_size=hist["total_trades"],
                    tradeable_at="18:00",
                ))

        return recommendations

    def generate_morning_prep(self, target_date: date) -> None:
        """Generate morning prep alerts (08:00-08:30 timeframe)"""

        # Get available data
        pre_asia = self.get_pre_asia_data(target_date)
        prev_orbs = self.get_previous_day_orbs(target_date)

        # Print header
        print("\n" + "="*80)
        print(f"MORNING PREP ALERT - {target_date.strftime('%A, %B %d, %Y')}")
        print("="*80)
        print("\n[V2 ZERO LOOKAHEAD - HONEST RECOMMENDATIONS ONLY]")

        # Print PRE_ASIA context
        print("\n" + "="*80)
        print("PRE_ASIA CONTEXT (07:00-09:00):")
        print("="*80)

        if pre_asia:
            print(f"  Range: {pre_asia['range_ticks']:.0f} ticks ({pre_asia['high']:.2f} - {pre_asia['low']:.2f})")

            if pre_asia['range_ticks'] > 50:
                print(f"  [VOLATILE] > 50 ticks - 09:00 and 11:00 may have edges")
            elif pre_asia['range_ticks'] < 30:
                print(f"  [QUIET] < 30 ticks - AVOID 09:00 ORB (historically poor)")
            else:
                print(f"  [NORMAL] 30-50 ticks - Neutral context")
        else:
            print("  Data not available yet (check back after 09:00)")

        # Print previous day context
        print("\n" + "="*80)
        print("PREVIOUS DAY ORB OUTCOMES:")
        print("="*80)

        if prev_orbs:
            print(f"  09:00: {prev_orbs.get('orb_0900', 'N/A')}")
            print(f"  10:00: {prev_orbs.get('orb_1000', 'N/A')}")
            print(f"  11:00: {prev_orbs.get('orb_1100', 'N/A')}")
            print(f"  18:00: {prev_orbs.get('orb_1800', 'N/A')}")
        else:
            print("  No previous day data available")

        # Generate recommendations
        all_recs = []

        # 09:00 analysis
        recs_0900 = self.analyze_0900(pre_asia) if pre_asia else []
        all_recs.extend(recs_0900)

        # 10:00 analysis (best baseline)
        recs_1000 = self.analyze_1000(pre_asia, prev_orbs)
        all_recs.extend(recs_1000)

        # 11:00 analysis
        recs_1100 = self.analyze_1100(pre_asia) if pre_asia else []
        all_recs.extend(recs_1100)

        # 18:00 analysis
        recs_1800 = self.analyze_1800(target_date)
        all_recs.extend(recs_1800)

        # Sort by avg_r
        all_recs.sort(key=lambda x: x.historical_avg_r, reverse=True)

        # Display recommendations
        print("\n" + "="*80)
        print("TODAY'S TRADEABLE SETUPS:")
        print("="*80)

        if all_recs:
            for i, rec in enumerate(all_recs, 1):
                direction_str = rec.direction if rec.direction else "Any direction"
                print(f"\n{i}. {rec.orb_label} - {direction_str}")
                print(f"   Reason: {rec.reason}")
                print(f"   Historical: WR={rec.historical_wr:.1%} | Avg R={rec.historical_avg_r:+.2f} | N={rec.sample_size}")
                print(f"   Confidence: {rec.confidence}")
                print(f"   Tradeable at: {rec.tradeable_at}")
        else:
            print("\nNo high-probability setups identified for morning session.")
            print("Focus on 10:00 ORB baseline (55.5% WR UP) as primary opportunity.")

        # Print what to avoid
        print("\n" + "="*80)
        print("SETUPS TO AVOID TODAY:")
        print("="*80)

        avoid_messages = []

        if pre_asia and pre_asia['range_ticks'] < 30:
            avoid_messages.append("  09:00 ORB (PRE_ASIA < 30 ticks = 40% WR historically)")

        avoid_messages.append("  10:00 DOWN (47% WR, negative expectancy)")
        avoid_messages.append("  23:00 ORB (49% WR, negative expectancy)")
        avoid_messages.append("  00:30 ORB (49% WR, negative expectancy)")

        for msg in avoid_messages:
            print(msg)

        # Print trading plan
        print("\n" + "="*80)
        print("RECOMMENDED TRADING PLAN:")
        print("="*80)
        print("\n  PRIMARY: 10:00 UP (55.5% WR, +0.11 R baseline)")
        print("           -> If 09:00 was WIN, increase confidence to 58% WR, +0.16 R")

        if pre_asia and pre_asia['range_ticks'] > 50:
            print(f"\n  SECONDARY: 09:00 ORB (PRE_ASIA > 50 ticks)")
            print(f"             11:00 UP (PRE_ASIA > 50 ticks = 55% WR, +0.10 R)")

        print("\n  TERTIARY: 18:00 ORB (52% WR baseline)")
        print("            -> Check PRE_LONDON at 18:00 for refinement")

        print("\n  SKIP: 23:00 and 00:30 (negative expectancy)")

        # Print monitoring notes
        print("\n" + "="*80)
        print("LIVE MONITORING NOTES:")
        print("="*80)
        print("\n  1. Track 09:00 ORB outcome (WIN/LOSS) for 10:00 correlation edge")
        print("  2. Track 09:00 + 10:00 outcomes for 11:00 correlation edges:")
        print("     - If 09:00 WIN + 10:00 WIN => 11:00 UP has 57% WR")
        print("     - If 09:00 LOSS + 10:00 WIN => 11:00 DOWN has 58% WR")
        print("  3. At 18:00, check PRE_LONDON range (17:00-18:00)")
        print("     - If PRE_LONDON > 40 ticks => Favor 18:00 DOWN (54% WR)")

        # Disclaimer
        print("\n" + "="*80)
        print("DISCLAIMER:")
        print("="*80)
        print("\n  These are HONEST win rates with ZERO LOOKAHEAD BIAS.")
        print("  Every setup shown is 100% reproducible in live trading.")
        print("  Past performance does not guarantee future results.")
        print("  Use this as ONE input in your trading decisions.")
        print("\n" + "="*80 + "\n")

    def close(self):
        self.con.close()


def main():
    # Parse target date from command line
    if len(sys.argv) > 1:
        target_date = date.fromisoformat(sys.argv[1])
    else:
        # Default to today
        target_date = date.today()

    alert_system = DailyAlertSystemV2()
    try:
        alert_system.generate_morning_prep(target_date)
    finally:
        alert_system.close()


if __name__ == "__main__":
    main()
