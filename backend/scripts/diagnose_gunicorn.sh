#!/bin/bash

# Gunicorn Diagnostic Script
# This script helps diagnose why Gunicorn isn't starting or listening on port 8000

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Gunicorn Diagnostic Script ===${NC}\n"

# Get the backend directory
BACKEND_DIR="${1:-$(pwd)}"
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Directory $BACKEND_DIR does not exist${NC}"
    exit 1
fi

cd "$BACKEND_DIR"

echo -e "${BLUE}1. Checking systemd service status...${NC}"
if systemctl is-active --quiet gunicorn; then
    echo -e "${GREEN}✓ Gunicorn service is active${NC}"
else
    echo -e "${RED}✗ Gunicorn service is NOT active${NC}"
fi

if systemctl is-enabled --quiet gunicorn; then
    echo -e "${GREEN}✓ Gunicorn service is enabled${NC}"
else
    echo -e "${YELLOW}⚠ Gunicorn service is NOT enabled${NC}"
fi

echo -e "\n${BLUE}2. Checking systemd service status details...${NC}"
sudo systemctl status gunicorn --no-pager -l || true

echo -e "\n${BLUE}3. Checking systemd service logs (last 50 lines)...${NC}"
sudo journalctl -u gunicorn -n 50 --no-pager || true

echo -e "\n${BLUE}4. Checking if logs directory exists...${NC}"
if [ -d "logs" ]; then
    echo -e "${GREEN}✓ Logs directory exists${NC}"
    ls -la logs/ | head -10
else
    echo -e "${RED}✗ Logs directory does NOT exist${NC}"
    echo -e "${YELLOW}Creating logs directory...${NC}"
    mkdir -p logs
    chmod 755 logs
    echo -e "${GREEN}✓ Logs directory created${NC}"
fi

echo -e "\n${BLUE}5. Checking Gunicorn error log (if exists)...${NC}"
if [ -f "logs/gunicorn_error.log" ]; then
    echo -e "${YELLOW}Last 50 lines of gunicorn_error.log:${NC}"
    tail -50 logs/gunicorn_error.log
else
    echo -e "${YELLOW}⚠ gunicorn_error.log does not exist${NC}"
fi

echo -e "\n${BLUE}6. Checking if port 8000 is in use...${NC}"
if sudo ss -tlnp | grep -q ":8000"; then
    echo -e "${GREEN}✓ Port 8000 is listening${NC}"
    sudo ss -tlnp | grep ":8000"
else
    echo -e "${RED}✗ Port 8000 is NOT listening${NC}"
fi

echo -e "\n${BLUE}7. Checking for Gunicorn processes...${NC}"
if pgrep -f gunicorn > /dev/null; then
    echo -e "${GREEN}✓ Gunicorn processes found:${NC}"
    ps aux | grep gunicorn | grep -v grep
else
    echo -e "${RED}✗ No Gunicorn processes found${NC}"
fi

echo -e "\n${BLUE}8. Checking Python environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Virtual environment found${NC}"
    source venv/bin/activate
    echo "Python: $(which python)"
    echo "Python version: $(python --version)"
    echo "Gunicorn: $(which gunicorn || echo 'NOT FOUND')"
else
    echo -e "${YELLOW}⚠ Virtual environment not found in current directory${NC}"
    echo "Looking for venv in parent directories..."
    if [ -f "../venv/bin/activate" ]; then
        echo -e "${GREEN}✓ Found venv in parent directory${NC}"
        source ../venv/bin/activate
    else
        echo -e "${YELLOW}⚠ No venv found. Using system Python${NC}"
    fi
fi

echo -e "\n${BLUE}9. Checking Django settings...${NC}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ai_trading_engine.settings_production}"
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"

# Check if settings module can be imported
if python -c "import django; django.setup(); from django.conf import settings; print('Settings loaded successfully')" 2>&1; then
    echo -e "${GREEN}✓ Django settings can be imported${NC}"
else
    echo -e "${RED}✗ Django settings import failed${NC}"
    python -c "import django; django.setup(); from django.conf import settings" 2>&1 || true
fi

echo -e "\n${BLUE}10. Checking WSGI application...${NC}"
if python -c "from ai_trading_engine.wsgi import application; print('WSGI application loaded successfully')" 2>&1; then
    echo -e "${GREEN}✓ WSGI application can be imported${NC}"
else
    echo -e "${RED}✗ WSGI application import failed${NC}"
    python -c "from ai_trading_engine.wsgi import application" 2>&1 || true
fi

echo -e "\n${BLUE}11. Checking Gunicorn configuration file...${NC}"
if [ -f "gunicorn.conf.py" ]; then
    echo -e "${GREEN}✓ gunicorn.conf.py exists${NC}"
    # Check for common issues
    if grep -q "logs/gunicorn" gunicorn.conf.py; then
        echo -e "${GREEN}✓ Log paths configured${NC}"
    fi
    if grep -q "bind.*8000" gunicorn.conf.py; then
        echo -e "${GREEN}✓ Bind address configured${NC}"
    fi
else
    echo -e "${RED}✗ gunicorn.conf.py does NOT exist${NC}"
fi

echo -e "\n${BLUE}12. Testing Gunicorn start manually (dry-run)...${NC}"
echo -e "${YELLOW}Attempting to start Gunicorn in foreground to see errors...${NC}"
echo -e "${YELLOW}Press Ctrl+C after a few seconds to stop...${NC}\n"

# Try to start Gunicorn manually to see errors
timeout 5 gunicorn \
    --config gunicorn.conf.py \
    --check-config \
    ai_trading_engine.wsgi:application \
    2>&1 || echo -e "\n${YELLOW}Gunicorn check-config completed (errors above)${NC}"

echo -e "\n${BLUE}13. Checking systemd service file...${NC}"
if [ -f "/etc/systemd/system/gunicorn.service" ]; then
    echo -e "${GREEN}✓ Systemd service file exists${NC}"
    echo -e "${YELLOW}Service file contents:${NC}"
    cat /etc/systemd/system/gunicorn.service
else
    echo -e "${RED}✗ Systemd service file does NOT exist${NC}"
    echo -e "${YELLOW}Expected location: /etc/systemd/system/gunicorn.service${NC}"
fi

echo -e "\n${BLUE}14. Recommendations:${NC}"
echo -e "${YELLOW}If Gunicorn is not running, try:${NC}"
echo "  1. Check the error logs above"
echo "  2. Ensure logs directory exists: mkdir -p logs"
echo "  3. Test manually: gunicorn --config gunicorn.conf.py ai_trading_engine.wsgi:application"
echo "  4. Check systemd: sudo systemctl status gunicorn"
echo "  5. View logs: sudo journalctl -u gunicorn -f"
echo "  6. Restart service: sudo systemctl restart gunicorn"

echo -e "\n${BLUE}=== Diagnostic Complete ===${NC}"










