@echo off
REM ==========================================================================
REM  One-click test runner for Windows.
REM  Creates a virtual environment, installs dependencies, and runs pytest.
REM  Usage: double-click this file, or run `run_tests.bat` in CMD/PowerShell.
REM ==========================================================================

setlocal

REM Move to the folder this script lives in.
cd /d "%~dp0"

echo === Creating virtual environment (.venv) ===
python -m venv .venv
if errorlevel 1 (
    echo Failed to create venv. Is Python installed and on PATH?
    echo Try: py -3 -m venv .venv
    pause
    exit /b 1
)

echo === Installing dependencies ===
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency install failed.
    pause
    exit /b 1
)

echo === Running tests ===
python -m pytest
set TEST_RESULT=%errorlevel%

echo.
if "%TEST_RESULT%"=="0" (
    echo All tests passed.
) else (
    echo Tests failed. See output above.
)

pause
exit /b %TEST_RESULT%
