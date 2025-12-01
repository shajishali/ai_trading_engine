@echo off
REM Windows batch script to stop all services

echo ========================================
echo Stopping All Services
echo ========================================
echo.

REM Stop Celery Worker
echo Stopping Celery Worker...
taskkill /F /FI "WINDOWTITLE eq Celery Worker*" 2>nul
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *celery*worker*" 2>nul
echo   Done

REM Stop Celery Beat
echo Stopping Celery Beat...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *celery*beat*" 2>nul
echo   Done

REM Stop Django Server
echo Stopping Django Server...
taskkill /F /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *runserver*" 2>nul
echo   Done

REM Stop Redis (if running as service, adjust as needed)
echo Stopping Redis...
taskkill /F /FI "IMAGENAME eq redis-server.exe" 2>nul
echo   Done

echo.
echo ========================================
echo All services stopped
echo ========================================
echo.
echo You can now run:
echo   python manage.py populate_all_coins_historical_data
echo.

pause










