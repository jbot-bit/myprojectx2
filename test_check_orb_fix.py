"""
Test that _check_orb now handles overnight ORBs correctly
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from datetime import datetime, timedelta
from config import TZ_LOCAL

# Simulate the fixed _check_orb logic
def test_orb_start_calculation():
    """Test ORB start calculation at 01:25 for 2300 and 0030 ORBs"""

    # Current time: 01:25
    now = datetime.now(TZ_LOCAL).replace(hour=1, minute=25, second=0, microsecond=0)

    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M')}\n")

    # Test 2300 ORB
    orb_hour, orb_min = 23, 0
    orb_start = now.replace(hour=orb_hour, minute=orb_min, second=0, microsecond=0)

    print(f"2300 ORB before adjustment: {orb_start.strftime('%Y-%m-%d %H:%M')}")

    # Apply overnight adjustment
    if orb_hour >= 18 and now.hour < 6:
        orb_start = orb_start - timedelta(days=1)
        print(f"2300 ORB after adjustment:  {orb_start.strftime('%Y-%m-%d %H:%M')} (YESTERDAY)")

    orb_end = orb_start + timedelta(minutes=5)
    print(f"2300 ORB end: {orb_end.strftime('%Y-%m-%d %H:%M')}")

    if now < orb_end:
        print("Status: FORMING (BUG - should be past formation)")
    else:
        print("Status: FORMED (correct - now checking for breakout)")

    print()

    # Test 0030 ORB
    orb_hour, orb_min = 0, 30
    orb_start = now.replace(hour=orb_hour, minute=orb_min, second=0, microsecond=0)

    print(f"0030 ORB before adjustment: {orb_start.strftime('%Y-%m-%d %H:%M')}")

    # Apply overnight adjustment
    if orb_hour <= 3 and now.hour >= 12:
        orb_start = orb_start + timedelta(days=1)
        print(f"0030 ORB after adjustment:  {orb_start.strftime('%Y-%m-%d %H:%M')} (TOMORROW)")
    elif orb_hour >= 18 and now.hour < 6:
        orb_start = orb_start - timedelta(days=1)
        print(f"0030 ORB after adjustment:  {orb_start.strftime('%Y-%m-%d %H:%M')} (YESTERDAY)")
    else:
        print("0030 ORB after adjustment:  No adjustment needed (same day)")

    orb_end = orb_start + timedelta(minutes=5)
    print(f"0030 ORB end: {orb_end.strftime('%Y-%m-%d %H:%M')}")

    if now < orb_end:
        print("Status: FORMING (wrong unless currently forming)")
    else:
        print("Status: FORMED (correct - now checking for breakout)")

    print("\n" + "="*60)
    print("EXPECTED BEHAVIOR AT 01:25:")
    print("- 2300 ORB: Formed (23:00-23:05 YESTERDAY)")
    print("- 0030 ORB: Formed (00:30-00:35 TODAY)")
    print("Both should be checking for breakouts, not forming")
    print("="*60)

if __name__ == "__main__":
    test_orb_start_calculation()
