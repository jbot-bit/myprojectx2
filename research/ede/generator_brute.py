"""
EDE Generator - Mode A: Brute Parameter Search

Systematically enumerates parameter space:
- Time windows (any start/end)
- Entry logic (break / fade / close / stop)
- Stop logic (fixed / half / ATR / structure)
- Targets (fixed R, trailing, time-based)

Output: raw parameter sets for backtesting

NO validation yet. Just structured hypothesis generation.
"""

import uuid
import time
import random
from datetime import datetime, time as dt_time
from typing import List, Dict, Any, Tuple
from itertools import product
import logging

from lifecycle_manager import EdgeCandidate, LifecycleManager

logger = logging.getLogger(__name__)


class BruteParameterGenerator:
    """
    Brute force parameter space exploration.

    Generates all reasonable combinations of:
    - Time windows
    - Entry types
    - Exit types
    - Risk models
    """

    def __init__(self, instruments: List[str] = ['MGC', 'NQ', 'MPL']):
        self.instruments = instruments
        self.lifecycle_manager = LifecycleManager()

    def generate_time_windows(self) -> List[Tuple[str, str, str]]:
        """
        Generate all reasonable time windows for trading.

        Returns:
            List of (session_name, start_time, end_time) tuples
        """
        windows = []

        # ORB windows (5-minute windows at key times)
        orb_times = [
            ('orb_0030', '00:30:00', '00:35:00'),
            ('orb_0900', '09:00:00', '09:05:00'),
            ('orb_1000', '10:00:00', '10:05:00'),
            ('orb_1100', '11:00:00', '11:05:00'),
            ('orb_1800', '18:00:00', '18:05:00'),
            ('orb_2300', '23:00:00', '23:05:00'),
        ]
        windows.extend(orb_times)

        # Session windows
        session_windows = [
            ('asia_full', '09:00:00', '17:00:00'),
            ('london_full', '18:00:00', '23:00:00'),
            ('ny_full', '23:00:00', '02:00:00'),
            ('asia_morning', '09:00:00', '12:00:00'),
            ('asia_afternoon', '12:00:00', '17:00:00'),
            ('london_open', '18:00:00', '20:00:00'),
            ('ny_open', '23:00:00', '01:00:00'),
        ]
        windows.extend(session_windows)

        # Custom windows (hourly increments)
        for hour_start in range(0, 24):
            for hour_end in range(hour_start + 1, min(hour_start + 8, 24)):
                session_name = f'custom_{hour_start:02d}_{hour_end:02d}'
                start_time = f'{hour_start:02d}:00:00'
                end_time = f'{hour_end:02d}:00:00'
                windows.append((session_name, start_time, end_time))

        return windows

    def generate_entry_types(self) -> List[Dict[str, Any]]:
        """
        Generate all entry logic variations.

        Returns:
            List of entry configuration dicts
        """
        entries = []

        # Break entries (breakout of range)
        entries.append({
            'type': 'break',
            'condition': {
                'direction': 'long',
                'trigger': 'close_above_high'
            }
        })
        entries.append({
            'type': 'break',
            'condition': {
                'direction': 'short',
                'trigger': 'close_below_low'
            }
        })

        # Fade entries (counter-trend)
        entries.append({
            'type': 'fade',
            'condition': {
                'direction': 'long',
                'trigger': 'buy_at_low'
            }
        })
        entries.append({
            'type': 'fade',
            'condition': {
                'direction': 'short',
                'trigger': 'sell_at_high'
            }
        })

        # Close entries (wait for close confirmation)
        entries.append({
            'type': 'close',
            'condition': {
                'direction': 'both',
                'trigger': 'first_5min_close'
            }
        })

        # Stop entries (stop orders)
        entries.append({
            'type': 'stop',
            'condition': {
                'direction': 'long',
                'trigger': 'stop_buy_above_high'
            }
        })
        entries.append({
            'type': 'stop',
            'condition': {
                'direction': 'short',
                'trigger': 'stop_sell_below_low'
            }
        })

        # Limit entries (limit orders)
        entries.append({
            'type': 'limit',
            'condition': {
                'direction': 'long',
                'trigger': 'limit_buy_at_low'
            }
        })
        entries.append({
            'type': 'limit',
            'condition': {
                'direction': 'short',
                'trigger': 'limit_sell_at_high'
            }
        })

        return entries

    def generate_exit_types(self) -> List[Dict[str, Any]]:
        """
        Generate all exit logic variations.

        Returns:
            List of exit configuration dicts
        """
        exits = []

        # Fixed R exits (classic stop/target)
        for stop_r in [0.5, 1.0, 1.5, 2.0]:
            for target_r in [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 8.0]:
                if target_r > stop_r:  # Ensure positive RR
                    exits.append({
                        'type': 'fixed_r',
                        'stop_type': 'fixed_r',
                        'stop_r': stop_r,
                        'target_r': target_r,
                        'condition': {
                            'stop_mode': 'fixed_points',
                            'target_mode': 'fixed_points'
                        }
                    })

        # ATR-scaled exits
        for atr_mult_stop in [0.5, 1.0, 1.5]:
            for atr_mult_target in [1.0, 2.0, 3.0]:
                exits.append({
                    'type': 'fixed_r',
                    'stop_type': 'atr',
                    'stop_r': atr_mult_stop,
                    'target_r': atr_mult_target,
                    'condition': {
                        'stop_mode': 'atr_scaled',
                        'target_mode': 'atr_scaled'
                    }
                })

        # Half exits (structure-based)
        exits.append({
            'type': 'fixed_r',
            'stop_type': 'half',
            'stop_r': 0.5,
            'target_r': 2.0,
            'condition': {
                'stop_mode': 'half_range',
                'target_mode': 'range_multiple'
            }
        })

        # Trailing exits
        exits.append({
            'type': 'trailing',
            'stop_type': 'atr',
            'stop_r': 1.0,
            'target_r': None,
            'condition': {
                'trail_mode': 'atr_trail',
                'trail_distance': 1.0
            }
        })

        # Time-based exits
        for hours in [1, 2, 4, 6]:
            exits.append({
                'type': 'time',
                'stop_type': 'fixed_r',
                'stop_r': 2.0,
                'target_r': None,
                'condition': {
                    'max_hold_hours': hours,
                    'exit_mode': 'time_limit'
                }
            })

        return exits

    def generate_risk_models(self) -> List[Dict[str, Any]]:
        """
        Generate risk model variations.

        Returns:
            List of risk configuration dicts
        """
        return [
            {'type': 'fixed_r', 'risk_pct': 1.0},
            {'type': 'fixed_r', 'risk_pct': 0.5},
            {'type': 'fixed_r', 'risk_pct': 2.0},
            {'type': 'dynamic_atr', 'risk_pct': 1.0},
            {'type': 'volatility_scaled', 'risk_pct': 1.0},
        ]

    def generate_filters(self) -> List[Dict[str, Any]]:
        """
        Generate filter variations.

        Returns:
            List of filter configuration dicts
        """
        filters = []

        # No filters
        filters.append(None)

        # ORB size filters
        for min_size in [0.02, 0.05, 0.10]:
            filters.append({
                'orb_size_min': min_size,
                'orb_size_max': None
            })

        # Volatility filters
        filters.append({
            'atr_min': None,
            'atr_max': 50.0
        })
        filters.append({
            'atr_min': 30.0,
            'atr_max': None
        })

        # Session filters
        filters.append({
            'prior_day_range_min': 20.0,
            'prior_day_range_max': None
        })

        return filters

    def generate_candidates(
        self,
        max_candidates: int = 500,
        instruments: List[str] = None,
        randomize: bool = True
    ) -> List[EdgeCandidate]:
        """
        Generate edge candidates by brute force enumeration.

        Args:
            max_candidates: Maximum number of candidates to generate
            instruments: List of instruments to generate for (default: all)
            randomize: Randomize order to avoid bias

        Returns:
            List of EdgeCandidate objects
        """
        if instruments is None:
            instruments = self.instruments

        # Generate parameter space
        time_windows = self.generate_time_windows()
        entry_types = self.generate_entry_types()
        exit_types = self.generate_exit_types()
        risk_models = self.generate_risk_models()
        filters_list = self.generate_filters()

        logger.info(f"Parameter space size:")
        logger.info(f"  Time windows: {len(time_windows)}")
        logger.info(f"  Entry types: {len(entry_types)}")
        logger.info(f"  Exit types: {len(exit_types)}")
        logger.info(f"  Risk models: {len(risk_models)}")
        logger.info(f"  Filters: {len(filters_list)}")

        total_combinations = (
            len(instruments) *
            len(time_windows) *
            len(entry_types) *
            len(exit_types) *
            len(risk_models) *
            len(filters_list)
        )

        logger.info(f"Total combinations: {total_combinations:,}")

        # Generate all combinations
        all_combinations = list(product(
            instruments,
            time_windows,
            entry_types,
            exit_types,
            risk_models,
            filters_list
        ))

        # Randomize to avoid bias
        if randomize:
            random.shuffle(all_combinations)

        # Limit to max_candidates
        selected_combinations = all_combinations[:max_candidates]

        logger.info(f"Generating {len(selected_combinations)} candidates...")

        candidates = []
        for instrument, time_window, entry, exit, risk, filters in selected_combinations:
            session_name, start_time, end_time = time_window

            # Generate unique ID
            idea_id = f"BRUTE_{instrument}_{session_name}_{str(uuid.uuid4())[:8]}"

            # Generate human name
            human_name = f"{instrument}_{session_name}_{entry['type']}_{exit['type']}"

            # Required features (from daily_features_v2)
            required_features = ['atr_20']
            if 'orb' in session_name:
                orb_prefix = session_name.replace('orb_', '')
                required_features.extend([
                    f'orb_{orb_prefix}_high',
                    f'orb_{orb_prefix}_low',
                    f'orb_{orb_prefix}_size'
                ])

            # Create candidate
            candidate = EdgeCandidate(
                idea_id=idea_id,
                human_name=human_name,
                instrument=instrument,
                generator_mode='brute',
                entry_type=entry['type'],
                entry_time_start=start_time,
                entry_time_end=end_time,
                entry_condition=entry['condition'],
                exit_type=exit['type'],
                stop_type=exit['stop_type'],
                stop_r=exit['stop_r'],
                target_r=exit['target_r'],
                exit_condition=exit['condition'],
                session_window=session_name,
                time_window_start=start_time,
                time_window_end=end_time,
                required_features=required_features,
                risk_model=risk['type'],
                risk_pct=risk['risk_pct'],
                filters=filters,
                assumptions={
                    'execution': 'close_based',
                    'slippage': 0,
                    'commission': 0
                },
                generation_notes=f"Brute force parameter search: {len(candidates)+1}/{len(selected_combinations)}"
            )

            candidates.append(candidate)

        logger.info(f"Generated {len(candidates)} candidates")
        return candidates

    def run_generation(
        self,
        max_candidates: int = 500,
        instruments: List[str] = None,
        submit_to_pipeline: bool = True
    ) -> Dict[str, Any]:
        """
        Run brute force generation and optionally submit to pipeline.

        Args:
            max_candidates: Maximum candidates to generate
            instruments: Instruments to generate for
            submit_to_pipeline: If True, submit to lifecycle manager

        Returns:
            Generation statistics
        """
        start_time = time.time()

        candidates = self.generate_candidates(
            max_candidates=max_candidates,
            instruments=instruments
        )

        stats = {
            'generated': len(candidates),
            'duplicates': 0,
            'invalid': 0,
            'accepted': 0,
            'rejected': 0
        }

        if submit_to_pipeline:
            logger.info("Submitting candidates to pipeline...")

            for candidate in candidates:
                success, message = self.lifecycle_manager.submit_candidate(candidate)

                if success:
                    stats['accepted'] += 1
                else:
                    if 'Duplicate' in message:
                        stats['duplicates'] += 1
                    elif 'Validation failed' in message:
                        stats['invalid'] += 1
                    else:
                        stats['rejected'] += 1

        duration = time.time() - start_time

        # Log generation run
        self.lifecycle_manager.log_generation_run(
            mode='brute',
            config={
                'max_candidates': max_candidates,
                'instruments': instruments or self.instruments
            },
            generated=stats['generated'],
            duplicates=stats['duplicates'],
            invalid=stats['invalid'],
            accepted=stats['accepted'],
            duration=duration,
            notes=f"Brute force parameter search"
        )

        logger.info(f"Generation complete in {duration:.1f}s")
        logger.info(f"Stats: {stats}")

        return stats


if __name__ == "__main__":
    # Test brute generator
    logging.basicConfig(level=logging.INFO)

    generator = BruteParameterGenerator(instruments=['MGC'])

    print("\n" + "="*70)
    print("BRUTE PARAMETER GENERATOR - MODE A")
    print("="*70)

    # Generate small batch for testing
    stats = generator.run_generation(
        max_candidates=50,
        instruments=['MGC'],
        submit_to_pipeline=True
    )

    print("\nGeneration Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\nBrute generator ready for full-scale discovery.")
