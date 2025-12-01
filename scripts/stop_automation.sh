#!/bin/bash
# Stop Automation System for Linux/Mac

echo "============================================================"
echo "Stopping Automation System..."
echo "============================================================"

# Stop Celery Beat
echo "Stopping Celery Beat..."
pkill -f "celery.*beat" && echo "Celery Beat stopped" || echo "Celery Beat was not running"

# Stop Celery Worker
echo "Stopping Celery Worker..."
pkill -f "celery.*worker" && echo "Celery Worker stopped" || echo "Celery Worker was not running"

# Note about Redis
echo ""
echo "Note: Redis Server is still running."
echo "To stop Redis, use: pkill redis-server"
echo ""

echo "============================================================"
echo "Automation system stopped!"
echo "============================================================"





















