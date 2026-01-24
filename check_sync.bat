@echo off
REM ========================================
REM Quick Sync Check - Run Anytime
REM ========================================
REM Use this to quickly verify database/config synchronization
REM without starting Claude Code

echo.
echo ====================================================================
echo    QUICK SYNCHRONIZATION CHECK
echo ====================================================================
echo.

cd /d "%~dp0"
call venv\Scripts\activate.bat

echo Running test_app_sync.py...
echo.
python test_app_sync.py

echo.
if errorlevel 1 (
    echo ❌ SYNC CHECK FAILED - Fix mismatches before proceeding!
) else (
    echo ✓ SYNC CHECK PASSED - Your project is synchronized!
)
echo.
pause
