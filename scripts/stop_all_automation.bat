@echo off
title Stop All Automation Services
color 0C

echo.
echo ================================================================
echo          STOPPING ALL AUTOMATION SERVICES
echo ================================================================
echo.
echo This will stop all services:
echo   - Django Server
echo   - Signal Generation
echo   - Update Coins
echo   - Update News Live
echo.

REM Stop Django Server
echo Stopping Django Server...
taskkill /FI "WINDOWTITLE eq Django Server*" /T /F 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     Django Server stopped
) else (
    echo     Django Server not found (may already be stopped)
)

REM Stop Signal Generation
echo Stopping Signal Generation...
taskkill /FI "WINDOWTITLE eq Signal Generation*" /T /F 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     Signal Generation stopped
) else (
    echo     Signal Generation not found (may already be stopped)
)

REM Stop Update Coins
echo Stopping Update Coins...
taskkill /FI "WINDOWTITLE eq Update Coins*" /T /F 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     Update Coins stopped
) else (
    echo     Update Coins not found (may already be stopped)
)

REM Stop Update News Live
echo Stopping Update News Live...
taskkill /FI "WINDOWTITLE eq Update News Live*" /T /F 2>nul
if %ERRORLEVEL% EQU 0 (
    echo     Update News Live stopped
) else (
    echo     Update News Live not found (may already be stopped)
)

REM Also kill by process name (if windows are closed but processes remain)
taskkill /IM python.exe /FI "WINDOWTITLE eq Django*" /F 2>nul
taskkill /IM python.exe /FI "WINDOWTITLE eq Signal*" /F 2>nul
taskkill /IM python.exe /FI "WINDOWTITLE eq Update Coins*" /F 2>nul
taskkill /IM python.exe /FI "WINDOWTITLE eq Update News*" /F 2>nul

echo.
echo ================================================================
echo              ✅ ALL SERVICES STOPPED
echo ================================================================
echo.
pause

