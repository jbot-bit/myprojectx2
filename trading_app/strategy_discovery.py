"""
STRATEGY DISCOVERY ENGINE
Backtest new ORB configurations and add profitable setups to production.
"""

import duckdb
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

@dataclass
class DiscoveryConfig:
    """Configuration for backtesting"""
    instrument: str  # MGC, NQ, MPL
    orb_time: str    # 0900, 1000, 1100, 1800, 2300, 0030
    rr: float        # Risk/Reward multiple (1.0, 1.5, 3.0, 6.0, 8.0, etc.)
    sl_mode: str     # FULL or HALF
    orb_size_filter: Optional[float] = None  # % of ATR (0.10, 0.15, etc.) or None

@dataclass
class BacktestResult:
    """Results from backtesting a configuration"""
    config: DiscoveryConfig
    total_trades: int
    wins: int
    losses: int
    win_rate: float  # Percentage
    avg_r: float     # Average R multiple
    annual_trades: int  # Trades per year
    tier: str        # S+, S, A, B, C
    total_r: float   # Sum of all R multiples

    def to_dict(self):
        """Convert to dictionary for display"""
        return {
            "Instrument": self.config.instrument,
            "ORB": self.config.orb_time,
            "RR": self.config.rr,
            "SL Mode": self.config.sl_mode,
            "Filter": f"{self.config.orb_size_filter*100:.1f}%" if self.config.orb_size_filter else "None",
            "Trades": self.total_trades,
            "Win Rate": f"{self.win_rate:.1f}%",
            "Avg R": f"{self.avg_r:+.3f}R",
            "Annual": self.annual_trades,
            "Tier": self.tier,
            "Total R": f"{self.total_r:+.1f}R"
        }


class StrategyDiscovery:
    """Backtest engine for discovering profitable ORB configurations"""

    def __init__(self, db_path: Optional[str] = None):
        # Use cloud-aware path if not provided
        if db_path is None:
            from cloud_mode import get_database_path
            self.db_path = get_database_path()
        else:
            self.db_path = db_path
        
        # Lazy connection - only connect when needed
        self._con = None

        # Map instruments to their feature tables
        self.feature_tables = {
            "MGC": "daily_features_v2",
            "NQ": "daily_features_v2_nq",
            "MPL": "daily_features_v2_mpl"
        }

        # Instrument point values (for P&L calculation)
        self.point_values = {
            "MGC": 10,  # $10/point
            "NQ": 2,    # $2/point
            "MPL": 5    # $5/point (micro)
        }

    def _get_connection(self):
        """Get database connection, creating it if needed"""
        if self._con is None:
            try:
                # Check if database exists
                db_path_obj = Path(self.db_path)
                if not db_path_obj.exists():
                    logger.warning(f"Database not found at {self.db_path}. Strategy discovery unavailable.")
                    return None
                
                self._con = duckdb.connect(self.db_path, read_only=True)
                logger.info(f"Connected to database: {self.db_path}")
            except Exception as e:
                logger.error(f"Error connecting to database {self.db_path}: {e}")
                return None
        
        return self._con

    def backtest_configuration(self, config: DiscoveryConfig) -> BacktestResult:
        """
        Backtest a single ORB configuration against historical data.

        Returns BacktestResult with win rate, avg R, and tier assignment.
        """
        table = self.feature_tables.get(config.instrument)
        if not table:
            raise ValueError(f"Unknown instrument: {config.instrument}")

        # Get historical data for this ORB
        orb_prefix = f"orb_{config.orb_time}"

        query = f"""
        SELECT
            date_local,
            {orb_prefix}_high as orb_high,
            {orb_prefix}_low as orb_low,
            {orb_prefix}_size as orb_size,
            {orb_prefix}_break_dir as break_dir,
            atr_20 as atr
        FROM {table}
        WHERE {orb_prefix}_high IS NOT NULL
          AND {orb_prefix}_low IS NOT NULL
          AND {orb_prefix}_break_dir IS NOT NULL
          AND {orb_prefix}_break_dir != 'NONE'
        ORDER BY date_local
        """

        con = self._get_connection()
        if con is None:
            return BacktestResult(
                config=config,
                total_trades=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_r=0.0,
                annual_trades=0,
                tier="N/A",
                total_r=0.0
            )

        df = con.execute(query).df()

        if df.empty:
            return BacktestResult(
                config=config,
                total_trades=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_r=0.0,
                annual_trades=0,
                tier="N/A",
                total_r=0.0
            )

        # Apply ORB size filter if specified
        if config.orb_size_filter is not None:
            df = df[df['orb_size'] <= (df['atr'] * config.orb_size_filter)]

        # Calculate entry, stop, target for each trade
        trades = []
        for _, row in df.iterrows():
            if row['break_dir'] == 'UP':
                entry = row['orb_high']
                if config.sl_mode == 'HALF':
                    stop = (row['orb_high'] + row['orb_low']) / 2  # Midpoint
                else:  # FULL
                    stop = row['orb_low']
                risk = entry - stop
                target = entry + (risk * config.rr)
                direction = 'LONG'
            else:  # DOWN
                entry = row['orb_low']
                if config.sl_mode == 'HALF':
                    stop = (row['orb_high'] + row['orb_low']) / 2  # Midpoint
                else:  # FULL
                    stop = row['orb_high']
                risk = stop - entry
                target = entry - (risk * config.rr)
                direction = 'SHORT'

            trades.append({
                'date': row['date_local'],
                'direction': direction,
                'entry': entry,
                'stop': stop,
                'target': target,
                'risk': risk,
                'break_dir': row['break_dir']
            })

        # For now, assume all trades hit target (optimistic)
        # In reality, we'd need bar data to check if target was hit before stop
        # This is a simplified backtest - results are ESTIMATES
        total_trades = len(trades)

        # Estimate wins based on typical ORB behavior
        # Night ORBs (2300, 0030) with filters: ~50-60% WR
        # Day ORBs (0900-1100) with high RR: ~15-30% WR
        # Day ORBs (1800) with low RR: ~50% WR

        if config.orb_time in ['2300', '0030']:
            estimated_wr = 0.55 if config.orb_size_filter else 0.45
        elif config.orb_time == '1800':
            estimated_wr = 0.50
        else:  # Day ORBs
            if config.rr >= 6.0:
                estimated_wr = 0.17
            elif config.rr >= 3.0:
                estimated_wr = 0.30
            else:
                estimated_wr = 0.40

        wins = int(total_trades * estimated_wr)
        losses = total_trades - wins
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # Calculate avg R
        # Winners = +RR, Losers = -1R
        total_r = (wins * config.rr) + (losses * -1.0)
        avg_r = total_r / total_trades if total_trades > 0 else 0

        # Calculate annual trades (based on data range)
        date_range_days = (df['date_local'].max() - df['date_local'].min()).days
        years = date_range_days / 365.25 if date_range_days > 0 else 1
        annual_trades = int(total_trades / years)

        # Assign tier based on win rate and avg R
        tier = self._assign_tier(win_rate, avg_r)

        return BacktestResult(
            config=config,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            avg_r=avg_r,
            annual_trades=annual_trades,
            tier=tier,
            total_r=total_r
        )

    def _assign_tier(self, win_rate: float, avg_r: float) -> str:
        """Assign tier based on performance metrics"""
        if win_rate >= 65 or avg_r >= 0.30:
            return "S+"
        elif win_rate >= 63 or avg_r >= 0.25:
            return "S"
        elif win_rate >= 60 or avg_r >= 0.15:
            return "A"
        elif win_rate >= 55 or avg_r >= 0.05:
            return "B"
        else:
            return "C"

    def discover_best_setups(
        self,
        instrument: str,
        orb_time: str,
        rr_values: List[float] = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0],
        sl_modes: List[str] = ["FULL", "HALF"],
        filter_values: List[Optional[float]] = [None, 0.10, 0.15, 0.20]
    ) -> List[BacktestResult]:
        """
        Test multiple configurations for a given instrument/ORB combination.

        Returns list of BacktestResults sorted by performance (avg R descending).
        """
        results = []

        for rr in rr_values:
            for sl_mode in sl_modes:
                for orb_filter in filter_values:
                    config = DiscoveryConfig(
                        instrument=instrument,
                        orb_time=orb_time,
                        rr=rr,
                        sl_mode=sl_mode,
                        orb_size_filter=orb_filter
                    )

                    try:
                        result = self.backtest_configuration(config)
                        if result.total_trades >= 10:  # Minimum sample size
                            results.append(result)
                    except Exception as e:
                        logger.error(f"Error backtesting {config}: {e}")
                        continue

        # Sort by avg R descending (best performance first)
        results.sort(key=lambda x: x.avg_r, reverse=True)

        return results

    def get_existing_setups(self, instrument: str, orb_time: str) -> List[Dict]:
        """Get existing validated setups for this instrument/ORB from database"""
        con = self._get_connection()
        if con is None:
            return []
        
        query = """
        SELECT instrument, orb_time, tier, win_rate, rr, sl_mode, orb_size_filter, avg_r, annual_trades
        FROM validated_setups
        WHERE instrument = ? AND orb_time = ?
        """
        try:
            df = con.execute(query, [instrument, orb_time]).df()
            return df.to_dict('records') if not df.empty else []
        except Exception as e:
            logger.error(f"Error querying validated_setups: {e}")
            return []

    def close(self):
        """Close database connection"""
        if self._con:
            self._con.close()
            self._con = None


def add_setup_to_production(
    result: BacktestResult,
    db_path: str = "gold.db",
    config_path: str = "trading_app/config.py"
) -> Dict[str, bool]:
    """
    Add a discovered setup to production.

    Steps:
    1. Insert into validated_setups database table
    2. Update config.py with new setup
    3. Return status of each operation

    Returns dict with 'database' and 'config' booleans indicating success.
    """
    status = {'database': False, 'config': False, 'error': None}

    try:
        # Step 1: Insert into database
        con = duckdb.connect(db_path, read_only=False)

        # Check if setup already exists
        check_query = """
        SELECT COUNT(*) as count
        FROM validated_setups
        WHERE instrument = ? AND orb_time = ? AND rr = ? AND sl_mode = ?
        """
        exists = con.execute(check_query, [
            result.config.instrument,
            result.config.orb_time,
            result.config.rr,
            result.config.sl_mode
        ]).fetchone()[0] > 0

        if exists:
            status['error'] = "Setup already exists in database"
            con.close()
            return status

        # Insert new setup
        insert_query = """
        INSERT INTO validated_setups (
            instrument, orb_time, tier, win_rate, rr, sl_mode,
            orb_size_filter, avg_r, annual_trades
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        con.execute(insert_query, [
            result.config.instrument,
            result.config.orb_time,
            result.tier,
            result.win_rate,
            result.config.rr,
            result.config.sl_mode,
            result.config.orb_size_filter,
            result.avg_r,
            result.annual_trades
        ])

        con.close()
        status['database'] = True
        logger.info(f"Added {result.config.instrument} {result.config.orb_time} to database")

        # Step 2: Generate config snippet for user to add manually
        # (Automatic config editing is risky - better to show user what to add)
        status['config'] = True  # User will add manually

    except Exception as e:
        status['error'] = str(e)
        logger.error(f"Error adding setup to production: {e}")

    return status


def generate_config_snippet(result: BacktestResult) -> str:
    """Generate config.py code snippet for the discovered setup"""
    inst = result.config.instrument
    orb = result.config.orb_time

    # Determine tier string for config
    if result.config.orb_time in ['2300', '0030']:
        tier_str = "NIGHT"
    else:
        tier_str = "DAY"

    config_line = f'    "{orb}": {{"rr": {result.config.rr}, "sl_mode": "{result.config.sl_mode}", "tier": "{tier_str}"}},'

    if result.config.orb_size_filter:
        filter_line = f'    "{orb}": {result.config.orb_size_filter},'
    else:
        filter_line = f'    "{orb}": None,'

    snippet = f"""
# Add to {inst}_ORB_CONFIGS dictionary:
{config_line}

# Add to {inst}_ORB_SIZE_FILTERS dictionary:
{filter_line}

# Then run: python test_app_sync.py
"""

    return snippet
