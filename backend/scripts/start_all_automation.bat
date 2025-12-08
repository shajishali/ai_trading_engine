@echo off
title AI Trading Engine - All Automation
color 0B

cls
echo.
echo ================================================================
echo          AI TRADING ENGINE - ALL AUTOMATION
echo ================================================================
echo.
echo Starting services in optimized order:
echo.
echo   [1] Django Server - Web interface (starts first)
echo   [2] Wait for server to be ready
echo   [3] Open browser with existing data
echo   [4] Start background tasks (non-blocking):
echo       - Signal Generation
echo       - Update Coins
echo       - Update News Live
echo.
echo Each service will run in its own terminal window.
echo Keep all windows open for the application to work.
echo.
echo ================================================================
echo.

cd /d "%~dp0"

echo Starting services now...
echo.

REM Step 1: Start Django Server FIRST
echo [1/5] Starting Django Server...
start "Django Server" cmd /k "cd /d %~dp0\.. && python manage.py runserver 0.0.0.0:8000"
echo     Waiting for server to initialize...
timeout /t 5 /nobreak > nul

REM Step 2: Wait for server to be ready (check if port 8000 is listening)
echo [2/5] Checking if server is ready...
:check_server
netstat -an | find "0.0.0.0:8000" | find "LISTENING" > nul
if %errorlevel% neq 0 (
    echo     Server not ready yet, waiting 2 more seconds...
    timeout /t 2 /nobreak > nul
    goto check_server
)
echo     Server is ready!

REM Step 3: Wait a bit more to ensure server is fully initialized
echo [3/5] Ensuring server is fully initialized...
timeout /t 3 /nobreak > nul

REM Step 4: Open browser with existing data
echo [4/5] Opening web browser with existing data...
start http://localhost:8000
echo     Browser opened! UI should load with existing data.
timeout /t 2 /nobreak > nul

REM Step 5: Start background tasks (these won't block the UI)
echo [5/5] Starting background tasks...
echo.
echo     Starting Signal Generation (runs in background)...
start "Signal Generation" cmd /k "cd /d %~dp0\.. && python scripts\run_signal_generation.py"
timeout /t 1 /nobreak > nul

echo     Starting Update Coins (runs in background)...
start "Update Coins" cmd /k "cd /d %~dp0\.. && python scripts\update_all_coins.py"
timeout /t 1 /nobreak > nul

echo     Starting Update News Live (runs in background)...
start "Update News Live" cmd /k "cd /d %~dp0\.. && python scripts\update_news_live.py"
timeout /t 1 /nobreak > nul

echo.
echo All services started!
echo.

cls
echo.
echo ================================================================
echo              ✅ ALL SERVICES STARTED SUCCESSFULLY
echo ================================================================
echo.
echo 🌐 Django Server      - http://localhost:8000
echo     ^(Started first - UI available with existing data^)
echo.
echo 📈 Background Tasks:
echo     - Signal Generation  - Generating trading signals
echo     - Update Coins       - Updating coin data in database
echo     - Update News Live   - Continuously updating cryptocurrency news
echo.
echo ================================================================
echo                     IMPORTANT NOTES
echo ================================================================
echo.
echo Services are running in 4 separate windows:
echo.
echo   1. "Django Server" - Web interface (started first)
echo   2. "Signal Generation" - Signal generation process (background)
echo   3. "Update Coins" - Database update process (background)
echo   4. "Update News Live" - Live news collection (background)
echo.
echo ✅ Server started first - UI should work immediately with old data
echo ✅ Background tasks won't interrupt the UI
echo ✅ New signals will appear after tasks complete
echo.
echo ⚠️  Keep ALL FOUR windows open!
echo.
echo To stop services:
echo   - Close the respective windows
echo   - Or use stop_all_automation.bat
echo.
echo ================================================================
echo.
echo This window will close in 5 seconds...
timeout /t 5 /nobreak > nul

