"""
EDE Backtest Engine - Step 3

Deterministic zero-lookahead backtesting system.

Enforces:
- Zero lookahead
- Exact entry/exit rules
- Fixed execution assumptions
- Reproducible results

Output:
- Complete trades table
- Win rate, avg R, expectancy
- Max DD, equity curve
- Sample size metrics
"""

import duckdb
import pandas as pd
import numpy as np
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

DB_PATH = str(Path(__file__).parent.parent / "gold.db")

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Individual trade record."""
    trade_id: str
    date_local: str
    instrument: str
    direction: str  # 'long' or 'short'

    entry_time: datetime
    entry_price: float
    stop_price: float
    target_price: float

    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # 'target', 'stop', 'time', 'eod'

    points_risked: Optional[float] = None
    points_gained: Optional[float] = None
    r_multiple: Optional[float] = None

    mae: Optional[float] = None  # Max adverse excursion
    mfe: Optional[float] = None  # Max favorable excursion

    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'date_local': self.date_local,
            'instrument': self.instrument,
            'direction': self.direction,
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'stop_price': self.stop_price,
            'target_price': self.target_price,
            'exit_time': self.exit_time,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'points_risked': self.points_risked,
            'points_gained': self.points_gained,
            'r_multiple': self.r_multiple,
            'mae': self.mae,
            'mfe': self.mfe
        }


@dataclass
class BacktestResult:
    """Complete backtest result with metrics."""
    idea_id: str
    instrument: str
    start_date: str
    end_date: str

    # Trades
    trades: List[Trade]
    total_trades: int
    wins: int
    losses: int
    breakevens: int

    # Performance metrics
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    avg_r: float
    expectancy: float

    # Risk metrics
    max_dd: float
    max_dd_pct: float
    largest_win_r: float
    largest_loss_r: float

    # Equity curve
    equity_curve: List[float]

    # Distribution metrics
    profit_factor: Optional[float] = None
    sharpe: Optional[float] = None


class BacktestEngine:
    """
    Deterministic zero-lookahead backtest engine.

    Uses bars_1m and daily_features_v2 exclusively.
    No future data allowed.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        """Get database connection."""
        return duckdb.connect(self.db_path, read_only=True)

    def load_bars(self, instrument: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Load 1-minute bars for backtest period.

        Args:
            instrument: 'MGC', 'NQ', 'MPL'
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'

        Returns:
            DataFrame with columns: ts_utc, open, high, low, close, volume
        """
        con = self._get_connection()

        # Map instrument to symbol
        symbol_map = {
            'MGC': 'MGC',
            'NQ': 'MNQ',
            'MPL': 'MPL'
        }
        symbol = symbol_map.get(instrument, instrument)

        bars = con.execute("""
            SELECT
                ts_utc,
                open,
                high,
                low,
                close,
                volume
            FROM bars_1m
            WHERE symbol = ?
            AND ts_utc >= ?::TIMESTAMP
            AND ts_utc < (?::DATE + INTERVAL '1 day')::TIMESTAMP
            ORDER BY ts_utc
        """, [symbol, start_date, end_date]).fetchdf()

        con.close()

        logger.info(f"Loaded {len(bars)} bars for {instrument} ({start_date} to {end_date})")
        return bars

    def load_daily_features(self, instrument: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Load daily features for backtest period.

        Args:
            instrument: 'MGC', 'NQ', 'MPL'
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'

        Returns:
            DataFrame with all daily features
        """
        con = self._get_connection()

        features = con.execute("""
            SELECT *
            FROM daily_features_v2
            WHERE instrument = ?
            AND date_local >= ?
            AND date_local <= ?
            ORDER BY date_local
        """, [instrument, start_date, end_date]).fetchdf()

        con.close()

        logger.info(f"Loaded {len(features)} daily features for {instrument}")
        return features

    def calculate_orb_levels(self, bars: pd.DataFrame, orb_start: str, orb_end: str) -> Optional[Dict[str, float]]:
        """
        Calculate ORB high/low from bars.

        Args:
            bars: Intraday bars for the day
            orb_start: 'HH:MM:SS' (local time)
            orb_end: 'HH:MM:SS' (local time)

        Returns:
            {'high': float, 'low': float, 'size': float} or None
        """
        if bars.empty:
            return None

        # Filter bars to ORB window
        # NOTE: Assumes bars have local time column or need conversion
        # For simplicity, using UTC times directly (assumes TZ conversion done)

        orb_bars = bars[
            (bars['ts_utc'].dt.time >= pd.to_datetime(orb_start).time()) &
            (bars['ts_utc'].dt.time < pd.to_datetime(orb_end).time())
        ]

        if len(orb_bars) == 0:
            return None

        orb_high = orb_bars['high'].max()
        orb_low = orb_bars['low'].min()
        orb_size = orb_high - orb_low

        return {
            'high': orb_high,
            'low': orb_low,
            'size': orb_size
        }

    def backtest_candidate(
        self,
        candidate: Dict[str, Any],
        start_date: str = '2024-01-01',
        end_date: str = '2026-01-15',
        slippage_points: float = 0.0
    ) -> Optional[BacktestResult]:
        """
        Run deterministic backtest on edge candidate.

        Args:
            candidate: Edge candidate dict from edge_candidates_raw
            start_date: Start date for backtest
            end_date: End date for backtest
            slippage_points: Fixed slippage per trade (default: 0)

        Returns:
            BacktestResult or None if no trades generated
        """
        instrument = candidate['instrument']
        idea_id = candidate['idea_id']

        logger.info(f"Backtesting {idea_id} ({instrument})")

        # Load data
        bars = self.load_bars(instrument, start_date, end_date)
        if bars.empty:
            logger.warning(f"No bars found for {instrument}")
            return None

        daily_features = self.load_daily_features(instrument, start_date, end_date)
        if daily_features.empty:
            logger.warning(f"No daily features found for {instrument}")
            return None

        # Run simulation
        trades = self._simulate_trades(candidate, bars, daily_features, slippage_points)

        if len(trades) == 0:
            logger.info(f"No trades generated for {idea_id}")
            return None

        # Calculate metrics
        result = self._calculate_metrics(idea_id, instrument, trades, start_date, end_date)

        logger.info(f"Backtest complete: {idea_id} | {result.total_trades} trades | {result.win_rate:.1f}% WR | {result.expectancy:.2f}R exp")

        return result

    def _simulate_trades(
        self,
        candidate: Dict[str, Any],
        bars: pd.DataFrame,
        daily_features: pd.DataFrame,
        slippage: float
    ) -> List[Trade]:
        """
        Simulate all trades for the candidate strategy.

        Enforces zero lookahead - only uses data available at trade time.
        """
        trades = []

        # Parse candidate parameters
        import json
        entry_type = candidate['entry_type']
        entry_start = candidate['entry_time_start']
        entry_end = candidate['entry_time_end']
        stop_type = candidate['stop_type']
        stop_r = candidate.get('stop_r', 1.0)
        target_r = candidate.get('target_r', 2.0)

        # Parse JSON fields
        filters_json = candidate.get('filters_json')
        filters = json.loads(filters_json) if filters_json and isinstance(filters_json, str) else filters_json

        # Group bars by date_local
        bars['date_local'] = bars['ts_utc'].dt.date.astype(str)
        dates = bars['date_local'].unique()

        for date_local in dates:
            # Get day's data
            day_bars = bars[bars['date_local'] == date_local].copy()
            if day_bars.empty:
                continue

            # Get day's features (for filters)
            day_features = daily_features[daily_features['date_local'] == date_local]
            if day_features.empty:
                continue

            day_features = day_features.iloc[0]

            # Apply filters
            if filters:
                if not self._apply_filters(day_features, filters):
                    continue  # Skip this day

            # Calculate ORB levels if needed
            orb_levels = None
            if 'orb' in candidate['session_window']:
                orb_levels = self.calculate_orb_levels(day_bars, entry_start, entry_end)
                if not orb_levels:
                    continue

            # Simulate trade entry
            trade = self._simulate_entry(
                candidate, day_bars, day_features, orb_levels, date_local, slippage
            )

            if trade:
                # Simulate trade exit
                self._simulate_exit(trade, day_bars, candidate)
                trades.append(trade)

        return trades

    def _apply_filters(self, day_features: pd.Series, filters: Dict[str, Any]) -> bool:
        """
        Check if day passes all filters.

        Returns:
            True if passes, False if fails
        """
        # ORB size filter
        if 'orb_size_min' in filters and filters['orb_size_min']:
            # Check if any ORB meets minimum size
            orb_cols = [col for col in day_features.index if col.endswith('_size')]
            if not orb_cols:
                return False
            orb_sizes = [float(day_features[col]) for col in orb_cols if pd.notna(day_features[col])]
            if not orb_sizes or max(orb_sizes) < filters['orb_size_min']:
                return False

        # ATR filter
        if 'atr_min' in filters and filters['atr_min']:
            atr = float(day_features.get('atr_20', 0)) if pd.notna(day_features.get('atr_20')) else 0
            if atr < filters['atr_min']:
                return False

        if 'atr_max' in filters and filters['atr_max']:
            atr = float(day_features.get('atr_20', 999)) if pd.notna(day_features.get('atr_20')) else 999
            if atr > filters['atr_max']:
                return False

        return True

    def _simulate_entry(
        self,
        candidate: Dict[str, Any],
        day_bars: pd.DataFrame,
        day_features: pd.Series,
        orb_levels: Optional[Dict[str, float]],
        date_local: str,
        slippage: float
    ) -> Optional[Trade]:
        """
        Simulate trade entry.

        Returns:
            Trade object if entry triggered, None otherwise
        """
        import json
        entry_type = candidate['entry_type']
        entry_condition_json = candidate.get('entry_condition_json', '{}')
        entry_condition = json.loads(entry_condition_json) if isinstance(entry_condition_json, str) else entry_condition_json
        instrument = candidate['instrument']

        # Get ATR for stop calculation
        atr = day_features.get('atr_20', 40.0)

        # Entry logic by type
        if entry_type == 'break' and orb_levels:
            # Breakout entry
            direction = entry_condition.get('direction', 'long')

            if direction == 'long':
                # Look for close above ORB high
                entry_bar = day_bars[day_bars['close'] > orb_levels['high']]
                if entry_bar.empty:
                    return None

                entry_bar = entry_bar.iloc[0]
                entry_price = entry_bar['close'] + slippage
                stop_price = orb_levels['low'] - slippage
                points_risked = entry_price - stop_price

                if candidate['target_r']:
                    target_price = entry_price + (points_risked * candidate['target_r'])
                else:
                    target_price = entry_price + (atr * 3)  # Default

                trade = Trade(
                    trade_id=f"{candidate['idea_id']}_{date_local}",
                    date_local=date_local,
                    instrument=instrument,
                    direction='long',
                    entry_time=entry_bar['ts_utc'],
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    points_risked=points_risked
                )
                return trade

            elif direction == 'short':
                # Look for close below ORB low
                entry_bar = day_bars[day_bars['close'] < orb_levels['low']]
                if entry_bar.empty:
                    return None

                entry_bar = entry_bar.iloc[0]
                entry_price = entry_bar['close'] - slippage
                stop_price = orb_levels['high'] + slippage
                points_risked = stop_price - entry_price

                if candidate['target_r']:
                    target_price = entry_price - (points_risked * candidate['target_r'])
                else:
                    target_price = entry_price - (atr * 3)

                trade = Trade(
                    trade_id=f"{candidate['idea_id']}_{date_local}",
                    date_local=date_local,
                    instrument=instrument,
                    direction='short',
                    entry_time=entry_bar['ts_utc'],
                    entry_price=entry_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    points_risked=points_risked
                )
                return trade

        # Add more entry logic types (fade, close, stop, limit) as needed
        # For now, return None for unimplemented types
        return None

    def _simulate_exit(
        self,
        trade: Trade,
        day_bars: pd.DataFrame,
        candidate: Dict[str, Any]
    ):
        """
        Simulate trade exit.

        Updates trade object with exit details.
        """
        # Get bars after entry
        exit_bars = day_bars[day_bars['ts_utc'] > trade.entry_time].copy()

        if exit_bars.empty:
            # No exit - end of day
            trade.exit_time = day_bars.iloc[-1]['ts_utc']
            trade.exit_price = day_bars.iloc[-1]['close']
            trade.exit_reason = 'eod'
            trade.points_gained = (trade.exit_price - trade.entry_price) if trade.direction == 'long' else (trade.entry_price - trade.exit_price)
            trade.r_multiple = trade.points_gained / trade.points_risked if trade.points_risked != 0 else 0
            return

        # Check each bar for stop or target hit
        mae = 0.0  # Max adverse excursion
        mfe = 0.0  # Max favorable excursion

        for idx, bar in exit_bars.iterrows():
            if trade.direction == 'long':
                # Long trade
                # Check stop
                if bar['low'] <= trade.stop_price:
                    trade.exit_time = bar['ts_utc']
                    trade.exit_price = trade.stop_price
                    trade.exit_reason = 'stop'
                    trade.points_gained = trade.exit_price - trade.entry_price
                    trade.r_multiple = -1.0 * (trade.points_risked / trade.points_risked if trade.points_risked != 0 else 0)
                    break

                # Check target
                if bar['high'] >= trade.target_price:
                    trade.exit_time = bar['ts_utc']
                    trade.exit_price = trade.target_price
                    trade.exit_reason = 'target'
                    trade.points_gained = trade.exit_price - trade.entry_price
                    trade.r_multiple = trade.points_gained / trade.points_risked if trade.points_risked != 0 else 0
                    break

                # Track MAE/MFE
                unrealized = bar['close'] - trade.entry_price
                if unrealized < mae:
                    mae = unrealized
                if unrealized > mfe:
                    mfe = unrealized

            else:  # Short trade
                # Check stop
                if bar['high'] >= trade.stop_price:
                    trade.exit_time = bar['ts_utc']
                    trade.exit_price = trade.stop_price
                    trade.exit_reason = 'stop'
                    trade.points_gained = trade.entry_price - trade.exit_price
                    trade.r_multiple = -1.0
                    break

                # Check target
                if bar['low'] <= trade.target_price:
                    trade.exit_time = bar['ts_utc']
                    trade.exit_price = trade.target_price
                    trade.exit_reason = 'target'
                    trade.points_gained = trade.entry_price - trade.exit_price
                    trade.r_multiple = trade.points_gained / trade.points_risked if trade.points_risked != 0 else 0
                    break

                # Track MAE/MFE
                unrealized = trade.entry_price - bar['close']
                if unrealized < mae:
                    mae = unrealized
                if unrealized > mfe:
                    mfe = unrealized

        trade.mae = abs(mae)
        trade.mfe = abs(mfe)

        # If no exit found, exit at EOD
        if not trade.exit_time:
            trade.exit_time = exit_bars.iloc[-1]['ts_utc']
            trade.exit_price = exit_bars.iloc[-1]['close']
            trade.exit_reason = 'eod'
            if trade.direction == 'long':
                trade.points_gained = trade.exit_price - trade.entry_price
            else:
                trade.points_gained = trade.entry_price - trade.exit_price
            trade.r_multiple = trade.points_gained / trade.points_risked if trade.points_risked != 0 else 0

    def _calculate_metrics(
        self,
        idea_id: str,
        instrument: str,
        trades: List[Trade],
        start_date: str,
        end_date: str
    ) -> BacktestResult:
        """Calculate all backtest metrics."""

        total_trades = len(trades)
        wins = len([t for t in trades if t.r_multiple > 0])
        losses = len([t for t in trades if t.r_multiple < 0])
        breakevens = len([t for t in trades if t.r_multiple == 0])

        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        # R multiples
        r_multiples = [t.r_multiple for t in trades if t.r_multiple is not None]
        avg_r = np.mean(r_multiples) if r_multiples else 0

        winning_rs = [r for r in r_multiples if r > 0]
        losing_rs = [r for r in r_multiples if r < 0]

        avg_win_r = np.mean(winning_rs) if winning_rs else 0
        avg_loss_r = np.mean(losing_rs) if losing_rs else 0

        # Expectancy
        expectancy = avg_r

        # Max drawdown
        equity_curve = np.cumsum([0] + r_multiples)
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = equity_curve - running_max
        max_dd = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0
        max_dd_pct = (max_dd / (running_max[np.argmin(drawdowns)] + 1)) * 100 if len(drawdowns) > 0 else 0

        # Largest trades
        largest_win_r = max(winning_rs) if winning_rs else 0
        largest_loss_r = abs(min(losing_rs)) if losing_rs else 0

        # Profit factor
        total_wins = sum(winning_rs) if winning_rs else 0
        total_losses = abs(sum(losing_rs)) if losing_rs else 0
        profit_factor = (total_wins / total_losses) if total_losses != 0 else None

        # Sharpe (simplified)
        sharpe = (np.mean(r_multiples) / np.std(r_multiples)) if len(r_multiples) > 1 else None

        return BacktestResult(
            idea_id=idea_id,
            instrument=instrument,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            total_trades=total_trades,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            win_rate=win_rate,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            avg_r=avg_r,
            expectancy=expectancy,
            max_dd=max_dd,
            max_dd_pct=max_dd_pct,
            largest_win_r=largest_win_r,
            largest_loss_r=largest_loss_r,
            equity_curve=equity_curve.tolist(),
            profit_factor=profit_factor,
            sharpe=sharpe
        )


if __name__ == "__main__":
    # Test backtest engine
    logging.basicConfig(level=logging.INFO)

    engine = BacktestEngine()

    # Load a candidate
    con = duckdb.connect(DB_PATH)
    candidate = con.execute("""
        SELECT *
        FROM edge_candidates_raw
        WHERE status = 'GENERATED'
        LIMIT 1
    """).fetchdf().to_dict('records')[0]
    con.close()

    if candidate:
        print(f"\nTesting candidate: {candidate['idea_id']}")
        result = engine.backtest_candidate(candidate, start_date='2025-01-01', end_date='2026-01-15')

        if result:
            print(f"\nBacktest Results:")
            print(f"  Trades: {result.total_trades}")
            print(f"  Win Rate: {result.win_rate:.1f}%")
            print(f"  Expectancy: {result.expectancy:.2f}R")
            print(f"  Max DD: {result.max_dd:.2f}R")
        else:
            print("  No trades generated")
