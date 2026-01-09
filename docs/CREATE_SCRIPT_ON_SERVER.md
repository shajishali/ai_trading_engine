# Create Fix Script on Server

Run these commands on your server to create the fix script:

```bash
# Make sure you're in the backend directory
cd ~/trading-engine/backend

# Create the scripts directory if it doesn't exist
mkdir -p scripts

# Create the fix script
cat > scripts/fix_database_connection.sh << 'SCRIPT_END'
#!/bin/bash
# Database Connection Fix Script for Deployment
# Run this script on your server via PuTTY/SSH to diagnose and fix database issues

echo "=========================================="
echo "Database Connection Diagnostic & Fix Tool"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get project directory (adjust if needed)
PROJECT_DIR="${1:-$(pwd)}"
cd "$PROJECT_DIR" || exit 1

echo "Project directory: $PROJECT_DIR"
echo ""

# Step 1: Check if MySQL/MariaDB is running
echo "Step 1: Checking MySQL/MariaDB service..."
if systemctl is-active --quiet mysql || systemctl is-active --quiet mariadb; then
    echo -e "${GREEN}✓ MySQL/MariaDB service is running${NC}"
else
    echo -e "${RED}✗ MySQL/MariaDB service is NOT running${NC}"
    echo "Attempting to start MySQL/MariaDB..."
    sudo systemctl start mysql || sudo systemctl start mariadb
    sleep 2
    if systemctl is-active --quiet mysql || systemctl is-active --quiet mariadb; then
        echo -e "${GREEN}✓ MySQL/MariaDB started successfully${NC}"
    else
        echo -e "${RED}✗ Failed to start MySQL/MariaDB${NC}"
        echo "Please check MySQL/MariaDB installation and configuration"
        exit 1
    fi
fi
echo ""

# Step 2: Test database connection
echo "Step 2: Testing database connection..."
if [ -f ".env" ]; then
    source .env
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-trading_user}"
DB_NAME="${DB_NAME:-ai_trading_engine}"

echo "Database settings:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"
echo ""

# Test connection with mysql client
if command -v mysql &> /dev/null; then
    echo "Testing connection with mysql client..."
    if mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"${DB_PASSWORD}" -e "SELECT 1;" "$DB_NAME" &> /dev/null; then
        echo -e "${GREEN}✓ Database connection successful${NC}"
    else
        echo -e "${RED}✗ Database connection failed${NC}"
        echo "Error details:"
        mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"${DB_PASSWORD}" -e "SELECT 1;" "$DB_NAME" 2>&1 | head -5
        echo ""
        echo "Common fixes:"
        echo "1. Check if DB_PASSWORD is set correctly in .env file"
        echo "2. Verify database user exists: mysql -u root -p -e \"SELECT User, Host FROM mysql.user WHERE User='$DB_USER';\""
        echo "3. Check database exists: mysql -u root -p -e \"SHOW DATABASES LIKE '$DB_NAME';\""
        echo "4. Verify network connectivity: telnet $DB_HOST $DB_PORT"
    fi
else
    echo -e "${YELLOW}⚠ mysql client not found, skipping direct connection test${NC}"
fi
echo ""

# Step 3: Check Django database connection
echo "Step 3: Testing Django database connection..."
if [ -d "venv" ]; then
    source venv/bin/activate
fi

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-ai_trading_engine.settings_production}"

python manage.py check --database default 2>&1 | head -20
echo ""

# Step 4: Test with Django shell
echo "Step 4: Testing database query..."
python manage.py shell << 'EOF'
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if result:
            print("✓ Django database connection: OK")
        else:
            print("✗ Django database connection: FAILED (no result)")
except Exception as e:
    print(f"✗ Django database connection: FAILED - {e}")
    import traceback
    traceback.print_exc()
EOF

echo ""

# Step 5: Check database connection pool
echo "Step 5: Checking database connection pool..."
python manage.py shell << 'EOF'
from django.db import connections
try:
    conn = connections['default']
    print(f"Database engine: {conn.settings_dict['ENGINE']}")
    print(f"Database name: {conn.settings_dict['NAME']}")
    print(f"Database host: {conn.settings_dict.get('HOST', 'localhost')}")
    print(f"Connection max age: {conn.settings_dict.get('CONN_MAX_AGE', 0)}")
    
    # Test connection
    conn.ensure_connection()
    print("✓ Connection pool: OK")
except Exception as e:
    print(f"✗ Connection pool: FAILED - {e}")
EOF

echo ""

# Step 6: Restart application server (if systemd service exists)
echo "Step 6: Checking application services..."
if systemctl list-units --type=service | grep -q "gunicorn\|uwsgi\|django"; then
    echo "Found application service, checking status..."
    SERVICE_NAME=$(systemctl list-units --type=service | grep -E "gunicorn|uwsgi|django" | head -1 | awk '{print $1}')
    if [ -n "$SERVICE_NAME" ]; then
        echo "Service: $SERVICE_NAME"
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo -e "${GREEN}✓ Application service is running${NC}"
            echo "Restarting service to refresh database connections..."
            sudo systemctl restart "$SERVICE_NAME"
            sleep 3
            if systemctl is-active --quiet "$SERVICE_NAME"; then
                echo -e "${GREEN}✓ Service restarted successfully${NC}"
            else
                echo -e "${RED}✗ Service failed to restart${NC}"
                echo "Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
            fi
        else
            echo -e "${YELLOW}⚠ Application service is not running${NC}"
            echo "Starting service..."
            sudo systemctl start "$SERVICE_NAME"
        fi
    fi
else
    echo "No systemd service found for application"
    echo "If using manual process, restart it manually"
fi
echo ""

# Step 7: Check Redis (if used for cache)
echo "Step 7: Checking Redis connection..."
if command -v redis-cli &> /dev/null; then
    if redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${YELLOW}⚠ Redis is not responding${NC}"
        echo "Attempting to start Redis..."
        sudo systemctl start redis-server || sudo systemctl start redis
        sleep 2
        if redis-cli ping &> /dev/null; then
            echo -e "${GREEN}✓ Redis started successfully${NC}"
        else
            echo -e "${RED}✗ Redis failed to start${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠ redis-cli not found, skipping Redis check${NC}"
fi
echo ""

# Step 8: Summary and recommendations
echo "=========================================="
echo "Summary and Recommendations"
echo "=========================================="
echo ""
echo "If database connection issues persist:"
echo ""
echo "1. Verify database credentials in .env file:"
echo "   cat .env | grep DB_"
echo ""
echo "2. Check database server logs:"
echo "   sudo tail -f /var/log/mysql/error.log"
echo "   OR"
echo "   sudo tail -f /var/log/mariadb/mariadb.log"
echo ""
echo "3. Check Django application logs:"
echo "   tail -f logs/errors.log"
echo ""
echo "4. Test database connection manually:"
echo "   mysql -h $DB_HOST -u $DB_USER -p$DB_PASSWORD $DB_NAME"
echo ""
echo "5. Check network connectivity:"
echo "   telnet $DB_HOST $DB_PORT"
echo ""
echo "6. Restart all services:"
echo "   sudo systemctl restart mysql"
echo "   sudo systemctl restart redis-server"
echo "   sudo systemctl restart <your-app-service>"
echo ""
echo "=========================================="
echo "Diagnostic complete!"
echo "=========================================="
SCRIPT_END

# Make it executable
chmod +x scripts/fix_database_connection.sh

echo "Script created successfully!"
echo "Now run: ./scripts/fix_database_connection.sh"
```

## Quick Alternative: Simple Manual Check

If you want to skip the script and do a quick manual check, run these commands:

```bash
# 1. Check if MySQL is running
sudo systemctl status mysql

# 2. If not running, start it
sudo systemctl start mysql

# 3. Test Django database connection
cd ~/trading-engine/backend
source venv/bin/activate
python manage.py shell
```

In the Python shell:
```python
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        print("✓ Database connection: OK")
except Exception as e:
    print(f"✗ Database connection: FAILED - {e}")
    import traceback
    traceback.print_exc()
```

# Exit shell
exit()

# 4. Restart your application service (find your service name first)
sudo systemctl list-units --type=service | grep -E "gunicorn|uwsgi|django"
# Then restart it (replace SERVICE_NAME with actual name):
sudo systemctl restart SERVICE_NAME
```

