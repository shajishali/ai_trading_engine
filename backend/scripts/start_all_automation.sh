#!/bin/bash
# AI Trading Engine - All Automation (Linux/Ubuntu Production)
# Equivalent to start_all_automation.bat for Windows

clear
echo ""
echo "================================================================"
echo "          AI TRADING ENGINE - ALL AUTOMATION"
echo "================================================================"
echo ""
echo "Starting services in optimized order:"
echo ""
echo "  [1] Django Server - Web interface (starts first)"
echo "  [2] Wait for server to be ready"
echo "  [3] Start background tasks (non-blocking):"
echo "      - Signal Generation"
echo "      - Update Coins"
echo "      - Update News Live"
echo ""
echo "Each service will run in the background."
echo "Keep the terminal session active or use screen/tmux."
echo ""
echo "================================================================"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project directory
cd "$PROJECT_DIR"

echo "Starting services now..."
echo ""

# Step 1: Start Django Server FIRST
echo "[1/4] Starting Django Server..."
# For production, you can use gunicorn instead:
# nohup gunicorn --bind 0.0.0.0:8000 --workers 4 ai_trading_engine.wsgi:application > logs/django.log 2>&1 &
# For development/testing, use runserver:
nohup python manage.py runserver 0.0.0.0:8000 > logs/django.log 2>&1 &
DJANGO_PID=$!
echo "    Django Server started (PID: $DJANGO_PID)"
echo "    Waiting for server to initialize..."
sleep 5

# Step 2: Wait for server to be ready (check if port 8000 is listening)
echo "[2/4] Checking if server is ready..."
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if netstat -tuln 2>/dev/null | grep -q ":8000 " || ss -tuln 2>/dev/null | grep -q ":8000 "; then
        echo "    Server is ready!"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo "    Server not ready yet, waiting 2 more seconds... (attempt $ATTEMPT/$MAX_ATTEMPTS)"
    sleep 2
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo "    WARNING: Server may not be ready. Continuing anyway..."
fi

# Step 3: Wait a bit more to ensure server is fully initialized
echo "[3/4] Ensuring server is fully initialized..."
sleep 3

# Step 4: Start background tasks (these won't block the UI)
echo "[4/4] Starting background tasks..."
echo ""

echo "    Starting Signal Generation (runs in background)..."
nohup python scripts/run_signal_generation.py > logs/signal_generation.log 2>&1 &
SIGNAL_PID=$!
echo "    Signal Generation started (PID: $SIGNAL_PID)"
sleep 1

echo "    Starting Update Coins (runs in background)..."
nohup python scripts/update_all_coins.py > logs/update_coins.log 2>&1 &
COINS_PID=$!
echo "    Update Coins started (PID: $COINS_PID)"
sleep 1

echo "    Starting Update News Live (runs in background)..."
nohup python scripts/update_news_live.py > logs/update_news.log 2>&1 &
NEWS_PID=$!
echo "    Update News Live started (PID: $NEWS_PID)"
sleep 1

echo ""
echo "All services started!"
echo ""

# Create a PID file to track processes
mkdir -p logs
echo "$DJANGO_PID" > logs/django.pid
echo "$SIGNAL_PID" > logs/signal_generation.pid
echo "$COINS_PID" > logs/update_coins.pid
echo "$NEWS_PID" > logs/update_news.pid

clear
echo ""
echo "================================================================"
echo "              ✅ ALL SERVICES STARTED SUCCESSFULLY"
echo "================================================================"
echo ""
echo "🌐 Django Server      - http://0.0.0.0:8000"
echo "   (Started first - UI available with existing data)"
echo ""
echo "📈 Background Tasks:"
echo "   - Signal Generation  - Generating trading signals (PID: $SIGNAL_PID)"
echo "   - Update Coins       - Updating coin data in database (PID: $COINS_PID)"
echo "   - Update News Live   - Continuously updating cryptocurrency news (PID: $NEWS_PID)"
echo ""
echo "================================================================"
echo "                     IMPORTANT NOTES"
echo "================================================================"
echo ""
echo "Services are running in the background:"
echo ""
echo "   1. Django Server (PID: $DJANGO_PID)"
echo "   2. Signal Generation (PID: $SIGNAL_PID)"
echo "   3. Update Coins (PID: $COINS_PID)"
echo "   4. Update News Live (PID: $NEWS_PID)"
echo ""
echo "✅ Server started first - UI should work immediately with old data"
echo "✅ Background tasks won't interrupt the UI"
echo "✅ New signals will appear after tasks complete"
echo ""
echo "📝 Log files are in: $PROJECT_DIR/logs/"
echo "   - django.log"
echo "   - signal_generation.log"
echo "   - update_coins.log"
echo "   - update_news.log"
echo ""
echo "⚠️  To keep services running after closing terminal:"
echo "   - Use 'screen' or 'tmux' before running this script"
echo "   - Or use systemd services for production"
echo ""
echo "To stop services:"
echo "   - Use: ./stop_all_automation.sh"
echo "   - Or kill processes using PIDs in logs/*.pid files"
echo ""
echo "================================================================"
echo ""









