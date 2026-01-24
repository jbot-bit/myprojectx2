============================= test session starts =============================
platform win32 -- Python 3.10.9, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\sydne\OneDrive\myprojectx2_cleanpush
configfile: pytest.ini
plugins: anyio-4.12.1
collected 145 items

tests\strategy_presentation\test_strategy_display_completeness.py ...... [  4%]
..................................                                       [ 27%]
tests\strategy_presentation\test_strategy_explanation_accuracy.py ..FF.. [ 31%]
...............................                                          [ 53%]
tests\test_ai_source_lock.py ...........                                 [ 60%]
tests\test_canonical_env.py ............s                                [ 69%]
tests\test_config_generator_returns_lists.py ....                        [ 72%]
tests\test_edge_approval.py ..........                                   [ 79%]
tests\test_edge_promotion.py FFFFFFF.                                    [ 84%]
tests\test_multi_setup_orb_detection.py ...                              [ 86%]
tests\test_no_hardcoded_db_paths.py F.FF                                 [ 89%]
tests\test_no_silent_overwrite.py ...                                    [ 91%]
tests\test_orb_temporal_consistency.py .                                 [ 92%]
tests\unit\test_config_generator.py FFFF.FF.FFF                          [100%]

================================== FAILURES ===================================
_ TestORBFilterExplanationAccuracy.test_0030_filter_explanation_matches_config _

self = <tests.strategy_presentation.test_strategy_explanation_accuracy.TestORBFilterExplanationAccuracy object at 0x00000200708B3A60>
sample_orb_0030 = {'atr_20': 23.0, 'current_price': 2688.0, 'expected_avg_r': 0.254, 'expected_tier': 'S', ...}

    def test_0030_filter_explanation_matches_config(self, sample_orb_0030):
        """0030 ORB: Filter threshold should match config (0.112)."""
        orb = sample_orb_0030
    
        # Config should have 0.112 filter for 0030
>       assert config.MGC_ORB_SIZE_FILTERS.get("0030") == 0.112, "Config mismatch!"
E       AssertionError: Config mismatch!
E       assert [0.112] == 0.112
E        +  where [0.112] = <built-in method get of dict object at 0x0000020054CCEEC0>('0030')
E        +    where <built-in method get of dict object at 0x0000020054CCEEC0> = {'0030': [0.112], '0900': [None], '1000': [None, None], '1100': [None], ...}.get
E        +      where {'0030': [0.112], '0900': [None], '1000': [None, None], '1100': [None], ...} = config.MGC_ORB_SIZE_FILTERS

tests\strategy_presentation\test_strategy_explanation_accuracy.py:58: AssertionError
_____ TestORBFilterExplanationAccuracy.test_day_orb_no_filter_explanation _____

self = <tests.strategy_presentation.test_strategy_explanation_accuracy.TestORBFilterExplanationAccuracy object at 0x00000200708B3D90>
sample_orb_1000 = {'atr_20': 16.0, 'current_price': 2688.0, 'expected_avg_r': 0.378, 'expected_tier': 'S+', ...}

    def test_day_orb_no_filter_explanation(self, sample_orb_1000):
        """Day ORBs (0900, 1000, 1100): Should not mention filters."""
        orb = sample_orb_1000
    
        # 1000 should have NO filter
>       assert config.MGC_ORB_SIZE_FILTERS.get("1000") is None, "1000 should have no filter!"
E       AssertionError: 1000 should have no filter!
E       assert [None, None] is None
E        +  where [None, None] = <built-in method get of dict object at 0x0000020054CCEEC0>('1000')
E        +    where <built-in method get of dict object at 0x0000020054CCEEC0> = {'0030': [0.112], '0900': [None], '1000': [None, None], '1100': [None], ...}.get
E        +      where {'0030': [0.112], '0900': [None], '1000': [None, None], '1100': [None], ...} = config.MGC_ORB_SIZE_FILTERS

tests\strategy_presentation\test_strategy_explanation_accuracy.py:69: AssertionError
____________________________ test_create_candidate ____________________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_create_candidate0/test_edge.db')

    def test_create_candidate(mock_db_connection):
        """Test creating an edge candidate."""
        candidate_id = create_edge_candidate(
            name="Test 1000 ORB Tight",
            instrument="MGC",
            hypothesis_text="1000 ORB with tight filter should have high WR",
            filter_spec={
                "orb_size_filter": 0.05,
                "sl_mode": "HALF"
            },
            test_config={
                "test_window_start": "2024-01-01",
                "test_window_end": "2025-12-31",
                "walk_forward_windows": 4
            },
            metrics={
                "orb_time": "1000",
                "rr": 8.0,
                "win_rate": 33.5,
                "avg_r": 0.342,
                "annual_trades": 260,
                "tier": "S+"
            },
            slippage_assumptions={
                "slippage_ticks": 2,
                "commission_per_contract": 2.50
            },
            code_version="abc123",
            data_version="v1",
            actor="TestUser"
        )
    
>       assert candidate_id == 1
E       assert 50 == 1

tests\test_edge_promotion.py:157: AssertionError
___________________________ test_approve_candidate ____________________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_approve_candidate0/test_edge.db')

    def test_approve_candidate(mock_db_connection):
        """Test approving a candidate."""
        # Create candidate
        candidate_id = create_edge_candidate(
            name="Test 0900 ORB",
            instrument="MGC",
            hypothesis_text="0900 baseline",
            filter_spec={"orb_size_filter": None, "sl_mode": "FULL"},
            test_config={"test_window_start": "2024-01-01", "test_window_end": "2025-12-31"},
            metrics={
                "orb_time": "0900",
                "rr": 2.0,
                "win_rate": 63.3,
                "avg_r": 0.266,
                "annual_trades": 300,
                "tier": "S"
            },
            slippage_assumptions={"slippage_ticks": 2, "commission_per_contract": 2.50},
            code_version="abc123",
            data_version="v1",
            actor="TestUser"
        )
    
        # Approve it
>       approve_edge_candidate(candidate_id, "Josh")

tests\test_edge_promotion.py:189: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 51, approver = 'Josh'

    def approve_edge_candidate(candidate_id: int, approver: str) -> None:
        """
        Approve an edge candidate by setting status='APPROVED', approved_at, and approved_by.
    
        This function uses a write-capable database connection to update the edge_candidates table.
    
        Args:
            candidate_id: ID of the candidate to approve
            approver: Name/identifier of the person approving (e.g., "Josh")
    
        Raises:
            ValueError: If candidate doesn't exist, is already approved, or other validation errors
            RuntimeError: If database update fails
        """
        from cloud_mode import get_database_connection
        import logging
    
        logger = logging.getLogger(__name__)
    
        # Get write-capable connection
        conn = get_database_connection(read_only=False)
    
        try:
            # Check if candidate exists
            result = conn.execute(
                "SELECT candidate_id, status FROM edge_candidates WHERE candidate_id = ?",
                [candidate_id]
            ).fetchone()
    
            if result is None:
>               raise ValueError(f"Edge candidate {candidate_id} not found")
E               ValueError: Edge candidate 51 not found

trading_app\edge_candidate_utils.py:149: ValueError
------------------------------ Captured log call ------------------------------
ERROR    edge_candidate_utils:edge_candidate_utils.py:172 Failed to approve candidate 51: Edge candidate 51 not found
_______________________ test_promote_approved_candidate _______________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_promote_approved_candidat0/test_edge.db')

    def test_promote_approved_candidate(mock_db_connection):
        """Test promoting an APPROVED candidate to validated_setups."""
        # Create candidate
        candidate_id = create_edge_candidate(
            name="Test 1100 ORB Safe",
            instrument="MGC",
            hypothesis_text="1100 safest MGC ORB",
            filter_spec={"orb_size_filter": 0.08, "sl_mode": "FULL"},
            test_config={"test_window_start": "2024-01-01", "test_window_end": "2025-12-31"},
            metrics={
                "orb_time": "1100",
                "rr": 2.0,
                "win_rate": 64.9,
                "avg_r": 0.299,
                "annual_trades": 280,
                "tier": "S+"
            },
            slippage_assumptions={"slippage_ticks": 2, "commission_per_contract": 2.50},
            code_version="def456",
            data_version="v1",
            actor="TestUser"
        )
    
        # Approve it
>       approve_edge_candidate(candidate_id, "Josh")

tests\test_edge_promotion.py:222: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 52, approver = 'Josh'

    def approve_edge_candidate(candidate_id: int, approver: str) -> None:
        """
        Approve an edge candidate by setting status='APPROVED', approved_at, and approved_by.
    
        This function uses a write-capable database connection to update the edge_candidates table.
    
        Args:
            candidate_id: ID of the candidate to approve
            approver: Name/identifier of the person approving (e.g., "Josh")
    
        Raises:
            ValueError: If candidate doesn't exist, is already approved, or other validation errors
            RuntimeError: If database update fails
        """
        from cloud_mode import get_database_connection
        import logging
    
        logger = logging.getLogger(__name__)
    
        # Get write-capable connection
        conn = get_database_connection(read_only=False)
    
        try:
            # Check if candidate exists
            result = conn.execute(
                "SELECT candidate_id, status FROM edge_candidates WHERE candidate_id = ?",
                [candidate_id]
            ).fetchone()
    
            if result is None:
>               raise ValueError(f"Edge candidate {candidate_id} not found")
E               ValueError: Edge candidate 52 not found

trading_app\edge_candidate_utils.py:149: ValueError
------------------------------ Captured log call ------------------------------
ERROR    edge_candidate_utils:edge_candidate_utils.py:172 Failed to approve candidate 52: Edge candidate 52 not found
_____________________ test_promote_fails_if_not_approved ______________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_promote_fails_if_not_appr0/test_edge.db')

    def test_promote_fails_if_not_approved(mock_db_connection):
        """Test that promotion fails if candidate is not APPROVED."""
        # Create candidate (status = DRAFT)
        candidate_id = create_edge_candidate(
            name="Test Draft",
            instrument="MGC",
            hypothesis_text="Test",
            filter_spec={"orb_size_filter": None, "sl_mode": "FULL"},
            test_config={"test_window_start": "2024-01-01", "test_window_end": "2025-12-31"},
            metrics={
                "orb_time": "0900",
                "rr": 2.0,
                "win_rate": 50.0,
                "avg_r": 0.0,
                "annual_trades": 100,
                "tier": "C"
            },
            slippage_assumptions={"slippage_ticks": 2, "commission_per_contract": 2.50},
            code_version="abc123",
            data_version="v1",
            actor="TestUser"
        )
    
        # Try to promote without approving
        with pytest.raises(ValueError, match="status is 'DRAFT', must be 'APPROVED'"):
>           promote_candidate_to_validated_setups(candidate_id, "Josh")

tests\test_edge_promotion.py:285: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 53, actor = 'Josh'

    def promote_candidate_to_validated_setups(candidate_id: int, actor: str) -> str:
        """
        Promote an APPROVED edge candidate to validated_setups table.
    
        This is the ONLY function that writes to validated_setups from edge_candidates.
    
        FAIL-CLOSED guarantees:
        1. Candidate must have status == 'APPROVED'
        2. Candidate must NOT already be promoted
        3. Manifest must be complete (all required fields present)
        4. No hardcoded placeholder values allowed
    
        Args:
            candidate_id: ID of the APPROVED candidate to promote
            actor: Name/identifier of person performing promotion
    
        Returns:
            setup_id: ID (VARCHAR) of the newly created validated_setups row (format: INSTRUMENT_ORBTIME_ID)
    
        Raises:
            ValueError: If candidate not found, not approved, already promoted, or incomplete manifest
            RuntimeError: If database operations fail
        """
        conn = get_database_connection(read_only=False)
    
        try:
            # 1) Fetch candidate row
>           result = conn.execute("""
                SELECT
                    candidate_id, name, instrument, hypothesis_text,
                    filter_spec_json, test_config_json, metrics_json, slippage_assumptions_json,
                    code_version, data_version, status, created_at_utc, approved_at, approved_by,
                    promoted_validated_setup_id, notes
                FROM edge_candidates
                WHERE candidate_id = ?
            """, [candidate_id]).fetchone()
E           _duckdb.BinderException: Binder Error: Referenced column "promoted_validated_setup_id" not found in FROM clause!
E           Candidate bindings: "created_at_utc", "approved_at", "data_version", "hypothesis_text", "candidate_id"
E           
E           LINE 6:                 promoted_validated_setup_id, notes
E                                   ^

trading_app\edge_pipeline.py:183: BinderException
------------------------------ Captured log call ------------------------------
ERROR    edge_pipeline:edge_pipeline.py:297 Failed to promote candidate 53: Binder Error: Referenced column "promoted_validated_setup_id" not found in FROM clause!
Candidate bindings: "created_at_utc", "approved_at", "data_version", "hypothesis_text", "candidate_id"

LINE 6:                 promoted_validated_setup_id, notes
                        ^
___________________ test_promote_fails_if_already_promoted ____________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_promote_fails_if_already_0/test_edge.db')

    def test_promote_fails_if_already_promoted(mock_db_connection):
        """Test that promotion fails if candidate was already promoted."""
        # Create and approve candidate
        candidate_id = create_edge_candidate(
            name="Test Double Promote",
            instrument="MGC",
            hypothesis_text="Test",
            filter_spec={"orb_size_filter": None, "sl_mode": "FULL"},
            test_config={"test_window_start": "2024-01-01", "test_window_end": "2025-12-31"},
            metrics={
                "orb_time": "0900",
                "rr": 2.0,
                "win_rate": 50.0,
                "avg_r": 0.0,
                "annual_trades": 100,
                "tier": "C"
            },
            slippage_assumptions={"slippage_ticks": 2, "commission_per_contract": 2.50},
            code_version="abc123",
            data_version="v1",
            actor="TestUser"
        )
    
>       approve_edge_candidate(candidate_id, "Josh")

tests\test_edge_promotion.py:311: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 54, approver = 'Josh'

    def approve_edge_candidate(candidate_id: int, approver: str) -> None:
        """
        Approve an edge candidate by setting status='APPROVED', approved_at, and approved_by.
    
        This function uses a write-capable database connection to update the edge_candidates table.
    
        Args:
            candidate_id: ID of the candidate to approve
            approver: Name/identifier of the person approving (e.g., "Josh")
    
        Raises:
            ValueError: If candidate doesn't exist, is already approved, or other validation errors
            RuntimeError: If database update fails
        """
        from cloud_mode import get_database_connection
        import logging
    
        logger = logging.getLogger(__name__)
    
        # Get write-capable connection
        conn = get_database_connection(read_only=False)
    
        try:
            # Check if candidate exists
            result = conn.execute(
                "SELECT candidate_id, status FROM edge_candidates WHERE candidate_id = ?",
                [candidate_id]
            ).fetchone()
    
            if result is None:
>               raise ValueError(f"Edge candidate {candidate_id} not found")
E               ValueError: Edge candidate 54 not found

trading_app\edge_candidate_utils.py:149: ValueError
------------------------------ Captured log call ------------------------------
ERROR    edge_candidate_utils:edge_candidate_utils.py:172 Failed to approve candidate 54: Edge candidate 54 not found
________________ test_promote_fails_if_missing_required_fields ________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_promote_fails_if_missing_0/test_edge.db')

    def test_promote_fails_if_missing_required_fields(mock_db_connection):
        """Test that promotion fails if required manifest fields are missing (FAIL-CLOSED)."""
        import duckdb
    
        conn = duckdb.connect(str(mock_db_connection), read_only=False)
    
        # Manually insert a candidate with incomplete metrics_json (missing 'rr')
        conn.execute("""
            INSERT INTO edge_candidates (
                candidate_id, name, instrument, hypothesis_text,
                filter_spec_json, test_config_json, metrics_json, slippage_assumptions_json,
                code_version, data_version, status, approved_by
            ) VALUES (
                999, 'Incomplete', 'MGC', 'Test incomplete',
                '{"orb_size_filter": null, "sl_mode": "FULL"}'::JSON,
                '{"test_window_start": "2024-01-01", "test_window_end": "2025-12-31"}'::JSON,
                '{"orb_time": "0900", "win_rate": 50.0, "avg_r": 0.0, "annual_trades": 100, "tier": "C"}'::JSON,
                '{"slippage_ticks": 2}'::JSON,
                'abc123', 'v1', 'APPROVED', 'Josh'
            )
        """)
    
        conn.commit()
        conn.close()
    
        # Try to promote - should fail due to missing 'rr' in metrics_json
        with pytest.raises(ValueError, match="missing required fields.*metrics_json.rr"):
>           promote_candidate_to_validated_setups(999, "Josh")

tests\test_edge_promotion.py:349: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 999, actor = 'Josh'

    def promote_candidate_to_validated_setups(candidate_id: int, actor: str) -> str:
        """
        Promote an APPROVED edge candidate to validated_setups table.
    
        This is the ONLY function that writes to validated_setups from edge_candidates.
    
        FAIL-CLOSED guarantees:
        1. Candidate must have status == 'APPROVED'
        2. Candidate must NOT already be promoted
        3. Manifest must be complete (all required fields present)
        4. No hardcoded placeholder values allowed
    
        Args:
            candidate_id: ID of the APPROVED candidate to promote
            actor: Name/identifier of person performing promotion
    
        Returns:
            setup_id: ID (VARCHAR) of the newly created validated_setups row (format: INSTRUMENT_ORBTIME_ID)
    
        Raises:
            ValueError: If candidate not found, not approved, already promoted, or incomplete manifest
            RuntimeError: If database operations fail
        """
        conn = get_database_connection(read_only=False)
    
        try:
            # 1) Fetch candidate row
>           result = conn.execute("""
                SELECT
                    candidate_id, name, instrument, hypothesis_text,
                    filter_spec_json, test_config_json, metrics_json, slippage_assumptions_json,
                    code_version, data_version, status, created_at_utc, approved_at, approved_by,
                    promoted_validated_setup_id, notes
                FROM edge_candidates
                WHERE candidate_id = ?
            """, [candidate_id]).fetchone()
E           _duckdb.BinderException: Binder Error: Referenced column "promoted_validated_setup_id" not found in FROM clause!
E           Candidate bindings: "created_at_utc", "approved_at", "data_version", "hypothesis_text", "candidate_id"
E           
E           LINE 6:                 promoted_validated_setup_id, notes
E                                   ^

trading_app\edge_pipeline.py:183: BinderException
------------------------------ Captured log call ------------------------------
ERROR    edge_pipeline:edge_pipeline.py:297 Failed to promote candidate 999: Binder Error: Referenced column "promoted_validated_setup_id" not found in FROM clause!
Candidate bindings: "created_at_utc", "approved_at", "data_version", "hypothesis_text", "candidate_id"

LINE 6:                 promoted_validated_setup_id, notes
                        ^
_________________ test_no_hardcoded_placeholders_in_promotion _________________

mock_db_connection = WindowsPath('C:/Users/sydne/AppData/Local/Temp/pytest-of-Josh/pytest-6/test_no_hardcoded_placeholders0/test_edge.db')

    def test_no_hardcoded_placeholders_in_promotion(mock_db_connection):
        """
        Test that promotion extracts ALL values from candidate JSON fields.
    
        This test verifies NO hardcoded placeholder values are used.
        """
        # Create candidate with UNIQUE values to ensure they're extracted, not hardcoded
        candidate_id = create_edge_candidate(
            name="Unique Values Test",
            instrument="NQ",  # Different instrument
            hypothesis_text="Testing value extraction",
            filter_spec={"orb_size_filter": 0.123, "sl_mode": "CUSTOM"},  # Unique values
            test_config={"test_window_start": "2023-06-15", "test_window_end": "2024-08-20"},
            metrics={
                "orb_time": "1800",  # Unique ORB time
                "rr": 7.5,  # Unique RR
                "win_rate": 72.8,  # Unique WR
                "avg_r": 0.555,  # Unique avg_r
                "annual_trades": 175,  # Unique count
                "tier": "A"  # Unique tier
            },
            slippage_assumptions={"slippage_ticks": 5, "commission_per_contract": 3.75},
            code_version="unique_hash_789",
            data_version="v99",
            actor="TestUser"
        )
    
>       approve_edge_candidate(candidate_id, "Josh")

tests\test_edge_promotion.py:379: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

candidate_id = 55, approver = 'Josh'

    def approve_edge_candidate(candidate_id: int, approver: str) -> None:
        """
        Approve an edge candidate by setting status='APPROVED', approved_at, and approved_by.
    
        This function uses a write-capable database connection to update the edge_candidates table.
    
        Args:
            candidate_id: ID of the candidate to approve
            approver: Name/identifier of the person approving (e.g., "Josh")
    
        Raises:
            ValueError: If candidate doesn't exist, is already approved, or other validation errors
            RuntimeError: If database update fails
        """
        from cloud_mode import get_database_connection
        import logging
    
        logger = logging.getLogger(__name__)
    
        # Get write-capable connection
        conn = get_database_connection(read_only=False)
    
        try:
            # Check if candidate exists
            result = conn.execute(
                "SELECT candidate_id, status FROM edge_candidates WHERE candidate_id = ?",
                [candidate_id]
            ).fetchone()
    
            if result is None:
>               raise ValueError(f"Edge candidate {candidate_id} not found")
E               ValueError: Edge candidate 55 not found

trading_app\edge_candidate_utils.py:149: ValueError
------------------------------ Captured log call ------------------------------
ERROR    edge_candidate_utils:edge_candidate_utils.py:172 Failed to approve candidate 55: Edge candidate 55 not found
__________________ test_no_hardcoded_db_paths_in_trading_app __________________

    def test_no_hardcoded_db_paths_in_trading_app():
        """Test that trading_app/ has no hardcoded database connections."""
        repo_root = Path(__file__).parent.parent
        trading_app_dir = repo_root / "trading_app"
    
        if not trading_app_dir.exists():
            pytest.skip("trading_app/ directory not found")
    
        violations = []
    
        # Scan all Python files in trading_app/
        for py_file in trading_app_dir.rglob("*.py"):
            file_violations = scan_file_for_hardcoded_connections(py_file, repo_root)
            violations.extend(file_violations)
    
        if violations:
            violation_report = "\n".join(
                f"  - {v['file']}:{v['line']} - {v['type']}"
                for v in violations
            )
>           pytest.fail(
                f"Found {len(violations)} hardcoded database connection(s) in trading_app/:\n"
                f"{violation_report}\n\n"
                f"All database connections must route through:\n"
                f"  from trading_app.cloud_mode import get_database_connection\n"
                f"  conn = get_database_connection()"
            )
E           Failed: Found 11 hardcoded database connection(s) in trading_app/:
E             - trading_app/data_loader.py:57 - duckdb.connect() call
E             - trading_app/data_loader.py:430 - duckdb.connect() call
E             - trading_app/data_loader.py:509 - duckdb.connect() call
E             - trading_app/ml_dashboard.py:111 - duckdb.connect() call
E             - trading_app/ml_dashboard.py:233 - duckdb.connect() call
E             - trading_app/ml_dashboard.py:322 - duckdb.connect() call
E             - trading_app/mobile_ui.py:562 - duckdb.connect() call
E             - trading_app/research_runner.py:80 - duckdb.connect() call
E             - trading_app/strategy_discovery.py:93 - duckdb.connect() call
E             - trading_app/utils.py:66 - duckdb.connect() call
E             - trading_app/utils.py:119 - duckdb.connect() call
E           
E           All database connections must route through:
E             from trading_app.cloud_mode import get_database_connection
E             conn = get_database_connection()

tests\test_no_hardcoded_db_paths.py:176: Failed
_________________ test_cloud_mode_is_sole_connection_provider _________________

    def test_cloud_mode_is_sole_connection_provider():
        """Test that cloud_mode.py exists and has connection functions."""
        repo_root = Path(__file__).parent.parent
        cloud_mode_file = repo_root / "trading_app" / "cloud_mode.py"
    
        assert cloud_mode_file.exists(), "Canonical connection module (cloud_mode.py) not found"
    
        # Check that it has the required functions
        with open(cloud_mode_file, 'r') as f:
>           content = f.read()

tests\test_no_hardcoded_db_paths.py:218: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self = <encodings.cp1252.IncrementalDecoder object at 0x000002007245A410>
input = b'"""\r\nCloud Mode Handler - Uses MotherDuck for Streamlit Cloud deployment\r\n"""\r\n\r\nimport os\r\nfrom pathlib i... Local mode active")\r\n        db_path = get_database_path()\r\n        print(f"[INFO] Database path: {db_path}")\r\n'
final = True

    def decode(self, input, final=False):
>       return codecs.charmap_decode(input,self.errors,decoding_table)[0]
E       UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 6372: character maps to <undefined>

..\..\AppData\Local\Programs\Python\Python310\lib\encodings\cp1252.py:23: UnicodeDecodeError
___________________ test_all_active_imports_use_cloud_mode ____________________

    def test_all_active_imports_use_cloud_mode():
        """Test that all active code imports from cloud_mode, not db_router."""
        repo_root = Path(__file__).parent.parent
    
        # Search for db_router imports in active code (not _archive)
        db_router_imports = []
    
        for py_file in repo_root.rglob("*.py"):
            rel_path = py_file.relative_to(repo_root)
            rel_path_str = str(rel_path).replace("\\", "/")
    
            # Skip archived code
            if rel_path_str.startswith("_archive/") or rel_path_str.startswith("_INVALID_SCRIPTS_ARCHIVE/"):
                continue
    
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
    
                if "from db_router import" in content or "import db_router" in content:
                    db_router_imports.append(rel_path_str)
    
            except (UnicodeDecodeError, PermissionError):
                pass
    
>       assert len(db_router_imports) == 0, (
            f"Found {len(db_router_imports)} file(s) importing from db_router (should use cloud_mode):\n" +
            "\n".join(f"  - {f}" for f in db_router_imports) +
            "\n\ndb_router.py is deprecated. Use cloud_mode.py instead."
        )
E       AssertionError: Found 1 file(s) importing from db_router (should use cloud_mode):
E           - tests/test_no_hardcoded_db_paths.py
E         
E         db_router.py is deprecated. Use cloud_mode.py instead.
E       assert 1 == 0
E        +  where 1 = len(['tests/test_no_hardcoded_db_paths.py'])

tests\test_no_hardcoded_db_paths.py:261: AssertionError
______________ TestConfigLoading.test_mgc_configs_load_correctly ______________

self = <test_config_generator.TestConfigLoading object at 0x000002007238E260>

    def test_mgc_configs_load_correctly(self):
        """MGC configs should load all 6 ORBs with correct values."""
        configs, filters = load_instrument_configs('MGC')
    
        # Should have 6 ORB configs
        assert len(configs) == 6
    
        # Check specific ORB configs (CROWN JEWELS)
>       assert configs['1000']['rr'] == 8.0
E       TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:38: TypeError
______________ TestConfigLoading.test_mgc_filters_load_correctly ______________

self = <test_config_generator.TestConfigLoading object at 0x000002007238C790>

    def test_mgc_filters_load_correctly(self):
        """MGC filters should match database values."""
        configs, filters = load_instrument_configs('MGC')
    
        # Check filter values
>       assert filters['0900'] is None  # No filter
E       assert [None] is None

tests\unit\test_config_generator.py:52: AssertionError
___________________ TestConfigLoading.test_nq_configs_load ____________________

self = <test_config_generator.TestConfigLoading object at 0x000002007238F370>

    def test_nq_configs_load(self):
        """NQ configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('NQ')
    
        # Should have 5 ORB configs
        assert len(configs) == 5
    
        # All NQ ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config in configs.items():
>           assert config['rr'] == 1.0
E           TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:66: TypeError
___________________ TestConfigLoading.test_mpl_configs_load ___________________

self = <test_config_generator.TestConfigLoading object at 0x000002007238F8B0>

    def test_mpl_configs_load(self):
        """MPL configs should load (even though not suitable for trading)."""
        configs, filters = load_instrument_configs('MPL')
    
        # Should have 6 ORB configs
        assert len(configs) == 6
    
        # All MPL ORBs have RR=1.0 (not suitable for live trading)
        for orb_time, config in configs.items():
>           assert config['rr'] == 1.0
E           TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:77: TypeError
______________________ TestOrbLookup.test_get_orb_config ______________________

self = <test_config_generator.TestOrbLookup object at 0x000002007238E3B0>

    def test_get_orb_config(self):
        """get_orb_config should return specific ORB config."""
        config = get_orb_config('MGC', '1000')
    
        assert config is not None
>       assert config['rr'] == 8.0
E       TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:103: TypeError
___________________ TestOrbLookup.test_get_orb_size_filter ____________________

self = <test_config_generator.TestOrbLookup object at 0x000002007238E290>

    def test_get_orb_size_filter(self):
        """get_orb_size_filter should return specific filter value."""
        # ORB with filter
        filter_2300 = get_orb_size_filter('MGC', '2300')
>       assert filter_2300 == pytest.approx(0.155, abs=0.001)
E       assert [0.155] == 0.155 ± 0.001
E         
E         comparison failed
E         Obtained: [0.155]
E         Expected: 0.155 ± 0.001

tests\unit\test_config_generator.py:110: AssertionError
_________________ TestDatabaseSync.test_mgc_1000_crown_jewel __________________

self = <test_config_generator.TestDatabaseSync object at 0x000002007238FFD0>

    def test_mgc_1000_crown_jewel(self):
        """MGC 1000 ORB should be RR=8.0 FULL (CROWN JEWEL)."""
        config = get_orb_config('MGC', '1000')
        filter_val = get_orb_size_filter('MGC', '1000')
    
>       assert config['rr'] == 8.0
E       TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:133: TypeError
_________________ TestDatabaseSync.test_mgc_2300_best_overall _________________

self = <test_config_generator.TestDatabaseSync object at 0x000002007238DFF0>

    def test_mgc_2300_best_overall(self):
        """MGC 2300 ORB should be RR=1.5 HALF with filter (BEST OVERALL)."""
        config = get_orb_config('MGC', '2300')
        filter_val = get_orb_size_filter('MGC', '2300')
    
>       assert config['rr'] == 1.5
E       TypeError: list indices must be integers or slices, not str

tests\unit\test_config_generator.py:142: TypeError
____________ TestDatabaseSync.test_all_mgc_orbs_have_valid_configs ____________

self = <test_config_generator.TestDatabaseSync object at 0x000002007238F760>

    def test_all_mgc_orbs_have_valid_configs(self):
        """All 6 MGC ORBs should have valid configs."""
        expected_orbs = ['0900', '1000', '1100', '1800', '2300', '0030']
        configs, filters = load_instrument_configs('MGC')
    
        for orb_time in expected_orbs:
            assert orb_time in configs
            assert orb_time in filters
    
            config = configs[orb_time]
>           assert 'rr' in config
E           AssertionError: assert 'rr' in [{'rr': 6.0, 'sl_mode': 'FULL'}]

tests\unit\test_config_generator.py:156: AssertionError
============================== warnings summary ===============================
tests/test_orb_temporal_consistency.py::test_orb_consistency
  C:\Users\sydne\OneDrive\myprojectx2_cleanpush\venv\lib\site-packages\_pytest\python.py:170: PytestReturnNotNoneWarning: Test functions should return None, but tests/test_orb_temporal_consistency.py::test_orb_consistency returned <class 'bool'>.
  Did you mean to use `assert` instead of `return`?
  See https://docs.pytest.org/en/stable/how-to/assert.html#return-not-none for more information.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/strategy_presentation/test_strategy_explanation_accuracy.py::TestORBFilterExplanationAccuracy::test_0030_filter_explanation_matches_config
FAILED tests/strategy_presentation/test_strategy_explanation_accuracy.py::TestORBFilterExplanationAccuracy::test_day_orb_no_filter_explanation
FAILED tests/test_edge_promotion.py::test_create_candidate - assert 50 == 1
FAILED tests/test_edge_promotion.py::test_approve_candidate - ValueError: Edg...
FAILED tests/test_edge_promotion.py::test_promote_approved_candidate - ValueE...
FAILED tests/test_edge_promotion.py::test_promote_fails_if_not_approved - _du...
FAILED tests/test_edge_promotion.py::test_promote_fails_if_already_promoted
FAILED tests/test_edge_promotion.py::test_promote_fails_if_missing_required_fields
FAILED tests/test_edge_promotion.py::test_no_hardcoded_placeholders_in_promotion
FAILED tests/test_no_hardcoded_db_paths.py::test_no_hardcoded_db_paths_in_trading_app
FAILED tests/test_no_hardcoded_db_paths.py::test_cloud_mode_is_sole_connection_provider
FAILED tests/test_no_hardcoded_db_paths.py::test_all_active_imports_use_cloud_mode
FAILED tests/unit/test_config_generator.py::TestConfigLoading::test_mgc_configs_load_correctly
FAILED tests/unit/test_config_generator.py::TestConfigLoading::test_mgc_filters_load_correctly
FAILED tests/unit/test_config_generator.py::TestConfigLoading::test_nq_configs_load
FAILED tests/unit/test_config_generator.py::TestConfigLoading::test_mpl_configs_load
FAILED tests/unit/test_config_generator.py::TestOrbLookup::test_get_orb_config
FAILED tests/unit/test_config_generator.py::TestOrbLookup::test_get_orb_size_filter
FAILED tests/unit/test_config_generator.py::TestDatabaseSync::test_mgc_1000_crown_jewel
FAILED tests/unit/test_config_generator.py::TestDatabaseSync::test_mgc_2300_best_overall
FAILED tests/unit/test_config_generator.py::TestDatabaseSync::test_all_mgc_orbs_have_valid_configs
====== 21 failed, 123 passed, 1 skipped, 1 warning in 127.27s (0:02:07) =======
