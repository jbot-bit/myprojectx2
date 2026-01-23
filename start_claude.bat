@echo off
REM ========================================
REM MGC Trading Project - Claude Code Launcher
REM ========================================
REM This script ensures project integrity before starting Claude Code
REM It prevents drift by validating database/config synchronization

echo.
echo ====================================================================
echo    MGC GOLD TRADING PROJECT - CLAUDE CODE LAUNCHER
echo ====================================================================
echo.

REM Change to project directory
cd /d "%~dp0"

REM Display current directory
echo [1/5] Project Directory: %CD%
echo.

REM Activate virtual environment
echo [2/5] Activating Python virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment!
    echo Please ensure venv exists at: %CD%\venv
    pause
    exit /b 1
)
echo    ✓ Virtual environment activated
echo.

REM Run critical synchronization test
echo [3/5] Running critical sync test to prevent drift...
echo    (This validates database and config.py are synchronized)
echo.
python test_app_sync.py
if errorlevel 1 (
    echo.
    echo ====================================================================
    echo    CRITICAL ERROR: Synchronization test FAILED!
    echo ====================================================================
    echo    Your database and config.py are OUT OF SYNC.
    echo    This is DANGEROUS and could cause REAL MONEY LOSSES.
    echo.
    echo    DO NOT proceed until you fix the mismatch.
    echo    See error messages above for details.
    echo ====================================================================
    echo.
    pause
    exit /b 1
)
echo    ✓ All synchronization tests PASSED!
echo.

REM Show git status
echo [4/5] Git Status:
git status -sb
echo.

REM Display project reminders
echo [5/5] Project Context Loaded:
echo    - Database: gold.db
echo    - Instrument: MGC (Micro Gold Futures)
echo    - Primary ORBs: 09:00, 10:00, 11:00
echo    - Secondary ORBs: 18:00, 23:00, 00:30
echo    - Trading Day: 09:00 Brisbane → 09:00 Brisbane (UTC+10)
echo    - CRITICAL: Always run test_app_sync.py after changes!
echo.
echo ====================================================================
echo    READY TO START CLAUDE CODE
echo ====================================================================
echo    Key reminders for Claude:
echo    1. ALWAYS run test_app_sync.py after updating strategies/config
echo    2. Never update validated_setups without updating config.py
echo    3. All docs are in CLAUDE.md and PROJECT_STRUCTURE.md
echo    4. Database schema uses 09:00→09:00 trading days
echo.

REM Project is ready!
echo ====================================================================
echo    ✓ PROJECT VALIDATED AND READY!
echo ====================================================================
echo.
echo Your project is synchronized and safe to use.
echo Launching Claude Code with project context...
echo.
echo CLAUDE.md will be automatically loaded as project authority.
echo.
echo Press any key to launch Claude Code...
pause > nul
echo.
echo Starting Claude Code...
echo.

REM Launch Claude Code (it will auto-detect CLAUDE.md in the project root)
claude
