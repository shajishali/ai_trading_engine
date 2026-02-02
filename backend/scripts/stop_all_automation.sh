#!/bin/bash
# Stop All Automation Services (Linux/Ubuntu)
# Equivalent to stop_all_automation.bat for Windows

echo ""
echo "================================================================"
echo "          STOPPING ALL AUTOMATION SERVICES"
echo "================================================================"
echo ""
echo "This will stop all services:"
echo "  - Django Server"
echo "  - Signal Generation"
echo "  - Update Coins"
echo "  - Update News Live"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
LOGS_DIR="$PROJECT_DIR/logs"

# Function to stop a process by PID file
stop_process() {
    local service_name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null
            sleep 1
            # Force kill if still running
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid" 2>/dev/null
            fi
            echo "    $service_name stopped"
            rm -f "$pid_file"
        else
            echo "    $service_name not running (PID file exists but process not found)"
            rm -f "$pid_file"
        fi
    else
        echo "    $service_name PID file not found (may already be stopped)"
    fi
}

# Stop services using PID files
stop_process "Django Server" "$LOGS_DIR/django.pid"
stop_process "Signal Generation" "$LOGS_DIR/signal_generation.pid"
stop_process "Update Coins" "$LOGS_DIR/update_coins.pid"
stop_process "Update News Live" "$LOGS_DIR/update_news.pid"

# Also try to kill by process name (fallback method)
echo ""
echo "Checking for any remaining processes..."
pkill -f "manage.py runserver" 2>/dev/null && echo "    Stopped Django runserver processes"
pkill -f "run_signal_generation.py" 2>/dev/null && echo "    Stopped Signal Generation processes"
pkill -f "update_all_coins.py" 2>/dev/null && echo "    Stopped Update Coins processes"
pkill -f "update_news_live.py" 2>/dev/null && echo "    Stopped Update News Live processes"

echo ""
echo "================================================================"
echo "              ✅ ALL SERVICES STOPPED"
echo "================================================================"
echo ""










