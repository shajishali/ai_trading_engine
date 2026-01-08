# Step-by-Step Guide: Deploy and Run Automation Scripts on Ubuntu via PuTTY

This guide will help you:
1. Push the automation scripts to GitHub
2. Pull them on your Ubuntu server via PuTTY
3. Run the automation in production

## Prerequisites
- Git repository initialized
- Access to your Ubuntu server via PuTTY/SSH
- Python and Django installed on Ubuntu server

---

## Step 1: Make Scripts Executable (Local - Windows)

The scripts are already created. If you need to make them executable again:

```bash
cd backend/scripts
chmod +x start_all_automation.sh stop_all_automation.sh
```

---

## Step 2: Commit and Push to GitHub

### 2.1 Check Git Status
```bash
cd "D:\Research Development"
git status
```

### 2.2 Add the New Scripts
```bash
git add backend/scripts/start_all_automation.sh
git add backend/scripts/stop_all_automation.sh
```

### 2.3 Commit the Changes
```bash
git commit -m "Add Linux automation scripts for production deployment"
```

### 2.4 Push to GitHub
```bash
git push origin main
```
(Replace `main` with your branch name if different, e.g., `master` or `develop`)

---

## Step 3: Connect to Ubuntu Server via PuTTY

1. Open PuTTY
2. Enter your server's IP address or hostname
3. Port: 22 (default SSH port)
4. Click "Open"
5. Login with your username and password

---

## Step 4: Navigate to Your Project on Ubuntu

Once connected via PuTTY, navigate to your project directory:

```bash
cd /path/to/your/project
# Example: cd ~/ai-trading-engine
# Or: cd /var/www/ai-trading-engine
```

---

## Step 5: Pull Latest Changes from GitHub

### 5.1 Check Current Status
```bash
git status
```

### 5.2 Pull Latest Changes
```bash
git pull origin main
```
(Replace `main` with your branch name if different)

This will download the new `start_all_automation.sh` and `stop_all_automation.sh` scripts.

---

## Step 6: Make Scripts Executable on Ubuntu

```bash
cd backend/scripts
chmod +x start_all_automation.sh stop_all_automation.sh
```

---

## Step 7: Create Logs Directory (if it doesn't exist)

```bash
cd ../..  # Go back to project root
mkdir -p logs
```

---

## Step 8: Run the Automation Script

### Option A: Run Directly (will stop when you close PuTTY)
```bash
cd backend/scripts
./start_all_automation.sh
```

### Option B: Run in Background (recommended for production)
```bash
cd backend/scripts
nohup ./start_all_automation.sh > ../logs/startup.log 2>&1 &
```

### Option C: Run in Screen Session (best for production)
```bash
# Install screen if not installed
sudo apt-get update
sudo apt-get install screen -y

# Start a screen session
screen -S automation

# Run the script
cd backend/scripts
./start_all_automation.sh

# Detach from screen: Press Ctrl+A, then D
# Reattach later: screen -r automation
```

### Option D: Run in TMUX Session (alternative to screen)
```bash
# Install tmux if not installed
sudo apt-get update
sudo apt-get install tmux -y

# Start a tmux session
tmux new -s automation

# Run the script
cd backend/scripts
./start_all_automation.sh

# Detach from tmux: Press Ctrl+B, then D
# Reattach later: tmux attach -t automation
```

---

## Step 9: Verify Services are Running

### Check if processes are running:
```bash
ps aux | grep "manage.py runserver"
ps aux | grep "run_signal_generation.py"
ps aux | grep "update_all_coins.py"
ps aux | grep "update_news_live.py"
```

### Check logs:
```bash
cd backend/logs
tail -f django.log
tail -f signal_generation.log
tail -f update_coins.log
tail -f update_news.log
```

### Check if Django server is accessible:
```bash
curl http://localhost:8000
# Or from another machine: curl http://YOUR_SERVER_IP:8000
```

---

## Step 10: Stop Services (if needed)

```bash
cd backend/scripts
./stop_all_automation.sh
```

---

## Troubleshooting

### Issue: "Permission denied" when running script
**Solution:**
```bash
chmod +x start_all_automation.sh
```

### Issue: "No such file or directory" for logs
**Solution:**
```bash
mkdir -p backend/logs
```

### Issue: Port 8000 already in use
**Solution:**
```bash
# Find process using port 8000
sudo lsof -i :8000
# Or
sudo netstat -tulpn | grep :8000

# Kill the process
kill -9 <PID>
```

### Issue: Script stops when closing PuTTY
**Solution:** Use `screen` or `tmux` (see Step 8, Option C or D)

### Issue: Python not found
**Solution:**
```bash
# Check Python installation
which python
which python3

# Use python3 if python doesn't work
# Edit start_all_automation.sh and change 'python' to 'python3'
```

---

## Production Recommendations

For a production environment, consider:

1. **Use Gunicorn instead of runserver:**
   Edit `start_all_automation.sh` and replace:
   ```bash
   nohup python manage.py runserver 0.0.0.0:8000 > logs/django.log 2>&1 &
   ```
   With:
   ```bash
   nohup gunicorn --bind 0.0.0.0:8000 --workers 4 ai_trading_engine.wsgi:application > logs/django.log 2>&1 &
   ```

2. **Use systemd services** for automatic startup and better process management

3. **Use Nginx** as a reverse proxy in front of Django

4. **Set up log rotation** to prevent log files from growing too large

---

## Quick Reference Commands

```bash
# Pull latest code
git pull origin main

# Start automation
cd backend/scripts && ./start_all_automation.sh

# Stop automation
cd backend/scripts && ./stop_all_automation.sh

# Check running processes
ps aux | grep python

# View logs
tail -f backend/logs/django.log

# Check server status
curl http://localhost:8000
```

---

## Notes

- The scripts create PID files in `backend/logs/` directory to track running processes
- Logs are written to `backend/logs/` directory
- Make sure your firewall allows port 8000 (or your configured port)
- For production, consider using a proper WSGI server like Gunicorn with Nginx

