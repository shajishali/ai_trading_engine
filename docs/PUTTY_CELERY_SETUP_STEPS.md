# Step-by-Step Guide: Fix Celery on Production Server Using PuTTY

## Overview
Your automated systems (data storing, signal generation, news fetching) use Celery tasks. On production, you need to run Celery Worker and Celery Beat as background services.

## ⚠️ IMPORTANT: Finding Your Actual Paths

Before creating service files, you need to know your actual paths. The `Environment="PATH=..."` should point to:
- **Format:** `/full/path/to/your/project/backend/venv/bin`
- **Example:** If your project is at `/home/ubuntu/myproject/backend` and you have a `venv` folder, then PATH should be `/home/ubuntu/myproject/backend/venv/bin`

**Quick way to find paths:** Run this helper script on your server:
```bash
cd /path/to/your/project/backend/scripts
chmod +x find_paths.sh
./find_paths.sh
```

See `docs/FIND_YOUR_PATHS.md` for detailed instructions.

---

## STEP 1: Connect to Your Server

1. Open **PuTTY**
2. Enter your server's **IP address** or hostname
3. Port: **22**
4. Click **Open**
5. Login with your username and password

---

## STEP 2: Check Redis (Required for Celery)

Type this command:
```bash
redis-cli ping
```

**Expected result:** `PONG`

**If you get "command not found" or error:**
```bash
sudo apt-get update
sudo apt-get install redis-server -y
sudo systemctl start redis-server
sudo systemctl enable redis-server
redis-cli ping
```

---

## STEP 3: Find Your Project Directory

```bash
# Find where your project is located
find ~ -name "manage.py" -type f 2>/dev/null

# Navigate to your backend directory
cd /path/to/your/project/backend

# Verify you're in the right place (should see manage.py)
ls -la manage.py
```

**Note the full path** - you'll need it later!

---

## STEP 4: Activate Virtual Environment

```bash
# Activate virtual environment
source venv/bin/activate

# Or if it's named differently:
# source env/bin/activate
# source .venv/bin/activate

# Verify (you should see (venv) in your prompt)
which python
```

---

## STEP 5: Verify Celery is Installed

```bash
# Check if Celery is installed
pip list | grep celery

# If not installed:
pip install celery redis
```

---

## STEP 6: Test Celery Connection (Optional)

```bash
# Test if Celery can connect to Redis
python manage.py shell
```

In Python shell, type:
```python
from django.conf import settings
print(settings.CELERY_BROKER_URL)
exit()
```

You should see: `redis://localhost:6379/0` or similar.

---

## STEP 7: Create Systemd Service Files

### Option A: Use the Automated Script (Easier)

```bash
# Navigate to scripts directory
cd /path/to/your/project/backend/scripts

# Make script executable
chmod +x create_celery_services.sh

# Run the script
./create_celery_services.sh
```

The script will automatically:
- Find your project path
- Find your virtual environment
- Create both service files
- Use correct user and paths

### Option B: Create Manually

**Create Worker Service:**
```bash
sudo nano /etc/systemd/system/ai-trading-celery-worker.service
```

Paste this (REPLACE paths with your actual paths):
```ini
[Unit]
Description=AI Trading Engine Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_GROUP
WorkingDirectory=/path/to/your/project/backend
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=/path/to/your/project/backend/venv/bin"
ExecStart=/path/to/your/project/backend/venv/bin/celery -A ai_trading_engine worker --loglevel=info --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**To find your username and paths:**

**Option 1: Use the helper script (Easiest)**
```bash
cd /path/to/your/project/backend/scripts
chmod +x find_paths.sh
./find_paths.sh
```
This will show you all the paths you need!

**Option 2: Find manually**
```bash
# Find your project directory
find ~ -name "manage.py" -type f 2>/dev/null

# Navigate to it
cd /path/that/was/shown/above

# Get current directory (this is your PROJECT_DIR)
pwd

# Find virtual environment
ls -la | grep venv  # or env or .venv

# Get your username
whoami

# Get your group
id -gn

# Find Celery binary
which celery  # (when venv is activated)
# OR
ls -la venv/bin/celery
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

**Create Beat Service:**
```bash
sudo nano /etc/systemd/system/ai-trading-celery-beat.service
```

Paste this (REPLACE paths):
```ini
[Unit]
Description=AI Trading Engine Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=YOUR_USERNAME
Group=YOUR_GROUP
WorkingDirectory=/path/to/your/project/backend
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
Environment="PATH=/path/to/your/project/backend/venv/bin"
ExecStart=/path/to/your/project/backend/venv/bin/celery -A ai_trading_engine beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## STEP 8: Start the Services

```bash
# Reload systemd (required after creating new services)
sudo systemctl daemon-reload

# Start Celery Worker
sudo systemctl start ai-trading-celery-worker

# Start Celery Beat
sudo systemctl start ai-trading-celery-beat

# Enable auto-start on boot
sudo systemctl enable ai-trading-celery-worker
sudo systemctl enable ai-trading-celery-beat
```

---

## STEP 9: Check if Services are Running

```bash
# Check Worker status
sudo systemctl status ai-trading-celery-worker

# Check Beat status
sudo systemctl status ai-trading-celery-beat
```

**What you should see:**
- Status: `active (running)` in green
- No red error messages
- Messages like "Connected to redis://..."

**If you see errors:**
```bash
# View detailed logs
sudo journalctl -u ai-trading-celery-worker -n 50
sudo journalctl -u ai-trading-celery-beat -n 50
```

---

## STEP 10: Verify Everything is Working

### Check Real-time Logs

```bash
# Watch Worker logs (press Ctrl+C to exit)
sudo journalctl -u ai-trading-celery-worker -f

# Watch Beat logs (press Ctrl+C to exit)
sudo journalctl -u ai-trading-celery-beat -f
```

You should see:
- Worker: "celery@hostname ready"
- Beat: "Scheduler: Sending: task-name"

### Test a Task (Optional)

```bash
cd /path/to/your/project/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py shell
```

In Python:
```python
from apps.data.tasks import update_coin_data_task
result = update_coin_data_task.delay()
print("Task ID:", result.id)
exit()
```

Check logs to see if task was processed.

---

## TROUBLESHOOTING

### Problem: Service won't start

**Check logs:**
```bash
sudo journalctl -u ai-trading-celery-worker -n 100
```

**Common fixes:**

1. **Permission denied:**
```bash
sudo chown -R $(whoami):$(whoami) /path/to/your/project/backend
```

2. **Redis not running:**
```bash
sudo systemctl start redis-server
redis-cli ping
```

3. **Wrong paths in service file:**
```bash
# Check service file
sudo cat /etc/systemd/system/ai-trading-celery-worker.service

# Verify paths exist
ls -la /path/to/your/project/backend/venv/bin/celery
```

4. **Settings file not found:**
```bash
ls -la /path/to/your/project/backend/ai_trading_engine/settings_production.py
```

### Problem: Tasks not running

1. **Check if Worker is running:**
```bash
sudo systemctl status ai-trading-celery-worker
```

2. **Check if Beat is running:**
```bash
sudo systemctl status ai-trading-celery-beat
```

3. **Check Redis connection:**
```bash
redis-cli ping
```

4. **Check Celery logs:**
```bash
sudo journalctl -u ai-trading-celery-worker -f
```

### Problem: Service stops after a few minutes

Check logs for errors:
```bash
sudo journalctl -u ai-trading-celery-worker -n 200
```

Common causes:
- Out of memory
- Database connection issues
- Missing dependencies

---

## USEFUL COMMANDS REFERENCE

### Service Management
```bash
# Start
sudo systemctl start ai-trading-celery-worker
sudo systemctl start ai-trading-celery-beat

# Stop
sudo systemctl stop ai-trading-celery-worker
sudo systemctl stop ai-trading-celery-beat

# Restart
sudo systemctl restart ai-trading-celery-worker
sudo systemctl restart ai-trading-celery-beat

# Status
sudo systemctl status ai-trading-celery-worker
sudo systemctl status ai-trading-celery-beat

# Enable/Disable auto-start
sudo systemctl enable ai-trading-celery-worker
sudo systemctl disable ai-trading-celery-worker
```

### View Logs
```bash
# Real-time (follow)
sudo journalctl -u ai-trading-celery-worker -f
sudo journalctl -u ai-trading-celery-beat -f

# Last N lines
sudo journalctl -u ai-trading-celery-worker -n 50
sudo journalctl -u ai-trading-celery-beat -n 50

# Since today
sudo journalctl -u ai-trading-celery-worker --since today
```

### Check System
```bash
# Check Redis
redis-cli ping

# Check if services are active
sudo systemctl is-active ai-trading-celery-worker
sudo systemctl is-active ai-trading-celery-beat

# Check all Celery processes
ps aux | grep celery
```

---

## VERIFICATION CHECKLIST

After setup, verify:

- [ ] Redis is running: `redis-cli ping` returns `PONG`
- [ ] Worker service is active: `sudo systemctl status ai-trading-celery-worker` shows `active (running)`
- [ ] Beat service is active: `sudo systemctl status ai-trading-celery-beat` shows `active (running)`
- [ ] Services start on boot: Both services are `enabled`
- [ ] Logs show no errors: `sudo journalctl -u ai-trading-celery-worker -n 50` shows no red errors
- [ ] Tasks are being scheduled: Beat logs show "Sending: task-name"
- [ ] Tasks are being processed: Worker logs show task execution

---

## SUMMARY

**What you've done:**
1. ✅ Connected to server via PuTTY
2. ✅ Verified Redis is running
3. ✅ Created systemd service files for Celery Worker and Beat
4. ✅ Started and enabled the services
5. ✅ Verified services are running

**Your automated systems should now be working:**
- Data storing tasks will run automatically
- Signal generation will run on schedule
- News fetching will run on schedule

**Services will:**
- Start automatically on server reboot
- Restart automatically if they crash
- Run in the background (no need to keep PuTTY open)

---

## Need More Help?

If you encounter issues:
1. Check the detailed guide: `docs/celery-production-setup-guide.md`
2. Check quick reference: `docs/celery-quick-reference.md`
3. Review service logs: `sudo journalctl -u ai-trading-celery-worker -n 100`

