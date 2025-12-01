@echo off
chcp 65001 >nul
echo.
echo ========================================
echo Step 2: Create MySQL Database and User
echo ========================================
echo.
echo This will open MySQL command line.
echo.
echo You will need to:
echo   1. Enter your MySQL root password
echo   2. Copy/paste the SQL commands from the instructions
echo.
echo Press any key to open MySQL...
pause >nul

echo.
echo Opening MySQL. Enter your root password when prompted.
echo.
echo After logging in, run these commands:
echo.
echo CREATE DATABASE IF NOT EXISTS ai_trading_engine CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
echo CREATE USER IF NOT EXISTS 'trading_user'@'localhost' IDENTIFIED BY 'YOUR_PASSWORD_HERE';
echo GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';
echo FLUSH PRIVILEGES;
echo SELECT user, host FROM mysql.user WHERE user = 'trading_user';
echo SHOW DATABASES LIKE 'ai_trading_engine';
echo.
echo (Replace YOUR_PASSWORD_HERE with your chosen password)
echo.
echo Type EXIT; when done.
echo.
pause

mysql -u root -p

echo.
echo ========================================
echo If you saw success messages, Step 2 is complete!
echo ========================================
echo.
pause

