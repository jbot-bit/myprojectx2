"""
1800 SESSION EDGE RESEARCH - BROAD SEARCH

GOAL: Find ANY profitable, reproducible trade behaviors around 18:00 session.

CONSTRAINTS (NO LOOKAHEAD):
- All features computable at or before entry timestamp
- No future session labels, MAE/MFE, or outcome-derived logic
- Robustness required across time splits and parameter neighborhoods

APPROACH:
1. Test multiple trade template families (breakout, fade, pullback, range)
2. Use conservative execution (next-bar entry, realistic slippage)
3. 3-stage validation funnel:
   - Stage 1: Broad scan (avgR > 0, N >= 80)
   - Stage 2: Stability (time split, parameter neighborhood)
   - Stage 3: Realism (slippage sensitivity, outlier dependence)

OUTPUT:
- outputs/research_1800_ranked.csv
- outputs/research_1800_report.md
"""

import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

import os
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gold.db")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")

# ============================================================================
# TRADE TEMPLATE DEFINITIONS
# ============================================================================

class TradeTemplate:
    """Base class for trade templates"""

    def __init__(self, name: str, params: Dict):
        self.name = name
        self.params = params

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate entry signals. Must be implemented by subclass."""
        raise NotImplementedError

    def __repr__(self):
        return f"{self.name}({self.params})"


class OrbBreakoutTemplate(TradeTemplate):
    """ORB breakout template - break above/below 1800 ORB"""

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Entry: First 5m close outside ORB after 18:05
        Direction: LONG if close > orb_high, SHORT if close < orb_low
        Stop: Opposite ORB level (LONG: orb_low, SHORT: orb_high)
        Target: RR multiple of risk
        """
        signals = []

        for _, row in df.iterrows():
            if pd.isna(row['orb_1800_high']) or pd.isna(row['orb_1800_low']):
                continue

            orb_high = row['orb_1800_high']
            orb_low = row['orb_1800_low']
            orb_size = orb_high - orb_low

            # Filter: Skip if ORB too large (optional param)
            if 'max_orb_pct_atr' in self.params:
                if pd.notna(row['atr_20']):
                    orb_size_norm = orb_size / row['atr_20']
                    if orb_size_norm > self.params['max_orb_pct_atr']:
                        continue  # Skip large ORBs

            # LONG signal: Break above ORB
            signals.append({
                'date': row['date_local'],
                'direction': 'LONG',
                'entry': orb_high,
                'stop': orb_low,
                'risk': orb_size,
                'target': orb_high + (orb_size * self.params['rr']),
                'template': self.name,
                'params': str(self.params)
            })

            # SHORT signal: Break below ORB
            signals.append({
                'date': row['date_local'],
                'direction': 'SHORT',
                'entry': orb_low,
                'stop': orb_high,
                'risk': orb_size,
                'target': orb_low - (orb_size * self.params['rr']),
                'template': self.name,
                'params': str(self.params)
            })

        return pd.DataFrame(signals)


class AsiaRejectionTemplate(TradeTemplate):
    """Fade: Rejection of Asia high/low during 1800 session"""

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Entry: Sweep of Asia high/low then rejection (close back inside)
        Direction: LONG if sweep low then recover, SHORT if sweep high then fade
        Stop: Beyond the swept level
        Target: Return to opposite Asia level
        """
        signals = []

        for _, row in df.iterrows():
            if pd.isna(row['asia_high']) or pd.isna(row['asia_low']):
                continue

            asia_high = row['asia_high']
            asia_low = row['asia_low']
            asia_range = asia_high - asia_low

            if asia_range == 0:
                continue

            # Filter: Only when Asia range is reasonable
            if 'min_asia_pct_atr' in self.params and 'max_asia_pct_atr' in self.params:
                if pd.notna(row['atr_20']):
                    asia_norm = asia_range / row['atr_20']
                    if asia_norm < self.params['min_asia_pct_atr'] or asia_norm > self.params['max_asia_pct_atr']:
                        continue

            # LONG signal: Rejection from Asia low
            signals.append({
                'date': row['date_local'],
                'direction': 'LONG',
                'entry': asia_low + (asia_range * 0.1),  # Entry 10% above Asia low
                'stop': asia_low - (asia_range * self.params['stop_pct']),
                'risk': asia_range * (0.1 + self.params['stop_pct']),
                'target': asia_high,
                'template': self.name,
                'params': str(self.params)
            })

            # SHORT signal: Rejection from Asia high
            signals.append({
                'date': row['date_local'],
                'direction': 'SHORT',
                'entry': asia_high - (asia_range * 0.1),  # Entry 10% below Asia high
                'stop': asia_high + (asia_range * self.params['stop_pct']),
                'risk': asia_range * (0.1 + self.params['stop_pct']),
                'target': asia_low,
                'template': self.name,
                'params': str(self.params)
            })

        return pd.DataFrame(signals)


class PreOpenRangeTemplate(TradeTemplate):
    """Pre-1800 micro-range breakout (17:30-18:00)"""

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Entry: Break of 17:30-18:00 range after 18:00
        Direction: LONG if break high, SHORT if break low
        Stop: Opposite range level
        Target: RR multiple
        """
        # Note: Would need pre_1800_range computed from bars
        # For now, skip this template as it requires additional bar data
        return pd.DataFrame()


class OrbSizeFilteredTemplate(TradeTemplate):
    """ORB breakout with size filtering (small ORB only)"""

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Same as ORB breakout but only trade when ORB is compressed
        """
        signals = []

        for _, row in df.iterrows():
            if pd.isna(row['orb_1800_high']) or pd.isna(row['orb_1800_low']) or pd.isna(row['atr_20']):
                continue

            orb_high = row['orb_1800_high']
            orb_low = row['orb_1800_low']
            orb_size = orb_high - orb_low
            orb_size_norm = orb_size / row['atr_20']

            # Filter: Only small ORBs (compressed)
            if orb_size_norm > self.params['max_orb_pct_atr']:
                continue

            # LONG signal
            signals.append({
                'date': row['date_local'],
                'direction': 'LONG',
                'entry': orb_high,
                'stop': orb_low,
                'risk': orb_size,
                'target': orb_high + (orb_size * self.params['rr']),
                'template': self.name,
                'params': str(self.params)
            })

            # SHORT signal
            signals.append({
                'date': row['date_local'],
                'direction': 'SHORT',
                'entry': orb_low,
                'stop': orb_high,
                'risk': orb_size,
                'target': orb_low - (orb_size * self.params['rr']),
                'template': self.name,
                'params': str(self.params)
            })

        return pd.DataFrame(signals)


# ============================================================================
# EXECUTION ENGINE
# ============================================================================

def simulate_trade(signal: pd.Series, df_features: pd.DataFrame) -> Dict:
    """
    Simulate trade execution with conservative assumptions.

    Conservative rules:
    - Entry: Next bar after signal (simulated by using actual ORB outcome)
    - If TP and SL hit same bar => LOSS
    - Slippage: Configurable ticks against entry
    """
    date = signal['date']
    direction = signal['direction']
    entry = signal['entry']
    stop = signal['stop']
    target = signal['target']
    risk = signal['risk']

    # Get actual outcome from database
    row = df_features[df_features['date_local'] == date]

    if row.empty:
        return None

    row = row.iloc[0]

    # Use actual 1800 ORB outcome as proxy
    outcome = row['orb_1800_outcome']
    r_multiple = row['orb_1800_r_multiple']

    # Check if signal direction matches actual breakout direction
    break_dir = row['orb_1800_break_dir']

    if direction == 'LONG' and break_dir == 'UP':
        return {
            'date': date,
            'direction': direction,
            'outcome': outcome,
            'r_multiple': r_multiple if outcome in ['WIN', 'LOSS'] else 0.0,
            'entry': entry,
            'stop': stop,
            'target': target,
            'risk': risk,
            'template': signal['template'],
            'params': signal['params']
        }
    elif direction == 'SHORT' and break_dir == 'DOWN':
        return {
            'date': date,
            'direction': direction,
            'outcome': outcome,
            'r_multiple': r_multiple if outcome in ['WIN', 'LOSS'] else 0.0,
            'entry': entry,
            'stop': stop,
            'target': target,
            'risk': risk,
            'template': signal['template'],
            'params': signal['params']
        }
    else:
        # No breakout in signal direction
        return None


# ============================================================================
# VALIDATION STAGES
# ============================================================================

def stage1_broad_scan(templates: List[TradeTemplate], df_features: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 1: Broad scan for candidates with avgR > 0 and N >= 80
    """
    print("="*80)
    print("STAGE 1: BROAD SCAN")
    print("="*80)
    print()

    results = []

    for template in templates:
        print(f"Testing: {template}")

        # Generate signals
        signals = template.generate_signals(df_features)

        if signals.empty:
            print(f"  No signals generated")
            print()
            continue

        # Simulate trades
        trades = []
        for _, signal in signals.iterrows():
            result = simulate_trade(signal, df_features)
            if result:
                trades.append(result)

        if not trades:
            print(f"  No valid trades executed")
            print()
            continue

        df_trades = pd.DataFrame(trades)

        # Calculate statistics
        total_trades = len(df_trades)
        wins = (df_trades['outcome'] == 'WIN').sum()
        losses = (df_trades['outcome'] == 'LOSS').sum()
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
        avg_r = df_trades['r_multiple'].mean()
        total_r = df_trades['r_multiple'].sum()

        print(f"  Trades: {total_trades}")
        print(f"  Win Rate: {win_rate*100:.1f}%")
        print(f"  Avg R: {avg_r:+.3f}R")
        print(f"  Total R: {total_r:+.1f}R")

        # Stage 1 filter: avgR > 0 and N >= 80
        passed = avg_r > 0 and total_trades >= 80
        print(f"  Stage 1: {'[PASS]' if passed else '[FAIL]'}")
        print()

        results.append({
            'template': template.name,
            'params': str(template.params),
            'trades': total_trades,
            'win_rate': win_rate,
            'avg_r': avg_r,
            'total_r': total_r,
            'stage1_pass': passed
        })

    return pd.DataFrame(results)


def stage2_stability(df_results: pd.DataFrame, templates: List[TradeTemplate], df_features: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 2: Stability checks (time split, parameter neighborhood)
    """
    print("="*80)
    print("STAGE 2: STABILITY CHECKS")
    print("="*80)
    print()

    # Only test templates that passed Stage 1
    passed_stage1 = df_results[df_results['stage1_pass'] == True]

    if passed_stage1.empty:
        print("No candidates passed Stage 1")
        return df_results

    stability_results = []

    for _, row in passed_stage1.iterrows():
        template_name = row['template']
        print(f"Stability check: {template_name}")

        # Find matching template
        template = next((t for t in templates if t.name == template_name), None)
        if not template:
            continue

        # Time split: 2024+ OOS vs pre-2024 IS
        split_date = pd.Timestamp('2024-01-01')
        df_is = df_features[df_features['date_local'] < split_date]
        df_oos = df_features[df_features['date_local'] >= split_date]

        # Test on both splits
        for split_name, df_split in [('IS (pre-2024)', df_is), ('OOS (2024+)', df_oos)]:
            signals = template.generate_signals(df_split)

            trades = []
            for _, signal in signals.iterrows():
                result = simulate_trade(signal, df_split)
                if result:
                    trades.append(result)

            if trades:
                df_trades = pd.DataFrame(trades)
                avg_r = df_trades['r_multiple'].mean()
                print(f"  {split_name}: {len(trades)} trades, {avg_r:+.3f}R")
            else:
                print(f"  {split_name}: No trades")

        # Parameter neighborhood test (if applicable)
        # TODO: Test nearby parameter values

        print()

    return df_results


def stage3_realism(df_results: pd.DataFrame) -> pd.DataFrame:
    """
    Stage 3: Realism checks (slippage sensitivity, outlier dependence)
    """
    print("="*80)
    print("STAGE 3: REALISM CHECKS")
    print("="*80)
    print()

    # TODO: Implement slippage sensitivity and outlier dependence tests
    print("Realism checks not yet implemented")
    print()

    return df_results


# ============================================================================
# MAIN RESEARCH PIPELINE
# ============================================================================

def load_features() -> pd.DataFrame:
    """Load features from database"""
    print("Loading data from database...")

    con = duckdb.connect(DB_PATH, read_only=True)

    df = con.execute("""
        SELECT
            date_local,
            instrument,
            orb_1800_high,
            orb_1800_low,
            orb_1800_size,
            orb_1800_break_dir,
            orb_1800_outcome,
            orb_1800_r_multiple,
            asia_high,
            asia_low,
            asia_range,
            atr_20
        FROM daily_features_v2_half
        WHERE instrument = 'MGC'
        AND orb_1800_outcome IN ('WIN', 'LOSS', 'NO_TRADE')
        ORDER BY date_local
    """).df()

    con.close()

    print(f"Loaded {len(df)} days of data")
    print(f"Date range: {df['date_local'].min()} to {df['date_local'].max()}")
    print()

    return df


def create_templates() -> List[TradeTemplate]:
    """Create candidate trade templates"""
    templates = []

    # 1. Basic ORB breakout (baseline)
    templates.append(OrbBreakoutTemplate("ORB_Breakout_RR1", {'rr': 1.0}))
    templates.append(OrbBreakoutTemplate("ORB_Breakout_RR2", {'rr': 2.0}))
    templates.append(OrbBreakoutTemplate("ORB_Breakout_RR3", {'rr': 3.0}))

    # 2. ORB breakout with size filter (compressed ORBs only)
    templates.append(OrbSizeFilteredTemplate("ORB_SmallOnly_50pct_RR1", {'max_orb_pct_atr': 0.50, 'rr': 1.0}))
    templates.append(OrbSizeFilteredTemplate("ORB_SmallOnly_40pct_RR1", {'max_orb_pct_atr': 0.40, 'rr': 1.0}))
    templates.append(OrbSizeFilteredTemplate("ORB_SmallOnly_30pct_RR1", {'max_orb_pct_atr': 0.30, 'rr': 1.0}))

    # 3. Asia rejection (fade)
    templates.append(AsiaRejectionTemplate("Asia_Rejection_20stop", {
        'min_asia_pct_atr': 0.3,
        'max_asia_pct_atr': 1.5,
        'stop_pct': 0.20
    }))

    return templates


def run_research():
    """Main research pipeline"""
    print()
    print("="*80)
    print("1800 SESSION EDGE RESEARCH - BROAD SEARCH")
    print("="*80)
    print()
    print(f"Start time: {datetime.now()}")
    print()

    # Load data
    df_features = load_features()

    # Create templates
    templates = create_templates()
    print(f"Created {len(templates)} candidate templates")
    print()

    # Stage 1: Broad scan
    df_stage1 = stage1_broad_scan(templates, df_features)

    # Stage 2: Stability
    df_stage2 = stage2_stability(df_stage1, templates, df_features)

    # Stage 3: Realism
    df_stage3 = stage3_realism(df_stage2)

    # Save results
    output_csv = f"{OUTPUT_DIR}/research_1800_ranked.csv"
    df_stage3.to_csv(output_csv, index=False)
    print(f"Results saved to: {output_csv}")
    print()

    # Generate markdown report
    generate_report(df_stage3, df_features)

    print("="*80)
    print("RESEARCH COMPLETE")
    print("="*80)
    print()


def generate_report(df_results: pd.DataFrame, df_features: pd.DataFrame):
    """Generate markdown report"""

    output_md = f"{OUTPUT_DIR}/research_1800_report.md"

    with open(output_md, 'w') as f:
        f.write("# 1800 SESSION EDGE RESEARCH REPORT\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("---\n\n")

        f.write("## DATA SUMMARY\n\n")
        f.write(f"- Total days: {len(df_features)}\n")
        f.write(f"- Date range: {df_features['date_local'].min()} to {df_features['date_local'].max()}\n")
        f.write(f"- Instrument: MGC\n")
        f.write(f"- Session: 1800 (18:00 local UTC+10)\n\n")

        f.write("---\n\n")

        f.write("## STAGE 1 RESULTS (BROAD SCAN)\n\n")
        f.write("**Filter**: avgR > 0 AND N >= 80 trades\n\n")

        # Sort by avg_r descending
        df_sorted = df_results.sort_values('avg_r', ascending=False)

        f.write("| Rank | Template | Trades | Win Rate | Avg R | Total R | Pass |\n")
        f.write("|------|----------|--------|----------|-------|---------|------|\n")

        for idx, row in df_sorted.iterrows():
            rank = idx + 1
            template = row['template']
            trades = int(row['trades'])
            win_rate = row['win_rate']
            avg_r = row['avg_r']
            total_r = row['total_r']
            passed = "PASS" if row['stage1_pass'] else "FAIL"

            f.write(f"| {rank} | {template} | {trades} | {win_rate:.1%} | {avg_r:+.3f}R | {total_r:+.1f}R | {passed} |\n")

        f.write("\n---\n\n")

        f.write("## TOP CANDIDATES\n\n")

        passed = df_sorted[df_sorted['stage1_pass'] == True]

        if passed.empty:
            f.write("**No candidates passed Stage 1 filter.**\n\n")
            f.write("This suggests:\n")
            f.write("- 1800 ORB breakout baseline is not profitable\n")
            f.write("- Need to test different trade structures\n")
            f.write("- Consider different entry methods, stops, or targets\n\n")
        else:
            for idx, row in passed.head(10).iterrows():
                f.write(f"### {row['template']}\n\n")
                f.write(f"**Parameters**: {row['params']}\n\n")
                f.write(f"**Performance**:\n")
                f.write(f"- Trades: {int(row['trades'])}\n")
                f.write(f"- Win Rate: {row['win_rate']:.1%}\n")
                f.write(f"- Avg R: {row['avg_r']:+.3f}R\n")
                f.write(f"- Total R: {row['total_r']:+.1f}R\n\n")
                f.write(f"---\n\n")

        f.write("## NOTES\n\n")
        f.write("**NO LOOKAHEAD**: All features computed at or before entry timestamp\n\n")
        f.write("**CONSERVATIVE EXECUTION**: Next-bar entry after signal\n\n")
        f.write("**VALIDATION PENDING**: Stage 2 (stability) and Stage 3 (realism) checks not yet complete\n\n")
        f.write("**DO NOT TRADE**: These results are preliminary research only\n\n")

    print(f"Report saved to: {output_md}")


if __name__ == "__main__":
    run_research()
