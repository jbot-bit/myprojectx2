# Deprecated Files - DO NOT USE

**Date Archived**: 2026-01-20

## Why These Files Are Deprecated

### populate_validated_setups.py
**Risk**: DANGEROUS - Executes `DELETE FROM validated_setups` and rebuilds from hardcoded dict.

**Problems**:
- Overwrites entire production truth without audit trail
- Loses promoted_from_candidate_id links (breaks traceability)
- Bypasses approval workflow
- No validation against edge_candidates
- No test_app_sync.py enforcement

**Replacement**: Use `trading_app/edge_pipeline.py` with `promote_candidate_to_validated_setups()` for incremental, auditable promotions.

### validated_strategies.py
**Risk**: Hardcoded strategy dict bypasses the edge discovery lifecycle.

**Problems**:
- No connection to research validation (EDE)
- No candidate approval workflow
- Changes require code edits instead of data operations
- No audit trail

**Replacement**: Use research/ede/ for discovery → export → edge_candidates → approve → promote workflow.

---

## Migration Path

If you need to rebuild validated_setups from scratch (emergency only):

1. Export current validated_setups to CSV backup
2. Create edge_candidates rows for each strategy
3. Approve via edge_candidates_ui.py
4. Promote via edge_pipeline.py (wired into UI)
5. Run test_app_sync.py to verify

**Never use populate_validated_setups.py again.**
