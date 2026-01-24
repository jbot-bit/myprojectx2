"""
Test what active ORB windows should be showing RIGHT NOW
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "trading_app"))

from datetime import datetime, timedelta
from config import TZ_LOCAL

# Simulate the _get_active_orb_windows logic
ORB_TIMES = [
    {"name": "0900", "hour": 9, "min": 0},
    {"name": "1000", "hour": 10, "min": 0},
    {"name": "1100", "hour": 11, "min": 0},
    {"name": "1800", "hour": 18, "min": 0},
    {"name": "2300", "hour": 23, "min": 0},
    {"name": "0030", "hour": 0, "min": 30},
]

def get_active_orb_windows(current_time):
    active_orbs = []
    EXPIRATION_HOURS = 3

    for orb_time in ORB_TIMES:
        orb_name = orb_time["name"]
        orb_hour = orb_time["hour"]
        orb_min = orb_time["min"]

        orb_start = current_time.replace(
            hour=orb_hour,
            minute=orb_min,
            second=0,
            microsecond=0
        )

        # Handle overnight ORBs
        if orb_hour <= 3 and current_time.hour >= 12:
            orb_start = orb_start + timedelta(days=1)
            print(f"  {orb_name}: Adjusted to TOMORROW (afternoon checking early morning ORB)")
        elif orb_hour >= 18 and current_time.hour < 6:
            orb_start = orb_start - timedelta(days=1)
            print(f"  {orb_name}: Adjusted to YESTERDAY (early morning checking evening ORB)")

        orb_expiration = orb_start + timedelta(hours=EXPIRATION_HOURS)

        print(f"  {orb_name}: start={orb_start.strftime('%Y-%m-%d %H:%M')}, expire={orb_expiration.strftime('%Y-%m-%d %H:%M')}")

        if orb_start <= current_time < orb_expiration:
            print(f"    -> ACTIVE!")
            active_orbs.append(orb_name)
        else:
            if current_time < orb_start:
                print(f"    -> Not yet (starts in {(orb_start - current_time).total_seconds()/60:.0f} min)")
            else:
                print(f"    -> Expired (ended {(current_time - orb_expiration).total_seconds()/60:.0f} min ago)")

    return active_orbs

if __name__ == "__main__":
    now = datetime.now(TZ_LOCAL)
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Hour: {now.hour}, Minute: {now.minute}\n")

    print("Checking all ORB windows:\n")
    active = get_active_orb_windows(now)

    print(f"\n{'='*60}")
    print(f"ACTIVE ORB WINDOWS: {active}")
    print(f"{'='*60}")

    if not active:
        print("\nERROR: No active ORBs detected!")
        print("This is the bug causing 'wait for 2300' message.")
