"""
Utility script to run ML training.

Usage:
    python ml_scripts/run_training.py --model directional
    python ml_scripts/run_training.py --model entry_quality
    python ml_scripts/run_training.py --model r_multiple
    python ml_scripts/run_training.py --all  # Train all models
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_training.train_pipeline import MLTrainingPipeline


def main():
    parser = argparse.ArgumentParser(description='Run ML training')
    parser.add_argument('--model', type=str, choices=['directional', 'entry_quality', 'r_multiple'])
    parser.add_argument('--all', action='store_true', help='Train all models')
    parser.add_argument('--data', type=str, default='ml_data/historical_features.parquet')

    args = parser.parse_args()

    if args.all:
        models = ['directional', 'entry_quality', 'r_multiple']
    elif args.model:
        models = [args.model]
    else:
        print("Error: Specify --model or --all")
        sys.exit(1)

    for model_name in models:
        print(f"\n{'='*60}")
        print(f"Training {model_name} model...")
        print('='*60)

        pipeline = MLTrainingPipeline(model_name)
        try:
            pipeline.run()
            print(f"\n[SUCCESS] {model_name} training complete!")
        except Exception as e:
            print(f"\n[FAILED] {model_name} training failed: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()
