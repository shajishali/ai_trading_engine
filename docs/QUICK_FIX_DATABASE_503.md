# Quick Fix: Database 503 Error on Signal Generation Page

## Problem
The signal generation page shows "Database temporarily unavailable" errors and returns 503 status codes.

## Immediate Fix Steps (Run on Server via PuTTY/SSH)

### Step 1: Connect to Server
```bash
ssh user@your-server-ip
# OR use PuTTY to connect
```

### Step 2: Navigate to Project
```bash
cd /path/to/your/project/backend
```

### Step 3: Run Database Fix Script
```bash
# Make script executable
chmod +x scripts/fix_database_connection.sh

# Run the script
./scripts/fix_database_connection.sh
```

### Step 4: Quick Manual Checks

#### Check MySQL is Running
```bash
sudo systemctl status mysql
# OR
sudo systemctl status mariadb

# If not running, start it:
sudo systemctl start mysql
```

#### Test Database Connection
```bash
# Activate virtual environment
source venv/bin/activate

# Test connection
python manage.py dbshell
# If this works, type: exit

# Or test with Django shell
python manage.py shell
```

In Django shell:
```python
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT 1")
    print("Database connection: OK")
```

#### Check Database Credentials
```bash
# Check .env file (if exists)
cat .env | grep DB_

# Or check settings
python manage.py shell
>>> from django.conf import settings
>>> print(settings.DATABASES['default'])
```

### Step 5: Restart Services
```bash
# Restart MySQL
sudo systemctl restart mysql

# Restart Redis (if using)
sudo systemctl restart redis-server

# Restart application server
# Find your service name:
sudo systemctl list-units --type=service | grep -E "gunicorn|uwsgi|django"

# Restart it (replace SERVICE_NAME):
sudo systemctl restart SERVICE_NAME

# Check status
sudo systemctl status SERVICE_NAME
```

### Step 6: Check Logs
```bash
# Application logs
tail -f logs/errors.log

# MySQL logs
sudo tail -f /var/log/mysql/error.log

# System logs
sudo journalctl -u your-app-service -n 50
```

## Common Issues and Solutions

### Issue 1: MySQL Not Running
**Symptoms:** Connection refused errors
**Fix:**
```bash
sudo systemctl start mysql
sudo systemctl enable mysql  # Enable on boot
```

### Issue 2: Wrong Database Credentials
**Symptoms:** Access denied errors
**Fix:**
1. Check `.env` file or environment variables
2. Verify database user exists:
```bash
mysql -u root -p
mysql> SELECT User, Host FROM mysql.user WHERE User='trading_user';
mysql> SHOW GRANTS FOR 'trading_user'@'localhost';
```

3. Update credentials if needed:
```bash
# Edit .env file
nano .env
# Update DB_PASSWORD, DB_USER, etc.
```

### Issue 3: Database Doesn't Exist
**Symptoms:** Unknown database errors
**Fix:**
```bash
mysql -u root -p
mysql> CREATE DATABASE IF NOT EXISTS ai_trading_engine;
mysql> GRANT ALL PRIVILEGES ON ai_trading_engine.* TO 'trading_user'@'localhost';
mysql> FLUSH PRIVILEGES;
```

### Issue 4: Too Many Connections
**Symptoms:** Too many connections error
**Fix:**
```bash
mysql -u root -p
mysql> SHOW PROCESSLIST;
mysql> SET GLOBAL max_connections = 200;
mysql> SHOW VARIABLES LIKE 'max_connections';
```

### Issue 5: Connection Timeout
**Symptoms:** Connection timeout errors
**Fix:**
1. Check network connectivity:
```bash
telnet localhost 3306
```

2. Increase timeout in Django settings:
```python
# In settings_production.py
DATABASES = {
    'default': {
        # ... other settings ...
        'OPTIONS': {
            'connect_timeout': 30,  # Increase from 10
            'read_timeout': 60,     # Increase from 30
            'write_timeout': 60,    # Increase from 30
        },
    }
}
```

### Issue 6: Stale Database Connections
**Symptoms:** Intermittent connection failures
**Fix:**
```bash
# Restart application to clear connection pool
sudo systemctl restart your-app-service

# Or reduce CONN_MAX_AGE in settings
# CONN_MAX_AGE: 300  # 5 minutes instead of 600
```

## Verify Fix

### Test via Browser
1. Open: `https://cryptai.it.com/signals/`
2. Check browser console (F12) - should see no 503 errors
3. Signals should load in the table

### Test via API
```bash
curl -X GET "https://cryptai.it.com/signals/api/signals/" \
  -H "Accept: application/json"
```

Should return:
```json
{
  "success": true,
  "signals": [...],
  "count": X
}
```

### Test via Django Shell
```bash
python manage.py shell
```

```python
from apps.signals.models import TradingSignal
from apps.signals.views import SignalAPIView
from django.test import RequestFactory

# Test query
signals = TradingSignal.objects.filter(is_valid=True)[:5]
print(f"Found {signals.count()} signals")

# Test API view
factory = RequestFactory()
request = factory.get('/signals/api/signals/')
view = SignalAPIView.as_view()
response = view(request)
print(f"API Response status: {response.status_code}")
```

## Prevention

### 1. Set Up Monitoring
```bash
# Create a health check script
cat > scripts/health_check.sh << 'EOF'
#!/bin/bash
python manage.py shell << PYTHON
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("OK")
except:
    print("FAIL")
PYTHON
EOF

chmod +x scripts/health_check.sh

# Add to cron for monitoring
# */5 * * * * /path/to/project/backend/scripts/health_check.sh
```

### 2. Configure Connection Pooling
Ensure `CONN_MAX_AGE` is set appropriately in `settings_production.py`:
```python
'CONN_MAX_AGE': 300,  # 5 minutes - prevents stale connections
```

### 3. Set Up Automatic Restart
Configure systemd to restart on failure:
```ini
[Service]
Restart=always
RestartSec=10
```

## Still Having Issues?

1. **Run diagnostic script:**
   ```bash
   python manage.py shell < scripts/diagnose_signal_generation.py
   ```

2. **Check detailed logs:**
   ```bash
   tail -f logs/errors.log
   tail -f logs/trading_engine.log
   ```

3. **Review database server logs:**
   ```bash
   sudo tail -f /var/log/mysql/error.log
   ```

4. **Check system resources:**
   ```bash
   free -h  # Memory
   df -h    # Disk space
   top      # CPU usage
   ```

## Quick Reference Commands

```bash
# Check MySQL status
sudo systemctl status mysql

# Restart MySQL
sudo systemctl restart mysql

# Check database connection
python manage.py dbshell

# Test Django connection
python manage.py shell
>>> from django.db import connection
>>> connection.ensure_connection()

# Restart app service
sudo systemctl restart your-app-service

# View logs
tail -f logs/errors.log
sudo journalctl -u your-app-service -f
```

