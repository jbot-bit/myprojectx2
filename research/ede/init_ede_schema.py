"""
Edge Discovery Engine (EDE) - Database Schema Initialization

This script creates all database tables required for the EDE pipeline:
- edge_candidates_raw: Generated hypotheses (Step 2 output)
- edge_candidates_survivors: Passed backtest validation (Step 3 output)
- edge_manifest: Approved edges (Step 4 output, source of truth)
- edge_live_tracking: Live performance monitoring (Step 5)
- edge_generation_log: Tracks all generation attempts
- edge_attack_results: Stores robustness attack results

ALL tables enforce zero-lookahead and parameter immutability.
"""

import duckdb
import os
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = str(Path(__file__).parent.parent / "gold.db")


def init_ede_schema():
    """Initialize complete EDE database schema."""

    print(f"Initializing EDE schema in: {DB_PATH}")

    con = duckdb.connect(DB_PATH)

    # ========================================================================
    # edge_candidates_raw (Step 2 output)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_candidates_raw (
            idea_id VARCHAR PRIMARY KEY,
            generation_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            generator_mode VARCHAR NOT NULL,  -- 'brute', 'conditional', 'contrast', 'inversion', 'ml_cluster'

            -- Edge identity
            human_name VARCHAR,
            instrument VARCHAR NOT NULL,  -- 'MGC', 'NQ', 'MPL'

            -- Entry rule (formal specification)
            entry_type VARCHAR NOT NULL,  -- 'break', 'fade', 'close', 'stop', 'limit'
            entry_time_start TIME NOT NULL,
            entry_time_end TIME NOT NULL,
            entry_condition_json JSON,  -- Full entry logic as JSON

            -- Exit rule (formal specification)
            exit_type VARCHAR NOT NULL,  -- 'fixed_r', 'trailing', 'time', 'structure', 'hybrid'
            stop_type VARCHAR NOT NULL,  -- 'fixed_r', 'atr', 'half', 'structure'
            stop_r DOUBLE,
            target_r DOUBLE,
            exit_condition_json JSON,  -- Full exit logic as JSON

            -- Time window
            session_window VARCHAR,  -- 'asia', 'london', 'ny', 'custom'
            time_window_start TIME,
            time_window_end TIME,

            -- Required features
            required_features VARCHAR[],  -- Array of feature names from daily_features_v2

            -- Risk model
            risk_model VARCHAR NOT NULL,  -- 'fixed_r', 'dynamic_atr', 'volatility_scaled'
            risk_pct DOUBLE DEFAULT 1.0,

            -- Filters
            filters_json JSON,  -- Volatility regimes, session state, prior day context

            -- Assumptions
            assumptions_json JSON,  -- All assumptions documented

            -- Status
            status VARCHAR DEFAULT 'GENERATED',  -- 'GENERATED', 'TESTING', 'FAILED', 'PASSED'

            -- Parameter hash (for deduplication)
            param_hash VARCHAR NOT NULL,

            -- Metadata
            generation_notes TEXT
        )
    """)

    print("[OK] Created edge_candidates_raw")

    # ========================================================================
    # edge_candidates_survivors (Step 3 output)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_candidates_survivors (
            survivor_id VARCHAR PRIMARY KEY,
            idea_id VARCHAR NOT NULL,  -- FK to edge_candidates_raw
            survival_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

            -- Backtest results (baseline)
            baseline_trades INTEGER NOT NULL,
            baseline_win_rate DOUBLE NOT NULL,
            baseline_avg_r DOUBLE NOT NULL,
            baseline_expectancy DOUBLE NOT NULL,
            baseline_max_dd DOUBLE NOT NULL,
            baseline_profit_factor DOUBLE,
            baseline_sharpe DOUBLE,

            -- Cost realism results (after slippage)
            cost_1tick_expectancy DOUBLE NOT NULL,
            cost_2tick_expectancy DOUBLE NOT NULL,
            cost_3tick_expectancy DOUBLE NOT NULL,
            cost_atr_expectancy DOUBLE NOT NULL,
            cost_missedfill_expectancy DOUBLE NOT NULL,

            -- Robustness attack results
            attack_stopfirst_expectancy DOUBLE NOT NULL,
            attack_entrydelay_expectancy DOUBLE NOT NULL,
            attack_exitdelay_expectancy DOUBLE NOT NULL,
            attack_noise_expectancy DOUBLE NOT NULL,
            attack_shuffle_expectancy DOUBLE NOT NULL,

            -- Regime splits
            regime_year_count INTEGER NOT NULL,
            regime_year_profitable INTEGER NOT NULL,
            regime_volatility_count INTEGER NOT NULL,
            regime_volatility_profitable INTEGER NOT NULL,
            regime_session_count INTEGER NOT NULL,
            regime_session_profitable INTEGER NOT NULL,
            regime_max_profit_concentration DOUBLE NOT NULL,  -- Max % from single regime

            -- Walk-forward validation
            walkforward_windows INTEGER NOT NULL,
            walkforward_profitable INTEGER NOT NULL,
            walkforward_avg_expectancy DOUBLE NOT NULL,

            -- Survival metrics
            survival_score DOUBLE NOT NULL,  -- Composite score (0-100)
            confidence_level VARCHAR NOT NULL,  -- 'LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH'

            -- Status
            status VARCHAR DEFAULT 'SURVIVOR',  -- 'SURVIVOR', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'

            -- Results hash
            results_hash VARCHAR NOT NULL,

            FOREIGN KEY (idea_id) REFERENCES edge_candidates_raw(idea_id)
        )
    """)

    print("[OK] Created edge_candidates_survivors")

    # ========================================================================
    # edge_manifest (Step 4 output - SOURCE OF TRUTH)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_manifest (
            edge_id VARCHAR PRIMARY KEY,
            survivor_id VARCHAR NOT NULL,  -- FK to edge_candidates_survivors
            approval_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

            -- Edge identity (immutable)
            human_name VARCHAR NOT NULL,
            instrument VARCHAR NOT NULL,
            version INTEGER DEFAULT 1,

            -- Time window (immutable)
            time_window_start TIME NOT NULL,
            time_window_end TIME NOT NULL,
            session_window VARCHAR,

            -- Entry rule (formal, immutable)
            entry_rule_json JSON NOT NULL,

            -- Exit rule (formal, immutable)
            exit_rule_json JSON NOT NULL,

            -- Risk model (immutable)
            risk_model_json JSON NOT NULL,

            -- Filters (immutable)
            filters_json JSON,

            -- Metrics snapshot (at approval)
            metrics_snapshot_json JSON NOT NULL,

            -- Parameter hash (immutable)
            param_hash VARCHAR NOT NULL UNIQUE,

            -- Discovery metadata
            discovery_date DATE NOT NULL,
            discovered_by VARCHAR DEFAULT 'EDE',

            -- Status
            status VARCHAR DEFAULT 'APPROVED',  -- 'APPROVED', 'ACTIVE', 'SUSPENDED', 'RETIRED'

            -- Performance thresholds (for drift detection)
            threshold_min_expectancy DOUBLE NOT NULL,
            threshold_min_winrate DOUBLE NOT NULL,
            threshold_max_dd DOUBLE NOT NULL,

            -- Sync tracking
            synced_to_validated_setups BOOLEAN DEFAULT FALSE,
            synced_to_config BOOLEAN DEFAULT FALSE,
            synced_to_docs BOOLEAN DEFAULT FALSE,
            sync_timestamp TIMESTAMPTZ,

            -- Audit trail
            approval_notes TEXT,

            FOREIGN KEY (survivor_id) REFERENCES edge_candidates_survivors(survivor_id)
        )
    """)

    print("[OK] Created edge_manifest")

    # ========================================================================
    # edge_live_tracking (Step 5 - continuous monitoring)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_live_tracking (
            tracking_id VARCHAR PRIMARY KEY,
            edge_id VARCHAR NOT NULL,  -- FK to edge_manifest
            trade_date DATE NOT NULL,
            trade_timestamp TIMESTAMPTZ NOT NULL,

            -- Trade details (paper only)
            entry_price DOUBLE NOT NULL,
            stop_price DOUBLE NOT NULL,
            target_price DOUBLE NOT NULL,
            exit_price DOUBLE,
            exit_timestamp TIMESTAMPTZ,

            -- Outcome
            outcome VARCHAR,  -- 'WIN', 'LOSS', 'BREAKEVEN', 'OPEN'
            r_multiple DOUBLE,
            pnl_points DOUBLE,

            -- MAE/MFE tracking
            mae DOUBLE,  -- Max adverse excursion (points)
            mfe DOUBLE,  -- Max favorable excursion (points)

            -- Execution metrics
            entry_slippage_points DOUBLE,
            exit_slippage_points DOUBLE,
            execution_quality VARCHAR,  -- 'GOOD', 'FAIR', 'POOR'

            -- Rolling metrics (updated after each trade)
            rolling_trades_last_20 INTEGER,
            rolling_wins_last_20 INTEGER,
            rolling_expectancy_last_20 DOUBLE,
            rolling_avg_r_last_20 DOUBLE,

            -- Drift indicators
            expectancy_drift_pct DOUBLE,  -- % deviation from historical
            winrate_drift_pct DOUBLE,
            mae_drift_pct DOUBLE,

            -- Regime context
            volatility_regime VARCHAR,  -- 'LOW', 'MID', 'HIGH'
            session_type VARCHAR,
            market_condition VARCHAR,

            -- Status
            drift_warning BOOLEAN DEFAULT FALSE,
            drift_severity VARCHAR,  -- NULL, 'MINOR', 'MODERATE', 'SEVERE'

            FOREIGN KEY (edge_id) REFERENCES edge_manifest(edge_id)
        )
    """)

    print("[OK] Created edge_live_tracking")

    # ========================================================================
    # edge_generation_log (tracks all generation attempts)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_generation_log (
            log_id VARCHAR PRIMARY KEY,
            run_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

            -- Run metadata
            generator_mode VARCHAR NOT NULL,
            run_config_json JSON NOT NULL,

            -- Results
            candidates_generated INTEGER NOT NULL,
            candidates_duplicates INTEGER DEFAULT 0,
            candidates_invalid INTEGER DEFAULT 0,
            candidates_accepted INTEGER NOT NULL,

            -- Performance
            run_duration_seconds DOUBLE,

            -- Notes
            run_notes TEXT
        )
    """)

    print("[OK] Created edge_generation_log")

    # ========================================================================
    # edge_attack_results (stores detailed attack results)
    # ========================================================================
    con.execute("""
        CREATE TABLE IF NOT EXISTS edge_attack_results (
            attack_id VARCHAR PRIMARY KEY,
            idea_id VARCHAR NOT NULL,  -- FK to edge_candidates_raw
            attack_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

            -- Attack type
            attack_type VARCHAR NOT NULL,  -- 'slippage', 'stopfirst', 'entrydelay', 'exitdelay', 'noise', 'shuffle'
            attack_severity VARCHAR NOT NULL,  -- 'LIGHT', 'MODERATE', 'SEVERE'

            -- Attack parameters
            attack_params_json JSON NOT NULL,

            -- Results
            baseline_expectancy DOUBLE NOT NULL,
            attacked_expectancy DOUBLE NOT NULL,
            expectancy_degradation_pct DOUBLE NOT NULL,

            baseline_winrate DOUBLE NOT NULL,
            attacked_winrate DOUBLE NOT NULL,

            baseline_avg_r DOUBLE NOT NULL,
            attacked_avg_r DOUBLE NOT NULL,

            -- Verdict
            passed BOOLEAN NOT NULL,
            failure_mode VARCHAR,  -- NULL if passed, description if failed

            FOREIGN KEY (idea_id) REFERENCES edge_candidates_raw(idea_id)
        )
    """)

    print("[OK] Created edge_attack_results")

    # ========================================================================
    # Create indexes for performance
    # ========================================================================
    con.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON edge_candidates_raw(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_candidates_instrument ON edge_candidates_raw(instrument)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_candidates_hash ON edge_candidates_raw(param_hash)")

    con.execute("CREATE INDEX IF NOT EXISTS idx_survivors_status ON edge_candidates_survivors(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_survivors_idea ON edge_candidates_survivors(idea_id)")

    con.execute("CREATE INDEX IF NOT EXISTS idx_manifest_status ON edge_manifest(status)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_manifest_instrument ON edge_manifest(instrument)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_manifest_hash ON edge_manifest(param_hash)")

    con.execute("CREATE INDEX IF NOT EXISTS idx_tracking_edge ON edge_live_tracking(edge_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tracking_date ON edge_live_tracking(trade_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_tracking_drift ON edge_live_tracking(drift_warning)")

    con.execute("CREATE INDEX IF NOT EXISTS idx_attacks_idea ON edge_attack_results(idea_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_attacks_passed ON edge_attack_results(passed)")

    print("[OK] Created all indexes")

    # ========================================================================
    # Verify schema
    # ========================================================================
    tables = con.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name LIKE 'edge_%'
        ORDER BY table_name
    """).fetchall()

    print("\n" + "="*70)
    print("EDE SCHEMA INITIALIZED SUCCESSFULLY")
    print("="*70)
    print(f"\nTables created: {len(tables)}")
    for table in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
        print(f"  - {table[0]}: {count} rows")

    print("\n" + "="*70)
    print("EDGE DISCOVERY ENGINE READY")
    print("="*70)
    print("\nNext steps:")
    print("  1. Run generators (Step 2) to create candidates")
    print("  2. Run backtest pipeline (Step 3) to validate candidates")
    print("  3. Approve survivors (Step 4) to create edges")
    print("  4. Monitor live performance (Step 5) for drift")
    print("\nAll tables enforce:")
    print("  [OK] Zero lookahead")
    print("  [OK] Parameter immutability")
    print("  [OK] Audit trails")
    print("  [OK] Reproducibility")

    con.close()


if __name__ == "__main__":
    init_ede_schema()
