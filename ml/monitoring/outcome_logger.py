"""
ML Outcome Logger

Logs ML predictions and actual outcomes for performance monitoring.

Database Schema:
- ml_predictions: Store predictions when made
- ml_outcomes: Store actual results when trade completes

Usage:
    from ml_monitoring.outcome_logger import OutcomeLogger

    logger = OutcomeLogger()

    # Log prediction
    prediction_id = logger.log_prediction(features, prediction, evaluation)

    # Log outcome (when trade completes)
    logger.log_outcome(prediction_id, actual_direction, actual_r_multiple, win=True)
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import duckdb
from pathlib import Path

logger = logging.getLogger(__name__)


class OutcomeLogger:
    """Logs ML predictions and outcomes to database."""

    def __init__(self, db_path: str = "gold.db"):
        """
        Initialize outcome logger.

        Args:
            db_path: Path to DuckDB database
        """
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist."""
        conn = duckdb.connect(self.db_path)

        try:
            # Predictions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_predictions (
                    prediction_id VARCHAR PRIMARY KEY,
                    timestamp_utc TIMESTAMP,
                    instrument VARCHAR,
                    orb_time VARCHAR,
                    strategy_name VARCHAR,

                    -- ML Prediction
                    predicted_direction VARCHAR,
                    confidence FLOAT,
                    confidence_level VARCHAR,
                    prob_up FLOAT,
                    prob_down FLOAT,
                    prob_none FLOAT,

                    -- Risk Adjustment
                    risk_adjustment FLOAT,

                    -- Context
                    orb_size FLOAT,
                    atr_14 FLOAT,
                    rsi_14 FLOAT,

                    -- Outcome (filled later)
                    actual_direction VARCHAR,
                    actual_r_multiple FLOAT,
                    win BOOLEAN,
                    outcome_logged_at TIMESTAMP
                )
            """)

            # Performance metrics table (daily aggregates)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ml_performance (
                    date_local DATE,
                    instrument VARCHAR,
                    model_version VARCHAR,

                    total_predictions INT,
                    correct_predictions INT,
                    directional_accuracy FLOAT,

                    avg_confidence FLOAT,
                    wins INT,
                    losses INT,
                    win_rate FLOAT,

                    avg_r_multiple FLOAT,

                    created_at TIMESTAMP,

                    PRIMARY KEY (date_local, instrument, model_version)
                )
            """)

            logger.info("ML outcome logging tables ready")

        except Exception as e:
            logger.error(f"Failed to create tables: {e}")

        finally:
            conn.close()

    def log_prediction(
        self,
        features: Dict[str, Any],
        prediction: Dict[str, float],
        evaluation: Any,
        model_version: str = "v_20260117_023515"
    ) -> str:
        """
        Log an ML prediction.

        Args:
            features: Feature dictionary used for prediction
            prediction: ML prediction dict from inference engine
            evaluation: Strategy evaluation object
            model_version: Model version used

        Returns:
            prediction_id: Unique ID for this prediction
        """
        import uuid

        prediction_id = str(uuid.uuid4())
        timestamp_utc = datetime.utcnow()

        conn = duckdb.connect(self.db_path)

        try:
            conn.execute("""
                INSERT INTO ml_predictions (
                    prediction_id, timestamp_utc, instrument, orb_time, strategy_name,
                    predicted_direction, confidence, confidence_level,
                    prob_up, prob_down, prob_none,
                    risk_adjustment,
                    orb_size, atr_14, rsi_14
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                prediction_id,
                timestamp_utc,
                features.get('instrument', 'UNKNOWN'),
                features.get('orb_time', 'UNKNOWN'),
                evaluation.strategy_name if evaluation else 'UNKNOWN',
                prediction['predicted_direction'],
                prediction['confidence'],
                prediction.get('confidence_level', 'UNKNOWN'),
                prediction['prob_up'],
                prediction['prob_down'],
                prediction['prob_none'],
                prediction.get('risk_adjustment', 1.0),
                features.get('orb_size', 0.0),
                features.get('atr_14', 0.0),
                features.get('rsi_14', 50.0),
            ])

            logger.info(f"Logged prediction {prediction_id}: {prediction['predicted_direction']} @ {prediction['confidence']:.1%}")

        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")
            return None

        finally:
            conn.close()

        return prediction_id

    def log_outcome(
        self,
        prediction_id: str,
        actual_direction: str,
        actual_r_multiple: float,
        win: bool
    ):
        """
        Log the actual outcome of a trade.

        Args:
            prediction_id: ID from log_prediction()
            actual_direction: Actual break direction (UP/DOWN/NONE)
            actual_r_multiple: Actual R-multiple achieved
            win: Whether trade was profitable
        """
        conn = duckdb.connect(self.db_path)

        try:
            conn.execute("""
                UPDATE ml_predictions
                SET actual_direction = ?,
                    actual_r_multiple = ?,
                    win = ?,
                    outcome_logged_at = ?
                WHERE prediction_id = ?
            """, [actual_direction, actual_r_multiple, win, datetime.utcnow(), prediction_id])

            logger.info(f"Logged outcome for {prediction_id}: {actual_direction}, R={actual_r_multiple:.2f}, Win={win}")

        except Exception as e:
            logger.error(f"Failed to log outcome: {e}")

        finally:
            conn.close()

    def compute_daily_performance(self, date_local: str, instrument: str = "MGC"):
        """
        Compute daily performance metrics.

        Args:
            date_local: Date to compute metrics for (YYYY-MM-DD)
            instrument: Instrument to compute for
        """
        conn = duckdb.connect(self.db_path)

        try:
            # Get predictions for this day
            result = conn.execute("""
                SELECT
                    COUNT(*) as total_predictions,
                    SUM(CASE WHEN predicted_direction = actual_direction THEN 1 ELSE 0 END) as correct_predictions,
                    AVG(confidence) as avg_confidence,
                    SUM(CASE WHEN win = true THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN win = false THEN 1 ELSE 0 END) as losses,
                    AVG(actual_r_multiple) as avg_r_multiple
                FROM ml_predictions
                WHERE DATE(timestamp_utc) = ?
                  AND instrument = ?
                  AND actual_direction IS NOT NULL
            """, [date_local, instrument]).fetchone()

            if result and result[0] > 0:
                total, correct, avg_conf, wins, losses, avg_r = result

                directional_accuracy = correct / total if total > 0 else 0
                win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0

                # Insert into performance table
                conn.execute("""
                    INSERT OR REPLACE INTO ml_performance (
                        date_local, instrument, model_version,
                        total_predictions, correct_predictions, directional_accuracy,
                        avg_confidence, wins, losses, win_rate,
                        avg_r_multiple, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    date_local, instrument, "latest",
                    total, correct, directional_accuracy,
                    avg_conf, wins, losses, win_rate,
                    avg_r, datetime.utcnow()
                ])

                logger.info(f"Computed daily performance for {date_local}: "
                          f"{directional_accuracy:.1%} accuracy, {win_rate:.1%} win rate")

        except Exception as e:
            logger.error(f"Failed to compute daily performance: {e}")

        finally:
            conn.close()

    def get_recent_performance(self, days: int = 7, instrument: str = "MGC") -> Dict[str, float]:
        """
        Get performance metrics for recent period.

        Args:
            days: Number of days to look back
            instrument: Instrument to query

        Returns:
            Dictionary of performance metrics
        """
        conn = duckdb.connect(self.db_path)

        try:
            result = conn.execute("""
                SELECT
                    AVG(directional_accuracy) as avg_accuracy,
                    AVG(win_rate) as avg_win_rate,
                    AVG(avg_r_multiple) as avg_r_multiple,
                    SUM(total_predictions) as total_predictions
                FROM ml_performance
                WHERE date_local >= CURRENT_DATE - INTERVAL ? DAY
                  AND instrument = ?
            """, [days, instrument]).fetchone()

            if result:
                return {
                    'avg_accuracy': result[0] or 0,
                    'avg_win_rate': result[1] or 0,
                    'avg_r_multiple': result[2] or 0,
                    'total_predictions': result[3] or 0
                }

        except Exception as e:
            logger.error(f"Failed to get recent performance: {e}")

        finally:
            conn.close()

        return {'avg_accuracy': 0, 'avg_win_rate': 0, 'avg_r_multiple': 0, 'total_predictions': 0}


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    logger_instance = OutcomeLogger()

    # Example: Log a prediction
    sample_features = {
        'instrument': 'MGC',
        'orb_time': '0900',
        'orb_size': 0.7,
        'atr_14': 5.2,
        'rsi_14': 55.0,
    }

    sample_prediction = {
        'predicted_direction': 'UP',
        'confidence': 0.52,
        'confidence_level': 'LOW',
        'prob_up': 0.52,
        'prob_down': 0.48,
        'prob_none': 0.0,
    }

    print("Logging sample prediction...")
    pred_id = logger_instance.log_prediction(sample_features, sample_prediction, None)

    if pred_id:
        print(f"Prediction ID: {pred_id}")

        # Later, log the outcome
        print("\nLogging sample outcome...")
        logger_instance.log_outcome(pred_id, 'UP', 1.5, win=True)

        print("\n✓ Outcome logging system working!")
