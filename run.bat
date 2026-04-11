@echo off
REM HITS Launcher for Windows

cd /d "%~dp0"

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or later from https://www.python.org/
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Install dependencies if needed
pip show PySide6 >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Launch HITS
echo Starting HITS...
python -m hits_ui.main

if errorlevel 1 (
    echo.
    echo An error occurred. Check the output above.
    pause
)
