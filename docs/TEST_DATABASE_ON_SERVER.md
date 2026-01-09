# Test Database Connection on Server

## Step 1: Test Database Connection in Django Shell

```bash
cd ~/trading-engine/backend
source venv/bin/activate
python manage.py shell
```

Then run:
```python
from django.db import connection, connections
from django.conf import settings

# Check database settings
print("Database settings:")
print(f"  Engine: {settings.DATABASES['default']['ENGINE']}")
print(f"  Name: {settings.DATABASES['default']['NAME']}")
print(f"  Host: {settings.DATABASES['default'].get('HOST', 'localhost')}")
print(f"  User: {settings.DATABASES['default']['USER']}")

# Test connection
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"\n✓ Database connection successful! Result: {result}")
except Exception as e:
    print(f"\n✗ Database connection failed: {e}")
    import traceback
    traceback.print_exc()
```

## Step 2: Test Signal Models

```python
# Test if we can query signals
from apps.signals.models import TradingSignal
try:
    count = TradingSignal.objects.count()
    print(f"✓ Found {count} signals in database")
    
    # Try to get a few signals
    signals = TradingSignal.objects.filter(is_valid=True)[:5]
    print(f"✓ Found {signals.count()} valid signals")
    
    if signals.exists():
        for signal in signals:
            print(f"  - {signal.symbol.symbol}: {signal.signal_type.name}")
except Exception as e:
    print(f"✗ Error querying signals: {e}")
    import traceback
    traceback.print_exc()
```

## Step 3: Test the API View Directly

```python
from apps.signals.views import SignalAPIView
from django.test import RequestFactory
from django.contrib.auth.models import User

# Create a test request
factory = RequestFactory()
request = factory.get('/signals/api/signals/')

# Get or create a test user (for login_required)
user = User.objects.first()
if user:
    request.user = user
else:
    print("⚠ No users found - create one or skip login_required")

# Test the view
try:
    view = SignalAPIView.as_view()
    response = view(request)
    print(f"✓ API View Response Status: {response.status_code}")
    if response.status_code == 200:
        import json
        data = json.loads(response.content)
        print(f"✓ API returned {data.get('count', 0)} signals")
    else:
        print(f"✗ API returned error status: {response.status_code}")
        print(f"  Content: {response.content.decode()[:200]}")
except Exception as e:
    print(f"✗ Error testing API view: {e}")
    import traceback
    traceback.print_exc()
```

## Step 4: Check Application Service

```bash
# Find your application service
sudo systemctl list-units --type=service | grep -E "gunicorn|uwsgi|django|trading"

# Check status
sudo systemctl status <your-service-name>

# Restart if needed
sudo systemctl restart <your-service-name>

# Check logs
sudo journalctl -u <your-service-name> -n 50 --no-pager
```

## Step 5: Check Application Logs

```bash
# Check Django error logs
tail -f logs/errors.log

# Check application logs
tail -f logs/trading_engine.log | grep -i "database\|connection\|error"
```

## Common Issues

### Issue: Database connection works in shell but not in API
**Solution:** This usually means:
1. Connection pool is exhausted - restart application service
2. Different settings module - check DJANGO_SETTINGS_MODULE
3. Connection timeout - increase timeout in settings

### Issue: "Too many connections"
**Solution:**
```bash
mysql -u root -p
mysql> SHOW PROCESSLIST;
mysql> SET GLOBAL max_connections = 200;
mysql> SHOW VARIABLES LIKE 'max_connections';
```

### Issue: Connection works but API still returns 503
**Solution:**
1. Check if the view is using the correct database connection
2. Restart application service to clear connection pool
3. Check if there are any middleware issues
4. Verify the request is reaching the view (check logs)

