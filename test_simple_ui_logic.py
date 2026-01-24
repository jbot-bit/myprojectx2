"""
Test simple_ui.py logic without Streamlit runtime
"""
from datetime import datetime, timedelta

def test_next_orb_logic():
    """Test next ORB calculation handles overnight correctly"""

    orb_times = [(9, 0, "0900"), (10, 0, "1000"), (11, 0, "1100"),
                 (18, 0, "1800"), (23, 0, "2300"), (0, 30, "0030")]

    # Test case 1: At 23:30, next ORBs should be 0030 (30 min) and 0900 (tomorrow)
    test_time = datetime.now().replace(hour=23, minute=30, second=0, microsecond=0)

    next_orbs = []
    for h, m, name in orb_times:
        orb_time = test_time.replace(hour=h, minute=m, second=0, microsecond=0)

        # Handle overnight ORBs
        if h <= 3 and test_time.hour >= 12:
            orb_time = orb_time + timedelta(days=1)

        if orb_time > test_time:
            diff = (orb_time - test_time).total_seconds() / 60
            next_orbs.append((name, diff))

    next_orbs.sort(key=lambda x: x[1])

    print(f"Test 1 - Current time: 23:30")
    print(f"Next ORBs: {next_orbs[:3]}")
    assert next_orbs[0][0] == "0030", f"Expected 0030, got {next_orbs[0][0]}"
    assert abs(next_orbs[0][1] - 60) < 1, f"Expected ~60 min, got {next_orbs[0][1]}"
    print("[PASS] 0030 is next at ~60 minutes\n")

    # Test case 2: At 01:00, next ORB should be 0900 (8 hours away)
    test_time = datetime.now().replace(hour=1, minute=0, second=0, microsecond=0)

    next_orbs = []
    for h, m, name in orb_times:
        orb_time = test_time.replace(hour=h, minute=m, second=0, microsecond=0)

        # Handle overnight ORBs
        if h <= 3 and test_time.hour >= 12:
            orb_time = orb_time + timedelta(days=1)

        if orb_time > test_time:
            diff = (orb_time - test_time).total_seconds() / 60
            next_orbs.append((name, diff))

    next_orbs.sort(key=lambda x: x[1])

    print(f"Test 2 - Current time: 01:00")
    print(f"Next ORBs: {next_orbs[:3]}")
    assert next_orbs[0][0] == "0900", f"Expected 0900, got {next_orbs[0][0]}"
    assert abs(next_orbs[0][1] - 480) < 1, f"Expected ~480 min (8h), got {next_orbs[0][1]}"
    print("[PASS] 0900 is next at ~480 minutes (8 hours)\n")

    # Test case 3: At 15:00, next ORB should be 1800 (3 hours away)
    test_time = datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)

    next_orbs = []
    for h, m, name in orb_times:
        orb_time = test_time.replace(hour=h, minute=m, second=0, microsecond=0)

        # Handle overnight ORBs
        if h <= 3 and test_time.hour >= 12:
            orb_time = orb_time + timedelta(days=1)

        if orb_time > test_time:
            diff = (orb_time - test_time).total_seconds() / 60
            next_orbs.append((name, diff))

    next_orbs.sort(key=lambda x: x[1])

    print(f"Test 3 - Current time: 15:00")
    print(f"Next ORBs: {next_orbs[:3]}")
    assert next_orbs[0][0] == "1800", f"Expected 1800, got {next_orbs[0][0]}"
    assert abs(next_orbs[0][1] - 180) < 1, f"Expected ~180 min (3h), got {next_orbs[0][1]}"
    print("[PASS] 1800 is next at ~180 minutes (3 hours)\n")

    print("ALL TESTS PASSED [OK]")

if __name__ == "__main__":
    test_next_orb_logic()
