@echo off
echo ========================================
echo Step 2: MySQL Database and User Setup
echo ========================================
echo.
echo This script will create the database and user for AI Trading Engine.
echo You will be prompted for:
echo   1. MySQL root password
echo   2. Password for trading_user account
echo.
pause

echo.
echo Creating database and user...
echo.

mysql -u root -p < mysql_setup_step2.sql

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo Step 2 completed successfully!
    echo ========================================
    echo.
    echo Database: ai_trading_engine
    echo User: trading_user
    echo Host: localhost
    echo.
    echo IMPORTANT: Save the trading_user password securely!
    echo You will need it for Step 5 (Environment Variables)
) else (
    echo.
    echo ========================================
    echo Error occurred during setup!
    echo ========================================
    echo Please check the error messages above.
)

pause






