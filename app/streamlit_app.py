"""
Mobile Trading App Entry Point for Streamlit Cloud
"""

import sys
from pathlib import Path

# Add trading_app to path
sys.path.insert(0, str(Path(__file__).parent.parent / "trading_app"))

# Import the mobile app module
import app_mobile
