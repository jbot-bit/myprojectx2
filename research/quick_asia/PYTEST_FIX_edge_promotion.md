# Test Fix Report: tests/test_edge_promotion.py

**Date**: 2026-01-21
**Task**: Fix or skip test_edge_promotion.py schema issues
**Status**: ✅ ALL TESTS SKIPPED WITH CLEAR REASON

---

## Summary

Skipped all 8 tests in `tests/test_edge_promotion.py` due to deprecated local-only workflow and schema mismatch with MotherDuck cloud database.

**Action Taken**: Added module-level `pytestmark` skip decorator

**Test Results**: 8/8 tests skipped (0 failures)

---

## Root Cause Analysis

### Schema Mismatch
- **Test Expectation**: edge_candidates table has `promoted_validated_setup_id` column
- **Actual MotherDuck Schema**: This column doesn't exist in cloud database
- **Error**: `BinderException: Referenced column "promoted_validated_setup_id" not found`

### Cloud Mode Conflict
- **Test Design**: Creates local mock database with test schema
- **Production Functions**: Use `get_database_connection()` which connects to MotherDuck in cloud mode
- **Result**: Mock patching doesn't work properly; functions connect to real cloud DB

### Deprecated Workflow
These tests were written for local-only workflow before MotherDuck migration. The edge promotion functions now use cloud-aware database connections that can't be properly mocked with the current test setup.

---

## Fix Applied

**File**: tests/test_edge_promotion.py

**Change**: Added module-level skip decorator

```python
# Skip all tests in this module if in cloud mode
CLOUD_MODE = os.getenv("CLOUD_MODE", "0").lower() in ["1", "true", "yes"]
FORCE_LOCAL = os.getenv("FORCE_LOCAL_DB", "0").lower() in ["1", "true", "yes"]

pytestmark = pytest.mark.skipif(
    CLOUD_MODE or not FORCE_LOCAL,
    reason="Edge promotion tests target deprecated local-only workflow. "
           "Functions now use cloud MotherDuck via get_database_connection(). "
           "Schema mismatch: test expects promoted_validated_setup_id column not in cloud schema. "
           "Run with FORCE_LOCAL_DB=1 to test local-only mode."
)
```

---

## Skip Conditions

Tests are skipped when:
1. **CLOUD_MODE=1** environment variable is set, OR
2. **FORCE_LOCAL_DB=1** is NOT set

Tests can be re-enabled by setting: `FORCE_LOCAL_DB=1`

---

## Tests Skipped (8 total)

1. `test_create_candidate` - Edge candidate creation
2. `test_approve_candidate` - Candidate approval workflow
3. `test_promote_approved_candidate` - Promotion to validated_setups
4. `test_promote_fails_if_not_approved` - Validation that DRAFT can't be promoted
5. `test_promote_fails_if_already_promoted` - Validation against double promotion
6. `test_promote_fails_if_missing_required_fields` - Fail-closed validation
7. `test_no_hardcoded_placeholders_in_promotion` - Value extraction validation
8. `test_extract_manifest_validates_all_fields` - Manifest validation

---

## Pytest Output

```
============================= test session starts =============================
platform win32 -- Python 3.10.9, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\sydne\OneDrive\myprojectx2_cleanpush
configfile: pytest.ini
plugins: anyio-4.12.1
collected 8 items

tests\test_edge_promotion.py ssssssss                                    [100%]

============================= 8 skipped in 0.08s ==============================
```

---

## Rationale per approve4.txt

Per approve4.txt instructions:
- "Prefer (1) skip if refactor touches production"
- "If skipping: must check for a reliable feature flag or cloud/local mode condition"

✅ **Reliable condition used**: CLOUD_MODE and FORCE_LOCAL_DB environment variables
✅ **Clear skip reason provided**: Explains schema mismatch and cloud mode conflict
✅ **Production logic unchanged**: Zero risk to production edge promotion functions
✅ **Path forward documented**: Tests can run with FORCE_LOCAL_DB=1

---

## Future Work

To restore these tests, one of the following is needed:
1. **Refactor tests** to work with cloud MotherDuck schema (remove promoted_validated_setup_id expectation)
2. **Use FORCE_LOCAL_DB=1** to test local-only mode
3. **Create cloud-specific tests** that work with actual MotherDuck schema
4. **Improve mocking** to properly intercept get_database_connection() in all modules

---

## Next Step

✅ **Task 2C Complete**: test_edge_promotion.py handled via skip with clear reason

**Next**: Task 2D - Fix or skip test_no_hardcoded_db_paths.py (3 failures expected)
