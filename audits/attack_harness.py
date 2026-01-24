"""
Attack Test Harness (Core)
Framework for adversarial testing of trading strategies
Based on: STEPHARNESS.txt
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Any
import pandas as pd
import numpy as np
from datetime import datetime


@dataclass
class AttackResult:
    """Result of a single attack test"""
    name: str
    avg_r: float
    winrate: float
    trades: int
    verdict: str = "UNKNOWN"

    def __post_init__(self):
        """Determine verdict based on results"""
        if self.avg_r <= 0:
            self.verdict = "FAIL - Negative expectancy"
        elif self.avg_r < 0.1:
            self.verdict = "BORDERLINE"
        elif self.winrate < 45:
            self.verdict = "BORDERLINE - Low WR"
        else:
            self.verdict = "PASS"


def run_attack(
    name: str,
    backtest_fn: Callable,
    mutate_fn: Callable,
    data: pd.DataFrame,
    **kwargs
) -> AttackResult:
    """
    Run a single attack test

    Args:
        name: Attack name
        backtest_fn: Function that takes data and returns trades DataFrame
        mutate_fn: Function that mutates data to simulate attack
        data: Clean data
        **kwargs: Additional arguments passed to mutate_fn

    Returns:
        AttackResult with metrics
    """
    # Apply attack to data
    attacked_data = mutate_fn(data.copy(), **kwargs)

    # Run backtest on attacked data
    try:
        trades = backtest_fn(attacked_data)

        if trades is None or len(trades) == 0:
            return AttackResult(
                name=name,
                avg_r=0.0,
                winrate=0.0,
                trades=0,
                verdict="FAIL - No trades"
            )

        # Calculate metrics
        avg_r = trades["r_multiple"].mean()
        winrate = (trades["outcome"] == "WIN").mean() * 100
        trade_count = len(trades)

        return AttackResult(
            name=name,
            avg_r=avg_r,
            winrate=winrate,
            trades=trade_count
        )

    except Exception as e:
        return AttackResult(
            name=name,
            avg_r=0.0,
            winrate=0.0,
            trades=0,
            verdict=f"ERROR - {str(e)}"
        )


# ============================================================================
# ATTACK 1: SLIPPAGE SHOCK
# ============================================================================

def slippage_attack(df: pd.DataFrame, ticks: int = 2, tick_size: float = 0.1) -> pd.DataFrame:
    """
    Inject slippage into entry/stop/target prices

    Args:
        df: Trade data with entry_price, stop_price, target_price columns
        ticks: Number of ticks slippage
        tick_size: Size of one tick

    Returns:
        Modified DataFrame with slippage applied
    """
    slip = ticks * tick_size

    # Random direction slippage on entry
    df["entry_price"] = df["entry_price"] + np.random.choice(
        [-slip, slip],
        size=len(df)
    )

    # Adverse slippage on stop (worse exit)
    df["stop_price"] = df["stop_price"] + slip

    # Adverse slippage on target (worse exit)
    df["target_price"] = df["target_price"] - slip

    return df


# ============================================================================
# ATTACK 2: STOP-FIRST AMBIGUITY
# ============================================================================

def stop_first_attack(df: pd.DataFrame) -> pd.DataFrame:
    """
    Force stop-first resolution when both stop and target are hit

    Args:
        df: Trade data with hit_stop_and_target flag

    Returns:
        Modified DataFrame with forced stop outcomes
    """
    if "hit_stop_and_target" in df.columns:
        mask = df["hit_stop_and_target"] == True
        df.loc[mask, "outcome"] = "LOSS"
        df.loc[mask, "r_multiple"] = -1.0

    return df


# ============================================================================
# ATTACK 3: LATENCY / DELAYED ENTRY
# ============================================================================

def latency_attack(df: pd.DataFrame, delay_candles: int = 1) -> pd.DataFrame:
    """
    Simulate delayed entry due to latency

    Args:
        df: Trade data with entry_index and price_at_entry_index
        delay_candles: Number of candles to delay

    Returns:
        Modified DataFrame with delayed entries
    """
    if "entry_index" in df.columns and "price_at_entry_index" in df.columns:
        df["entry_index"] = df["entry_index"] + delay_candles
        df["entry_price"] = df["price_at_entry_index"]  # Use actual price at new index

    return df


# ============================================================================
# ATTACK 4: TRADE SKIP (OUTAGES / HUMAN ERROR)
# ============================================================================

def skip_attack(df: pd.DataFrame, skip_pct: float = 0.2) -> pd.DataFrame:
    """
    Randomly skip percentage of trades

    Args:
        df: Trade data
        skip_pct: Percentage of trades to skip (0.0 to 1.0)

    Returns:
        Modified DataFrame with trades skipped
    """
    mask = np.random.rand(len(df)) > skip_pct
    return df[mask].copy()


# ============================================================================
# ATTACK 5: SPREAD WIDENING / REJECTED FILLS
# ============================================================================

def spread_attack(df: pd.DataFrame, max_spread_ticks: int = 4, tick_size: float = 0.1, rejection_rate: float = 0.15) -> pd.DataFrame:
    """
    Simulate spread widening and rejected fills

    Args:
        df: Trade data
        max_spread_ticks: Maximum spread in ticks
        tick_size: Size of one tick
        rejection_rate: Percentage of fills to reject

    Returns:
        Modified DataFrame with spread costs and rejected fills
    """
    spread = max_spread_ticks * tick_size

    # Random rejection
    reject_mask = np.random.rand(len(df)) < rejection_rate
    df = df[~reject_mask].copy()

    # Spread cost on entry
    df["entry_price"] = df["entry_price"] + spread

    return df


# ============================================================================
# ATTACK 6: PARTIAL DATA LOSS
# ============================================================================

def missing_bar_attack(df: pd.DataFrame, loss_pct: float = 0.05) -> pd.DataFrame:
    """
    Simulate partial data loss (missing bars)

    Args:
        df: Trade data
        loss_pct: Percentage of bars to drop

    Returns:
        Modified DataFrame with missing bars
    """
    # Drop random bars
    drop_idx = np.random.choice(df.index, size=int(loss_pct * len(df)), replace=False)
    df = df.drop(drop_idx)

    # Force skip trades with incomplete ORB
    if "orb_complete" in df.columns:
        df = df[df["orb_complete"] == True]

    return df


# ============================================================================
# ATTACK RUNNER
# ============================================================================

def run_all_attacks(
    backtest_fn: Callable,
    data: pd.DataFrame,
    baseline_result: AttackResult = None
) -> pd.DataFrame:
    """
    Run all attacks and return results table

    Args:
        backtest_fn: Backtest function that takes data and returns trades
        data: Clean data
        baseline_result: Optional baseline result for comparison

    Returns:
        DataFrame with attack results
    """
    attacks = [
        ("Slip 1 tick", slippage_attack, {"ticks": 1}),
        ("Slip 3 ticks", slippage_attack, {"ticks": 3}),
        ("Slip 5 ticks", slippage_attack, {"ticks": 5}),
        ("Stop-first bias", stop_first_attack, {}),
        ("Latency +1 candle", latency_attack, {"delay_candles": 1}),
        ("Latency +2 candles", latency_attack, {"delay_candles": 2}),
        ("Skip 10%", skip_attack, {"skip_pct": 0.1}),
        ("Skip 20%", skip_attack, {"skip_pct": 0.2}),
        ("Skip 30%", skip_attack, {"skip_pct": 0.3}),
        ("Spread widening", spread_attack, {}),
        ("Missing bars 5%", missing_bar_attack, {"loss_pct": 0.05}),
    ]

    results = []

    # Add baseline if provided
    if baseline_result:
        results.append(baseline_result.__dict__)

    # Run each attack
    for name, fn, kwargs in attacks:
        print(f"Running attack: {name}...")
        res = run_attack(name, backtest_fn, fn, data, **kwargs)
        results.append(res.__dict__)

    return pd.DataFrame(results)


# ============================================================================
# STOP CONDITIONS (HARD FAIL)
# ============================================================================

def check_stop_conditions(attack_results: pd.DataFrame) -> Dict[str, Any]:
    """
    Check if any stop conditions are violated

    Args:
        attack_results: DataFrame from run_all_attacks

    Returns:
        Dictionary with stop condition check results
    """
    failures = []

    # Check for negative expectancy flip
    negative_attacks = attack_results[attack_results["avg_r"] < 0]
    if len(negative_attacks) > 0:
        failures.append({
            "condition": "Negative Expectancy Flip",
            "attacks": negative_attacks["name"].tolist(),
            "severity": "CRITICAL"
        })

    # Check for exploding losses
    if "avg_r" in attack_results.columns:
        min_r = attack_results["avg_r"].min()
        if min_r < -2.0:
            failures.append({
                "condition": "Exploding Loss Per Trade",
                "min_r": min_r,
                "severity": "CRITICAL"
            })

    # Check for optimistic fill dependency
    baseline_r = attack_results[attack_results["name"] == "Baseline"]["avg_r"].iloc[0] if "Baseline" in attack_results["name"].values else None
    if baseline_r:
        for _, row in attack_results.iterrows():
            if row["name"] != "Baseline":
                degradation = (baseline_r - row["avg_r"]) / baseline_r if baseline_r != 0 else 0
                if degradation > 0.8:  # 80% degradation
                    failures.append({
                        "condition": "Optimistic Fill Dependency",
                        "attack": row["name"],
                        "degradation_pct": degradation * 100,
                        "severity": "WARNING"
                    })

    return {
        "deployable": len([f for f in failures if f["severity"] == "CRITICAL"]) == 0,
        "failures": failures,
        "warnings": len([f for f in failures if f["severity"] == "WARNING"]),
        "critical_failures": len([f for f in failures if f["severity"] == "CRITICAL"])
    }


if __name__ == "__main__":
    print("Attack Harness Framework - Ready")
    print("Use run_all_attacks() to execute full attack suite")
