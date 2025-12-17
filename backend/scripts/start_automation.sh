#!/bin/bash
# Start Automation System for Linux/Mac

echo "============================================================"
echo "Starting Automation System..."
echo "============================================================"

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Project root is the parent of the scripts directory (the Django backend directory)
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Script directory : $SCRIPT_DIR"
echo "Project directory: $PROJECT_DIR"
echo ""

# Always run Celery from the Django project root so that the ai_trading_engine
# package is importable (fixes: 'The module ai_trading_engine was not found')
cd "$PROJECT_DIR"

# Check if Redis is already running
if pgrep -x "redis-server" > /dev/null; then
    echo "Redis Server is already running"
else
    echo "Starting Redis Server..."
    redis-server redis.conf &
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to start Redis Server"
        echo "Please ensure Redis is installed and redis.conf exists"
        exit 1
    fi
    echo "Waiting for Redis to start..."
    sleep 3
fi

# Check if Celery processes are already running
if pgrep -f "celery.*worker" > /dev/null; then
    echo "WARNING: Celery Worker may already be running"
fi

# Start Celery Worker
echo "Starting Celery Worker..."
celery -A ai_trading_engine worker --loglevel=info &
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start Celery Worker"
    exit 1
fi

# Wait a moment for worker to initialize
sleep 2

# Start Celery Beat
echo "Starting Celery Beat..."
celery -A ai_trading_engine beat --loglevel=info &
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to start Celery Beat"
    exit 1
fi

echo ""
echo "============================================================"
echo "Automation system started!"
echo "============================================================"
echo "- Redis: Running"
echo "- Celery Worker: Running"
echo "- Celery Beat: Running"
echo ""
echo "Note: Services are running in the background."
echo "To stop, use: ./stop_automation.sh"
echo "To check status, use: ./check_automation_health.py"
echo "============================================================"





















