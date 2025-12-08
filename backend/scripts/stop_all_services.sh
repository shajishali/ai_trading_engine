#!/bin/bash
# Linux/Mac script to stop all services

echo "========================================"
echo "Stopping All Services"
echo "========================================"
echo

# Stop Celery Worker
echo "Stopping Celery Worker..."
pkill -f "celery.*worker" 2>/dev/null
echo "  Done"

# Stop Celery Beat
echo "Stopping Celery Beat..."
pkill -f "celery.*beat" 2>/dev/null
echo "  Done"

# Stop Django Server
echo "Stopping Django Server..."
pkill -f "manage.py.*runserver" 2>/dev/null
echo "  Done"

# Stop Redis (if running as process)
echo "Stopping Redis..."
pkill -f "redis-server" 2>/dev/null
echo "  Done"

echo
echo "========================================"
echo "All services stopped"
echo "========================================"
echo
echo "You can now run:"
echo "  python manage.py populate_all_coins_historical_data"
echo










