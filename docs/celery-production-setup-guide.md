# Celery Production Setup Guide - Step by Step

This guide will help you set up Celery workers and beat scheduler on your production server using PuTTY.

## Prerequisites
- You have SSH access to your production server via PuTTY
- Your Django application is already deployed
- You have root or sudo access on the server

---

## Step 1: Connect to Your Server via PuTTY

1. Open PuTTY
2. Enter your server's IP address or hostname
3. Port: 22 (default SSH port)
4. Connection type: SSH
5. Click "Open"
6. Login with your username and password

---

## Step 2: Check if Redis is Running

Redis is required for Celery to work. Check if it's installed and running:

```bash
# Check if Redis is installed
redis-cli ping

# If you get "PONG" response, Redis is running
# If you get "command not found", Redis needs to be installed
```

**If Redis is NOT installed:**

```bash
# For Ubuntu/Debian:
sudo apt-get update
sudo apt-get install redis-server -y

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping
```

---

## Step 3: Navigate to Your Project Directory

```bash
# Find your project directory (adjust path as needed)
cd /path/to/your/project/backend

# Or if it's in a different location, find it:
find ~ -name "manage.py" -type f 2>/dev/null

# Once found, navigate there
cd /path/to/your/project/backend
```

---

## Step 4: Activate Your Virtual Environment

```bash
# If you have a virtual environment (venv)
source venv/bin/activate

# Or if it's named differently:
source env/bin/activate
# or
source .venv/bin/activate

# Verify you're in the virtual environment (you should see (venv) or similar in prompt)
which python
```

---

## Step 5: Verify Celery Configuration

```bash
# Check if Celery can connect to Redis
python -c "from django.conf import settings; import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings_production'); from django import setup; setup(); print('Celery Broker:', settings.CELERY_BROKER_URL)"
```

You should see your Redis URL. If there's an error, check your settings file.

---

## Step 6: Test Celery Worker Manually (Optional - for testing)

First, let's test if Celery works:

```bash
# In one terminal, start Celery worker (for testing)
celery -A ai_trading_engine worker --loglevel=info

# You should see output like:
# [INFO/MainProcess] Connected to redis://localhost:6379/0
# [INFO/MainProcess] celery@hostname ready.

# Press Ctrl+C to stop it after testing
```

---

## Step 7: Create Systemd Service Files

We'll create systemd services so Celery runs automatically and restarts on server reboot.

### Create Celery Worker Service

```bash
# Create the service file
sudo nano /etc/systemd/system/ai-trading-celery-worker.service
```

**Paste the following content** (adjust paths as needed):

```ini
[Unit]
Description=AI Trading Engine Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/your/project/backend
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=/path/to/your/project/backend/venv/bin"
ExecStart=/path/to/your/project/backend/venv/bin/celery -A ai_trading_engine worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Important:** Replace these paths:
- `/path/to/your/project/backend` - Your actual project path
- `User=www-data` - Your server user (could be `ubuntu`, `debian`, or your username)
- `venv/bin` - Your virtual environment path

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### Create Celery Beat Service

```bash
# Create the beat service file
sudo nano /etc/systemd/system/ai-trading-celery-beat.service
```

**Paste the following content**:

```ini
[Unit]
Description=AI Trading Engine Celery Beat Scheduler
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/path/to/your/project/backend
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=/path/to/your/project/backend/venv/bin"
ExecStart=/path/to/your/project/backend/venv/bin/celery -A ai_trading_engine beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Again, replace the paths** as mentioned above.

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## Step 8: Find Your Actual Paths

To find the correct paths, run these commands:

```bash
# Find your project directory
pwd
# (when you're in your project/backend directory)

# Find your Python virtual environment
which python
# (when virtual environment is activated)

# Find your user
whoami

# Find your group
groups
```

Update the service files with these actual values.

---

## Step 9: Reload Systemd and Start Services

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Start Celery Worker
sudo systemctl start ai-trading-celery-worker

# Start Celery Beat
sudo systemctl start ai-trading-celery-beat

# Enable them to start on boot
sudo systemctl enable ai-trading-celery-worker
sudo systemctl enable ai-trading-celery-beat
```

---

## Step 10: Check Service Status

```bash
# Check Celery Worker status
sudo systemctl status ai-trading-celery-worker

# Check Celery Beat status
sudo systemctl status ai-trading-celery-beat

# If there are errors, check the logs:
sudo journalctl -u ai-trading-celery-worker -f
sudo journalctl -u ai-trading-celery-beat -f
```

**What to look for:**
- Status should show "active (running)" in green
- No red error messages
- You should see "Connected to redis://..." messages

---

## Step 11: Troubleshooting Common Issues

### Issue 1: Permission Denied

```bash
# Fix ownership of project directory
sudo chown -R www-data:www-data /path/to/your/project/backend

# Or use your actual user instead of www-data
sudo chown -R your-username:your-username /path/to/your/project/backend
```

### Issue 2: Cannot Connect to Redis

```bash
# Check if Redis is running
sudo systemctl status redis-server

# Check Redis connection
redis-cli ping

# If Redis is not running:
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Issue 3: Module Not Found Errors

```bash
# Make sure virtual environment is correct in service file
# Verify Python packages are installed
source /path/to/your/project/backend/venv/bin/activate
pip list | grep celery
pip list | grep redis
```

### Issue 4: Settings Module Not Found

```bash
# Verify your settings file exists
ls -la /path/to/your/project/backend/ai_trading_engine/settings_production.py

# Test Django settings
cd /path/to/your/project/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py check
```

---

## Step 12: Verify Celery is Working

```bash
# Check if tasks are being processed
# In your Django shell or management command:
cd /path/to/your/project/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py shell

# In Python shell:
from apps.data.tasks import update_coin_data_task
result = update_coin_data_task.delay()
print(result.id)
```

---

## Step 13: Monitor Celery Logs

```bash
# View real-time logs for worker
sudo journalctl -u ai-trading-celery-worker -f

# View real-time logs for beat
sudo journalctl -u ai-trading-celery-beat -f

# View last 100 lines
sudo journalctl -u ai-trading-celery-worker -n 100
```

---

## Step 14: Useful Commands

### Stop Services
```bash
sudo systemctl stop ai-trading-celery-worker
sudo systemctl stop ai-trading-celery-beat
```

### Restart Services
```bash
sudo systemctl restart ai-trading-celery-worker
sudo systemctl restart ai-trading-celery-beat
```

### Disable Auto-start on Boot
```bash
sudo systemctl disable ai-trading-celery-worker
sudo systemctl disable ai-trading-celery-beat
```

### Check if Services are Running
```bash
sudo systemctl is-active ai-trading-celery-worker
sudo systemctl is-active ai-trading-celery-beat
```

---

## Step 15: Verify Scheduled Tasks

Your Celery Beat should be running scheduled tasks. Check the logs to see if tasks are being scheduled:

```bash
sudo journalctl -u ai-trading-celery-beat -n 50 | grep "Scheduler"
```

You should see messages about scheduled tasks being sent to the queue.

---

## Quick Reference: All Commands in One Place

```bash
# 1. Connect via PuTTY (do this first)

# 2. Navigate to project
cd /path/to/your/project/backend

# 3. Check Redis
redis-cli ping

# 4. Create service files (use nano editor)
sudo nano /etc/systemd/system/ai-trading-celery-worker.service
sudo nano /etc/systemd/system/ai-trading-celery-beat.service

# 5. Reload and start
sudo systemctl daemon-reload
sudo systemctl start ai-trading-celery-worker
sudo systemctl start ai-trading-celery-beat
sudo systemctl enable ai-trading-celery-worker
sudo systemctl enable ai-trading-celery-beat

# 6. Check status
sudo systemctl status ai-trading-celery-worker
sudo systemctl status ai-trading-celery-beat

# 7. View logs
sudo journalctl -u ai-trading-celery-worker -f
sudo journalctl -u ai-trading-celery-beat -f
```

---

## Need Help?

If you encounter errors:
1. Check the service logs: `sudo journalctl -u ai-trading-celery-worker -n 50`
2. Verify all paths in service files are correct
3. Ensure Redis is running: `redis-cli ping`
4. Check file permissions: `ls -la /path/to/your/project/backend`
5. Verify virtual environment: `which python` (should show venv path)

---

## Summary

After completing these steps:
- ✅ Celery Worker will be running and processing tasks
- ✅ Celery Beat will be scheduling periodic tasks
- ✅ Both services will automatically start on server reboot
- ✅ Services will automatically restart if they crash
- ✅ You can monitor logs using journalctl

Your automated systems (data storing, signal generation, news fetching) should now be working!

