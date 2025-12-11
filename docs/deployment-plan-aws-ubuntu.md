# AWS Ubuntu Deployment Plan - AI Trading Engine (Simplified)

## 🎯 Goal
Get the website working and signals generating. That's it.

**Total Time**: ~1 hour

---

## 🪟 Windows Users - Quick Setup

### Required Tools
- **PuTTY** - SSH terminal (https://www.putty.org/)
- **PuTTYgen** - SSH key tool (included with PuTTY)
- **WinSCP** (Optional) - File transfer GUI (https://winscp.net/)

### Connect to Server
1. **Convert PEM to PuTTY format**:
   - Open PuTTYgen → Conversions → Import key → Select your PEM file
   - Save as `trading-engine-key.ppk`

2. **Configure PuTTY**:
   - Host: `52.221.248.235`
   - Port: `22`
   - Connection → Data → Auto-login username: `ubuntu`
   - Connection → SSH → Auth → Browse → Select your `.ppk` file
   - Save session and connect

**All commands below run in PuTTY terminal.**

---

## 📋 Deployment Phases

| Phase | Name | Time |
|-------|------|------|
| **Phase 1** | Server Setup | 15 min |
| **Phase 2** | Database Setup | 10 min |
| **Phase 3** | Deploy Application | 20 min |
| **Phase 4** | Setup Celery | 10 min |
| **Phase 5** | Setup Gunicorn | 10 min |
| **Phase 6** | Setup Nginx | 10 min |
| **Phase 7** | Verify Everything | 5 min |

---

## Phase 1: Server Setup (15 min)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install essentials
sudo apt install -y python3.10 python3.10-venv python3-pip \
    mysql-server mysql-client nginx redis-server git curl \
    build-essential default-libmysqlclient-dev python3-dev

# Configure firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Create deployment user (optional, or use ubuntu user)
sudo adduser tradingengine
sudo usermod -aG sudo tradingengine
```

---

## Phase 2: Database Setup (10 min)

```bash
# Secure MySQL installation
sudo mysql_secure_installation
# Follow prompts: set root password, remove anonymous users, etc.

# Create database and user
sudo mysql -u root -p
```

**In MySQL prompt, run:**
```sql
CREATE DATABASE trading_engine_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trading_user'@'localhost' IDENTIFIED BY 'YOUR_STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON trading_engine_db.* TO 'trading_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

**Test connection:**
```bash
mysql -u trading_user -p trading_engine_db
# Enter password, should see mysql> prompt
# Type: EXIT; to exit
```

---

## Phase 3: Deploy Application (20 min)

### 3.1 Clone/Upload Project

**Option A: Using Git**
```bash
cd ~
git clone YOUR_REPO_URL trading-engine
cd trading-engine/backend
```

**Option B: Using WinSCP (Windows users)**
1. Open WinSCP → Connect to server
2. Upload entire project to `/home/tradingengine/trading-engine/`
3. In PuTTY: `cd ~/trading-engine/backend`

### 3.2 Setup Virtual Environment

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.3 Configure Environment

```bash
# Create .env file
cp env.production.template .env
nano .env
```

**Required .env variables:**
```bash
DEBUG=False
SECRET_KEY=GENERATE_STRONG_SECRET_KEY_HERE
ALLOWED_HOSTS=52.221.248.235
DB_ENGINE=django.db.backends.mysql
DB_NAME=trading_engine_db
DB_USER=trading_user
DB_PASSWORD=YOUR_DB_PASSWORD_HERE
DB_HOST=localhost
DB_PORT=3306
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

**Generate SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 3.4 Update Production Settings

```bash
# Edit settings_production.py
nano ai_trading_engine/settings_production.py
```

**Update database configuration:**
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',  # Changed from postgresql
        'NAME': config('DB_NAME', default='trading_engine_db'),
        'USER': config('DB_USER', default='trading_user'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}
```

### 3.5 Run Migrations and Setup

```bash
# Set production settings
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Verify static files
ls -la staticfiles/
```

---

## Phase 4: Setup Celery (10 min)

### 4.1 Create Celery Worker Service

```bash
sudo nano /etc/systemd/system/celery-worker.service
```

**Paste this:**
```ini
[Unit]
Description=Celery Worker for AI Trading Engine
After=network.target redis-server.service mysql.service

[Service]
Type=forking
User=tradingengine
Group=tradingengine
WorkingDirectory=/home/tradingengine/trading-engine/backend
Environment="PATH=/home/tradingengine/trading-engine/backend/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/celery -A ai_trading_engine worker --loglevel=info --pool=solo --pidfile=/var/run/celery/worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4.2 Create Celery Beat Service

```bash
sudo nano /etc/systemd/system/celery-beat.service
```

**Paste this:**
```ini
[Unit]
Description=Celery Beat Scheduler for AI Trading Engine
After=network.target redis-server.service mysql.service

[Service]
Type=forking
User=tradingengine
Group=tradingengine
WorkingDirectory=/home/tradingengine/trading-engine/backend
Environment="PATH=/home/tradingengine/trading-engine/backend/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/celery -A ai_trading_engine beat --loglevel=info --pidfile=/var/run/celery/beat.pid --logfile=/var/log/celery/beat.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4.3 Enable and Start Celery

```bash
# Create directories
sudo mkdir -p /var/run/celery /var/log/celery
sudo chown tradingengine:tradingengine /var/run/celery /var/log/celery

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat

# Check status
sudo systemctl status celery-worker
sudo systemctl status celery-beat
```

---

## Phase 5: Setup Gunicorn (10 min)

### 5.1 Create Gunicorn Service

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

**Paste this:**
```ini
[Unit]
Description=Gunicorn daemon for AI Trading Engine
After=network.target mysql.service redis-server.service

[Service]
User=tradingengine
Group=tradingengine
WorkingDirectory=/home/tradingengine/trading-engine/backend
Environment="PATH=/home/tradingengine/trading-engine/backend/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/gunicorn \
    --config gunicorn.conf.py \
    --bind 0.0.0.0:8000 \
    ai_trading_engine.wsgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.2 Enable and Start Gunicorn

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn

# Check status
sudo systemctl status gunicorn

# Verify it's listening on port 8000
sudo ss -ltnp | grep 8000
```

**If Gunicorn fails, check logs:**
```bash
sudo journalctl -u gunicorn -n 50 --no-pager
```

---

## Phase 6: Setup Nginx (10 min)

### 6.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/trading-engine
```

**Paste this (replace IP with your server IP):**
```nginx
server {
    listen 80;
    server_name 52.221.248.235;

    client_max_body_size 10M;

    # Static files
    location /static/ {
        alias /home/tradingengine/trading-engine/backend/staticfiles/;
    }

    # Media files
    location /media/ {
        alias /home/tradingengine/trading-engine/backend/media/;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6.2 Enable Site and Restart Nginx

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/trading-engine /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx

# Check status
sudo systemctl status nginx
```

---

## Phase 7: Verify Everything Works (5 min)

### 7.1 Check All Services

```bash
# Check service status
sudo systemctl status gunicorn
sudo systemctl status celery-worker
sudo systemctl status celery-beat
sudo systemctl status nginx

# All should show "active (running)"
```

### 7.2 Test from Server

```bash
# Test Gunicorn directly
curl http://127.0.0.1:8000/

# Test through Nginx
curl http://127.0.0.1/
```

### 7.3 Test from Browser

Open in browser: `http://52.221.248.235` (replace with your IP)

**Expected**: Website should load

### 7.4 Check Celery Logs

```bash
# Check Celery worker logs
sudo tail -f /var/log/celery/worker.log

# Check Celery beat logs
sudo tail -f /var/log/celery/beat.log
```

**Expected**: Should see Celery processing tasks and signals generating

---

## ✅ Deployment Checklist

- [ ] Phase 1: Server setup complete
- [ ] Phase 2: MySQL database created
- [ ] Phase 3: App deployed, migrations run, static files collected
- [ ] Phase 4: Celery worker and beat running
- [ ] Phase 5: Gunicorn running on port 8000
- [ ] Phase 6: Nginx proxying to Gunicorn
- [ ] Phase 7: Website accessible, signals generating

---

## 🔧 Quick Troubleshooting

### Gunicorn not starting
```bash
sudo journalctl -u gunicorn -n 50 --no-pager
# Look for error messages
```

### Celery not working
```bash
sudo journalctl -u celery-worker -n 50 --no-pager
sudo tail -f /var/log/celery/worker.log
```

### Nginx 502 error
```bash
# Check if Gunicorn is listening
sudo ss -ltnp | grep 8000

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Database connection error
```bash
# Test MySQL connection
mysql -u trading_user -p trading_engine_db

# Check .env file has correct DB credentials
cat .env | grep DB_
```

### Static files not loading
```bash
# Recollect static files
cd ~/trading-engine/backend
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py collectstatic --noinput
```

---

## 📝 Important Notes

1. **User**: Use `tradingengine` user or `ubuntu` user (update paths accordingly)
2. **IP Address**: Replace `52.221.248.235` with your actual server IP
3. **Database Password**: Use a strong password for MySQL
4. **SECRET_KEY**: Generate a new one, don't use the example
5. **Settings**: Make sure `settings_production.py` uses MySQL (not PostgreSQL)

---

## 🚀 You're Done!

If all services are running and the website loads, deployment is complete!

**Next Steps (Optional):**
- Setup SSL certificate (requires domain name)
- Configure backups
- Setup monitoring

But for now, **website and signals should be working!** 🎉
