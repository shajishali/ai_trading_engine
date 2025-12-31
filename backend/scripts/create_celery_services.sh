#!/bin/bash
# Script to create systemd service files for Celery
# Run this script on your production server

set -e

echo "============================================================"
echo "Creating Celery Systemd Services"
echo "============================================================"

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Get current user
CURRENT_USER=$(whoami)
CURRENT_GROUP=$(id -gn)

# Find virtual environment
if [ -d "$PROJECT_DIR/venv" ]; then
    VENV_PATH="$PROJECT_DIR/venv"
elif [ -d "$PROJECT_DIR/env" ]; then
    VENV_PATH="$PROJECT_DIR/env"
elif [ -d "$PROJECT_DIR/.venv" ]; then
    VENV_PATH="$PROJECT_DIR/.venv"
else
    echo "ERROR: Virtual environment not found!"
    echo "Please create a virtual environment first."
    exit 1
fi

CELERY_BIN="$VENV_PATH/bin/celery"

echo "Project Directory: $PROJECT_DIR"
echo "Virtual Environment: $VENV_PATH"
echo "User: $CURRENT_USER"
echo "Group: $CURRENT_GROUP"
echo ""

# Verify Celery is installed
if [ ! -f "$CELERY_BIN" ]; then
    echo "ERROR: Celery not found at $CELERY_BIN"
    echo "Please install Celery: pip install celery"
    exit 1
fi

# Create Celery Worker service
echo "Creating Celery Worker service..."
sudo tee /etc/systemd/system/ai-trading-celery-worker.service > /dev/null <<EOF
[Unit]
Description=AI Trading Engine Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$PROJECT_DIR
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=$VENV_PATH/bin"
ExecStart=$CELERY_BIN -A ai_trading_engine worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create Celery Beat service
echo "Creating Celery Beat service..."
sudo tee /etc/systemd/system/ai-trading-celery-beat.service > /dev/null <<EOF
[Unit]
Description=AI Trading Engine Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_GROUP
WorkingDirectory=$PROJECT_DIR
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=$VENV_PATH/bin"
ExecStart=$CELERY_BIN -A ai_trading_engine beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "Service files created successfully!"
echo ""
echo "Next steps:"
echo "1. Reload systemd: sudo systemctl daemon-reload"
echo "2. Start services:"
echo "   sudo systemctl start ai-trading-celery-worker"
echo "   sudo systemctl start ai-trading-celery-beat"
echo "3. Enable auto-start:"
echo "   sudo systemctl enable ai-trading-celery-worker"
echo "   sudo systemctl enable ai-trading-celery-beat"
echo "4. Check status:"
echo "   sudo systemctl status ai-trading-celery-worker"
echo "   sudo systemctl status ai-trading-celery-beat"
echo ""

