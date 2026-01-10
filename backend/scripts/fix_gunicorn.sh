#!/bin/bash

# Quick Fix Script for Gunicorn Issues
# This script fixes common Gunicorn startup problems

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Gunicorn Quick Fix Script ===${NC}\n"

# Get the backend directory
BACKEND_DIR="${1:-$(pwd)}"
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}Error: Directory $BACKEND_DIR does not exist${NC}"
    exit 1
fi

cd "$BACKEND_DIR"

# Fix 1: Create logs directory if it doesn't exist
echo -e "${BLUE}1. Ensuring logs directory exists...${NC}"
if [ ! -d "logs" ]; then
    mkdir -p logs
    chmod 755 logs
    echo -e "${GREEN}✓ Created logs directory${NC}"
else
    echo -e "${GREEN}✓ Logs directory already exists${NC}"
fi

# Fix 2: Check and activate virtual environment
echo -e "\n${BLUE}2. Setting up Python environment...${NC}"
if [ -d "venv" ]; then
    source venv/bin/activate
    echo -e "${GREEN}✓ Activated virtual environment${NC}"
elif [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
    echo -e "${GREEN}✓ Activated virtual environment from parent directory${NC}"
else
    echo -e "${YELLOW}⚠ No virtual environment found, using system Python${NC}"
fi

# Fix 3: Verify Python syntax
echo -e "\n${BLUE}3. Checking Python syntax...${NC}"
if python -m py_compile apps/core/middleware.py 2>&1; then
    echo -e "${GREEN}✓ Middleware syntax is valid${NC}"
else
    echo -e "${RED}✗ Middleware has syntax errors${NC}"
    exit 1
fi

# Fix 4: Test Django settings import
echo -e "\n${BLUE}4. Testing Django configuration...${NC}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ai_trading_engine.settings_production}"

if python -c "import django; django.setup(); from django.conf import settings; print('OK')" 2>&1; then
    echo -e "${GREEN}✓ Django settings can be loaded${NC}"
else
    echo -e "${RED}✗ Django settings failed to load${NC}"
    echo -e "${YELLOW}Trying with default settings...${NC}"
    export DJANGO_SETTINGS_MODULE="ai_trading_engine.settings"
    if python -c "import django; django.setup(); from django.conf import settings; print('OK')" 2>&1; then
        echo -e "${GREEN}✓ Django default settings can be loaded${NC}"
        echo -e "${YELLOW}⚠ Using default settings instead of production settings${NC}"
    else
        echo -e "${RED}✗ Django settings import failed${NC}"
        exit 1
    fi
fi

# Fix 5: Test WSGI import
echo -e "\n${BLUE}5. Testing WSGI application...${NC}"
if python -c "from ai_trading_engine.wsgi import application; print('OK')" 2>&1; then
    echo -e "${GREEN}✓ WSGI application can be imported${NC}"
else
    echo -e "${RED}✗ WSGI application import failed${NC}"
    exit 1
fi

# Fix 6: Check Gunicorn configuration
echo -e "\n${BLUE}6. Checking Gunicorn configuration...${NC}"
if [ -f "gunicorn.conf.py" ]; then
    echo -e "${GREEN}✓ gunicorn.conf.py exists${NC}"
    
    # Test configuration
    if gunicorn --check-config --config gunicorn.conf.py ai_trading_engine.wsgi:application 2>&1; then
        echo -e "${GREEN}✓ Gunicorn configuration is valid${NC}"
    else
        echo -e "${YELLOW}⚠ Gunicorn configuration check had warnings${NC}"
    fi
else
    echo -e "${RED}✗ gunicorn.conf.py not found${NC}"
    exit 1
fi

# Fix 7: Stop any existing Gunicorn processes
echo -e "\n${BLUE}7. Stopping existing Gunicorn processes...${NC}"
if pgrep -f gunicorn > /dev/null; then
    echo -e "${YELLOW}Stopping existing Gunicorn processes...${NC}"
    pkill -f gunicorn || true
    sleep 2
    echo -e "${GREEN}✓ Stopped existing processes${NC}"
else
    echo -e "${GREEN}✓ No existing Gunicorn processes${NC}"
fi

# Fix 8: Restart systemd service
echo -e "\n${BLUE}8. Restarting Gunicorn service...${NC}"
if systemctl list-unit-files | grep -q gunicorn.service; then
    echo -e "${YELLOW}Restarting systemd service...${NC}"
    sudo systemctl daemon-reload
    sudo systemctl restart gunicorn
    
    sleep 3
    
    if systemctl is-active --quiet gunicorn; then
        echo -e "${GREEN}✓ Gunicorn service is now running${NC}"
    else
        echo -e "${RED}✗ Gunicorn service failed to start${NC}"
        echo -e "${YELLOW}Checking service status...${NC}"
        sudo systemctl status gunicorn --no-pager -l || true
        echo -e "\n${YELLOW}Recent service logs:${NC}"
        sudo journalctl -u gunicorn -n 30 --no-pager || true
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Gunicorn systemd service not found${NC}"
    echo -e "${YELLOW}You may need to create the service file${NC}"
fi

# Fix 9: Verify port is listening
echo -e "\n${BLUE}9. Verifying port 8000 is listening...${NC}"
sleep 2
if sudo ss -tlnp | grep -q ":8000"; then
    echo -e "${GREEN}✓ Port 8000 is now listening${NC}"
    sudo ss -tlnp | grep ":8000"
else
    echo -e "${RED}✗ Port 8000 is still not listening${NC}"
    echo -e "${YELLOW}Checking for errors...${NC}"
    if [ -f "logs/gunicorn_error.log" ]; then
        echo -e "${YELLOW}Last 20 lines of error log:${NC}"
        tail -20 logs/gunicorn_error.log
    fi
    exit 1
fi

# Fix 10: Test HTTP connection
echo -e "\n${BLUE}10. Testing HTTP connection...${NC}"
if curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8000 | grep -q "200\|301\|302\|403"; then
    echo -e "${GREEN}✓ HTTP connection successful${NC}"
    echo -e "${YELLOW}Response:${NC}"
    curl -H "Host: cryptai.it.com" http://127.0.0.1:8000 2>&1 | head -10
else
    echo -e "${YELLOW}⚠ HTTP connection test had issues (may be normal if site requires authentication)${NC}"
fi

echo -e "\n${GREEN}=== Quick Fix Complete ===${NC}"
echo -e "${BLUE}If issues persist, run: ./scripts/diagnose_gunicorn.sh${NC}"















