@echo off
REM HITS Launcher for Windows - Web UI Mode

cd /d "%~dp0"

echo HITS - Hybrid Intel Trace System
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or later from https://www.python.org/
    pause
    exit /b 1
)

REM Check Node.js installation
where node >nul 2>&1
if errorlevel 1 (
    echo Error: Node.js is not installed or not in PATH
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Setting up virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo Installing Python dependencies...
    pip install -r requirements.txt -q
) else (
    call venv\Scripts\activate.bat
)

REM Build frontend if needed
if not exist "hits_web\dist\index.html" (
    echo Building frontend...
    cd hits_web
    call npm install
    call npm run build
    cd ..
)

REM Start server (prefer Node server mode)
set PORT=%HITS_PORT:8765%
echo Starting HITS web server on http://127.0.0.1:%PORT%...
echo Press Ctrl+C to stop
echo.
node bin\hits.js --port %PORT%

if errorlevel 1 (
    echo.
    echo An error occurred. Check the output above.
    pause
)
