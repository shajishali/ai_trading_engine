# AWS Ubuntu Deployment Plan - AI Trading Engine

## 🪟 Windows Deployment Guide (PuTTY/PuTTYgen)

**This deployment plan is optimized for Windows users using PuTTY and PuTTYgen.**

### Required Windows Tools
- ✅ **PuTTY** - SSH terminal client (https://www.putty.org/)
- ✅ **PuTTYgen** - SSH key generator (included with PuTTY)
- ✅ **WinSCP** (Recommended) - File transfer GUI (https://winscp.net/)

### Quick Start for Windows Users
1. **Install PuTTY and PuTTYgen** (download from putty.org)
2. **Generate SSH key** with PuTTYgen (see Phase 0.1)
3. **Connect to server** using PuTTY (see Phase 1.1)
4. **Setup key authentication** (see Phase 1.2)
5. **Use WinSCP** for easier file transfers and editing

**All commands in this guide are run through PuTTY terminal window.**

---

## ⚠️ CRITICAL: Pre-Deployment Verification

**Before starting deployment, verify these critical items match your current project structure:**

### Project Structure (VERIFIED)
```
trading-engine/                    # Root directory (cloned from Git)
├── backend/                       # Django application
│   ├── ai_trading_engine/        # Django project settings
│   │   ├── settings.py           # Development settings
│   │   ├── settings_production.py # Production settings (MUST UPDATE for MySQL)
│   │   ├── wsgi.py
│   │   └── celery.py
│   ├── apps/                     # Django apps (analytics, core, data, signals, etc.)
│   ├── manage.py
│   ├── requirements.txt
│   ├── gunicorn.conf.py          # Gunicorn config (uses settings_production)
│   ├── env.production.template   # Environment variables template
│   ├── staticfiles/              # Collected static files (when USE_S3=False)
│   ├── media/                    # Media files
│   ├── logs/                     # Application logs
│   └── templates/                # Backend templates
└── frontend/                      # Frontend templates and static files
    ├── templates/                # Frontend templates
    └── static/                   # Frontend static source files
```

### Critical Configuration Changes Required

1. **Database Configuration** ⚠️ **MUST FIX**
   - `settings_production.py` currently defaults to **PostgreSQL**
   - Deployment plan uses **MySQL**
   - **Action Required**: Update `settings_production.py` database config to MySQL (see Phase 3.5)

2. **Static Files Location**
   - When `USE_S3=False`: Static files collected to `backend/staticfiles/`
   - When `USE_S3=True`: Static files served from S3
   - Nginx configured to serve from `backend/staticfiles/` (local storage)

3. **Templates Location**
   - Templates in both `backend/templates/` and `frontend/templates/`
   - Django settings already configured to use both locations

4. **Settings Module**
   - Production uses: `ai_trading_engine.settings_production`
   - Configured in: `gunicorn.conf.py`

5. **Environment Variables**
   - Use `env.production.template` as base
   - Copy to `.env` in `backend/` directory
   - Fill in all required values

---

## Server Specifications
- **OS**: Ubuntu (version to be confirmed)
- **Storage**: 50 GB
- **RAM**: 2 GB
- **IP Address**: Provided by supervisor

---

## Deployment Phases Overview

| Phase | Name | Estimated Time | Status |
|-------|------|----------------|--------|
| **Phase 0** | Pre-Deployment Preparation | 30-60 min | ✅ In Progress |
| **Phase 1** | Server Initial Setup & Security | 1-2 hours | ⏳ Pending |
| **Phase 2** | Database Setup (MySQL) | 30-45 min | ⏳ Pending |
| **Phase 3** | Application Deployment | 1-2 hours | ⏳ Pending |
| **Phase 4** | Redis Setup | 15-20 min | ⏳ Pending |
| **Phase 5** | Celery Setup | 30-45 min | ⏳ Pending |
| **Phase 6** | Gunicorn Setup | 20-30 min | ⏳ Pending |
| **Phase 7** | Nginx Configuration | 30-45 min | ⏳ Pending |
| **Phase 8** | Monitoring & Logging | 30-45 min | ⏳ Pending |
| **Phase 9** | Backup Strategy | 30 min | ⏳ Pending |
| **Phase 10** | Security Hardening | 30-45 min | ⏳ Pending |
| **Phase 11** | Performance Optimization | 30-45 min | ⏳ Pending |
| **Phase 12** | Final Testing & Go-Live | 1-2 hours | ⏳ Pending |

**Total Estimated Time**: 8-12 hours

---

## Pre-Deployment Checklist

### Phase 0: Pre-Deployment Preparation
**Status**: ✅ In Progress

**Completed Items:**
- ✅ Production .env template created (`backend/env.production.template`)
- ✅ Environment variables documented (`docs/phase0-environment-variables.md`)
- ✅ Resource planning completed (`docs/phase0-resource-planning.md`)
- ✅ Phase 0 checklist created (`docs/phase0-checklist.md`)
- ✅ Database backups available in `backups/` directory

**Pending Items:**
- ⏳ Server access credentials (waiting for supervisor)
- ⏳ IP address confirmation
- ⏳ Git repository cleanup (uncommitted changes)
- ⏳ Final local testing
- ⏳ Update `settings_production.py` to use MySQL (currently defaults to PostgreSQL)

#### 0.1 PuTTY and PuTTYgen Setup (Windows Users)

**Download and Install:**
1. Download PuTTY from: https://www.putty.org/
2. Download PuTTYgen (usually included with PuTTY)
3. Install both applications

**Generate SSH Key Pair with PuTTYgen:**
1. Open **PuTTYgen**
2. Click **Generate** button
3. Move your mouse randomly over the blank area to generate randomness
4. Once generated:
   - **Key comment**: Add a comment like "trading-engine-production"
   - **Key passphrase**: Enter a strong passphrase (optional but recommended)
   - **Key passphrase confirmation**: Re-enter the passphrase
5. Click **Save private key** → Save as `trading-engine-key.ppk` (keep this secure!)
6. Click **Save public key** → Save as `trading-engine-key.pub`
7. **Copy the public key text** from the text box (you'll need this on the server)

**Alternative: Convert Existing SSH Key to PuTTY Format:**
- If you have an existing `id_rsa` key, use PuTTYgen:
  1. Click **Conversions** → **Import key**
  2. Select your `id_rsa` file
  3. Click **Save private key** to save as `.ppk` format

#### 0.2 Server Access & Information Gathering
- [x] **Server IP Address**: `52.221.248.235` ✅
- [x] **SSH Username**: `ubuntu` ✅
- [x] **Key File**: PEM file in Downloads folder ✅
- [ ] Convert PEM to PuTTY format (.ppk) using PuTTYgen
- [ ] Configure PuTTY session with server details
- [ ] Test connection to server
- [ ] Confirm Ubuntu version (Ubuntu 20.04 LTS or 22.04 LTS recommended)
- [ ] Check if firewall ports are open (22, 80, 443, 8000)
- [ ] Verify domain name (if available) or use IP address

**See**: `docs/server-access-setup.md` for detailed setup instructions

#### 0.2 Local Environment Preparation
- [ ] Ensure all code is committed to Git repository
- [ ] Create production-ready `.env` file (without committing secrets)
- [ ] Document all environment variables needed
- [ ] Test application locally one final time
- [ ] Prepare database backup/export if migrating existing data

#### 0.3 Resource Planning
- [ ] Calculate storage requirements (database, logs, static files)
- [ ] Plan for 2GB RAM usage (Django + Celery + Redis + Nginx)
- [ ] Identify which services can run on limited resources
- [ ] Plan for swap space if needed

---

## Phase 1: Server Initial Setup & Security
**Estimated Time**: 1-2 hours  
**Status**: ⏳ Pending

### 1.1 Initial Server Access with PuTTY

**IMPORTANT**: You have a PEM key file. You need to convert it to PuTTY format first!

**Step 1: Convert PEM to PuTTY Format (.ppk)**

1. **Open PuTTYgen**
2. **Click**: Conversions → Import key
3. **Navigate** to your Downloads folder
4. **Select** your PEM file (usually `*.pem`)
5. **Click**: Save private key
6. **Save as**: `trading-engine-key.ppk` (recommended location: `C:\Users\YourUsername\.ssh\`)

**Step 2: Configure PuTTY Session**

1. **Open PuTTY**
2. **Configure Connection:**
   - **Host Name (or IP address)**: `52.221.248.235`
   - **Port**: `22`
   - **Connection type**: `SSH`
3. **Set Username:**
   - Go to **Connection** → **Data**
   - **Auto-login username**: `ubuntu`
4. **Configure SSH Key:**
   - Go to **Connection** → **SSH** → **Auth**
   - Click **Browse** under "Private key file for authentication"
   - Select your `trading-engine-key.ppk` file
5. **Save Session:**
   - Go back to **Session** category
   - Enter name: "Trading Engine Server"
   - Click **Save**
6. **Click Open** to connect
7. **Accept the host key** when prompted (click Yes)

**You should now be connected!**

**See detailed instructions**: `docs/server-access-setup.md`

**Commands to run in PuTTY terminal:**
```bash
# Update system packages
sudo apt update
sudo apt upgrade -y
```

**Tip**: You can increase font size in PuTTY: **Window** → **Appearance** → **Font settings**

### 1.2 Setup SSH Key Authentication and Create Deployment User

**A. Setup SSH Key Authentication (Recommended for Security):**

**On Windows (Your Local Machine):**
1. You should already have your public key from PuTTYgen (the text you copied)
2. If not, open PuTTYgen → Load your `.ppk` key → Copy the public key text

**On Server (via PuTTY terminal):**
```bash
# Create .ssh directory for your current user
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Create authorized_keys file (paste your public key here)
nano ~/.ssh/authorized_keys
# Paste your public key (from PuTTYgen) into this file
# Press Ctrl+X, then Y, then Enter to save

# Set correct permissions
chmod 600 ~/.ssh/authorized_keys
```

**B. Configure PuTTY to Use Your Private Key:**

1. **Open PuTTY**
2. **Load your saved session** (or create new one)
3. Go to **Connection** → **SSH** → **Auth**
4. Click **Browse** under **Private key file for authentication**
5. Select your `trading-engine-key.ppk` file
6. Go back to **Session** and **Save** the session
7. **Open** the connection - it should now use key authentication

**C. Create Deployment User:**
```bash
# Create dedicated user for deployment
sudo adduser tradingengine
# Follow prompts to set password and user info

# Add user to sudo group
sudo usermod -aG sudo tradingengine

# Switch to new user
su - tradingengine
```

**D. Setup SSH Key for Deployment User:**

**On Windows:**
1. Open PuTTYgen → Load your `.ppk` key → Copy public key text again

**On Server (still in PuTTY, now as tradingengine user):**
```bash
# Create .ssh directory
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Add your public key
nano ~/.ssh/authorized_keys
# Paste your public key, save and exit (Ctrl+X, Y, Enter)

# Set permissions
chmod 600 ~/.ssh/authorized_keys
```

**E. Test Key Authentication:**
1. **Close current PuTTY session**
2. **Open new PuTTY session** with your saved configuration
3. **Connect** - it should log in automatically without password
4. If it asks for passphrase, enter the one you set in PuTTYgen

### 1.3 Install Essential Packages
```bash
# Install required system packages
sudo apt install -y \
    python3.10 python3.10-venv python3-pip \
    mysql-server mysql-client \
    nginx \
    redis-server \
    git \
    curl \
    wget \
    build-essential \
    default-libmysqlclient-dev \
    python3-dev \
    supervisor \
    certbot python3-certbot-nginx \
    htop \
    ufw \
    fail2ban
```

### 1.4 Configure Firewall
```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (IMPORTANT - do this first!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow Django development port (temporary, remove after Nginx setup)
sudo ufw allow 8000/tcp

# Check firewall status
sudo ufw status
```

### 1.5 Configure Fail2Ban (Security)
```bash
# Fail2Ban is already installed, configure it
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo systemctl status fail2ban
```

### 1.6 Setup Swap Space (Important for 2GB RAM)
```bash
# Check current swap
free -h

# Create 2GB swap file (adjust based on needs)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make swap permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify
free -h
```

---

## Phase 2: Database Setup (MySQL)
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 2.1 Secure MySQL Installation
```bash
# MySQL should be installed, verify
sudo systemctl status mysql

# Run MySQL secure installation
sudo mysql_secure_installation

# Follow prompts:
# - Set root password (use strong password)
# - Remove anonymous users? Yes
# - Disallow root login remotely? Yes
# - Remove test database? Yes
# - Reload privilege tables? Yes
```

### 2.2 Create Database and User
```bash
# Login to MySQL as root
sudo mysql -u root -p

# In MySQL prompt, run:
CREATE DATABASE trading_engine_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tradingengine_user'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON trading_engine_db.* TO 'tradingengine_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 2.3 Configure MySQL for Production (2GB RAM)
```bash
# Edit MySQL configuration
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf

# Add or update these settings under [mysqld] section:
# [mysqld]
# # Basic settings
# bind-address = 127.0.0.1
# port = 3306
# 
# # Memory settings for 2GB RAM
# innodb_buffer_pool_size = 512M
# innodb_log_file_size = 128M
# innodb_log_buffer_size = 16M
# max_connections = 100
# 
# # Query cache (MySQL 5.7 and below)
# query_cache_type = 1
# query_cache_size = 64M
# query_cache_limit = 2M
# 
# # Table cache
# table_open_cache = 2000
# table_definition_cache = 1400
# 
# # Temporary tables
# tmp_table_size = 64M
# max_heap_table_size = 64M
# 
# # Connection settings
# wait_timeout = 600
# interactive_timeout = 600
# 
# # Logging
# slow_query_log = 1
# slow_query_log_file = /var/log/mysql/slow-query.log
# long_query_time = 2
# 
# # Character set
# character-set-server = utf8mb4
# collation-server = utf8mb4_unicode_ci

# Restart MySQL
sudo systemctl restart mysql

# Verify MySQL is running
sudo systemctl status mysql
```

### 2.4 Test Database Connection
```bash
# Test connection
mysql -u tradingengine_user -p trading_engine_db

# Enter password when prompted
# You should see: mysql> prompt
# Type: EXIT; to exit
```

### 2.5 Install MySQL Client Libraries (for Python)
```bash
# Ensure MySQL client libraries are installed
sudo apt install -y default-libmysqlclient-dev pkg-config

# Verify installation
mysql_config --version
```

---

## Phase 3: Application Deployment
**Estimated Time**: 1-2 hours  
**Status**: ⏳ Pending

### 3.1 Clone Repository

**Option A: Using Git with HTTPS (Easier for PuTTY users):**
```bash
# Navigate to home directory
cd ~

# Clone your repository (replace with your repo URL)
git clone https://github.com/username/repo.git trading-engine
cd trading-engine/backend
```

**Option B: Using Git with SSH Key (If you have GitHub SSH key setup):**
```bash
# Navigate to home directory
cd ~

# Clone using SSH
git clone git@github.com:username/repo.git trading-engine
cd trading-engine/backend
```

**Option C: Upload Project Files Using WinSCP (Alternative Method):**

If Git is not available or you prefer file transfer:

1. **Download WinSCP**: https://winscp.net/eng/download.php
2. **Open WinSCP** and create new session:
   - **File protocol**: SFTP
   - **Host name**: Your server IP
   - **Port number**: 22
   - **User name**: tradingengine
   - **Password**: (or use your .ppk key file)
3. **Connect** to server
4. **Navigate** to `/home/tradingengine/` on server
5. **Upload** your entire project folder from Windows to server
6. **Rename** uploaded folder to `trading-engine` if needed

**After uploading, in PuTTY terminal:**
```bash
cd ~/trading-engine/backend
```

### 3.2 Create Virtual Environment
```bash
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### 3.3 Install Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt

# If requirements.txt doesn't exist, install manually:
pip install django==5.2.5
pip install celery
pip install redis
pip install mysqlclient
# Alternative if mysqlclient fails: pip install pymysql
pip install gunicorn
pip install django-cors-headers
pip install channels
pip install djangorestframework
# ... (add all your dependencies)
```

### 3.4 Configure Environment Variables

**Option A: Edit on Server (using PuTTY terminal):**
```bash
# Copy the production template
cp env.production.template .env

# Edit the .env file with your actual values
nano .env
# Use nano editor:
# - Arrow keys to navigate
# - Type to edit
# - Ctrl+X to exit (will prompt to save)
# - Y to confirm save
# - Enter to confirm filename
```

**Option B: Edit Locally and Upload (Easier for Windows users):**

1. **On Windows**: Open `backend/env.production.template` in Notepad++
2. **Fill in all values** and save as `.env` (make sure it's `.env`, not `.env.txt`)
3. **Open WinSCP** (or use PuTTY's PSCP command)
4. **Upload** the `.env` file to `/home/tradingengine/trading-engine/backend/`

**Using PSCP (PuTTY's command-line tool):**
```powershell
# Open PowerShell on Windows
# Navigate to your project directory
cd "D:\Research Development\backend"

# Upload .env file (replace with your details)
pscp -i "C:\path\to\trading-engine-key.ppk" .env tradingengine@YOUR_IP_ADDRESS:/home/tradingengine/trading-engine/backend/
```

**Using WinSCP (GUI method - easier):**
1. Open WinSCP
2. Connect to server
3. Navigate to `/home/tradingengine/trading-engine/backend/`
4. Drag and drop your `.env` file from Windows

**Required Environment Variables (based on `env.production.template`):**
```bash
# Django Core Settings
DEBUG=False
SECRET_KEY=CHANGE-THIS-TO-A-STRONG-RANDOM-SECRET-KEY
PRODUCTION_SECRET_KEY=CHANGE-THIS-TO-A-STRONG-RANDOM-SECRET-KEY
ALLOWED_HOSTS=YOUR_IP_ADDRESS,YOUR_DOMAIN.com
PRODUCTION_ALLOWED_HOSTS=YOUR_IP_ADDRESS,YOUR_DOMAIN.com

# Database Configuration (MySQL)
DB_ENGINE=django.db.backends.mysql
DB_NAME=trading_engine_db
DB_USER=tradingengine_user
DB_PASSWORD=YOUR_STRONG_PASSWORD_HERE
DB_HOST=localhost
DB_PORT=3306

# Redis Configuration
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=2

# AWS S3 (Optional - set USE_S3=False for local storage)
USE_S3=False

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://yourdomain.com
```

**Generate a strong SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 3.5 Configure Production Settings

**IMPORTANT**: The project uses `settings_production.py` for production. You need to update it to use MySQL instead of PostgreSQL.

**Option A: Edit on Server (using PuTTY terminal):**
```bash
# Edit production settings file
nano ai_trading_engine/settings_production.py
# Use nano editor (see nano tips below)
```

**Option B: Edit Locally and Upload (Easier for Windows users):**
1. **On Windows**: Use WinSCP to download `settings_production.py`
2. **Edit** with Notepad++ or your preferred editor
3. **Upload** back to server using WinSCP

**Nano Editor Tips (for PuTTY users):**
- **Navigate**: Arrow keys
- **Search**: Ctrl+W (type search term, press Enter)
- **Save**: Ctrl+O (press Enter to confirm)
- **Exit**: Ctrl+X (will prompt to save if modified)
- **Cut line**: Ctrl+K
- **Paste**: Ctrl+U

**Update Database Configuration in settings_production.py:**
```python
# Change from PostgreSQL to MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',  # Changed from postgresql
        'NAME': config('DB_NAME', default='trading_engine_db'),
        'USER': config('DB_USER', default='tradingengine_user'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 600,  # Connection pooling for MySQL
    }
}
```

**Note**: The project already uses PyMySQL (configured in `settings.py`), so MySQL should work without additional configuration. The `settings_production.py` file currently defaults to PostgreSQL, so you must change it to MySQL as shown above.

### 3.6 Run Migrations and Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Set production settings module
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production

# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Collect static files
# Note: This collects to backend/staticfiles/ when USE_S3=False
# If USE_S3=True, static files are uploaded to S3
python manage.py collectstatic --noinput

# Verify static files were collected
ls -la staticfiles/
```

### 3.7 Test Application Locally
```bash
# Test Django server with production settings
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py runserver 0.0.0.0:8000

# Test from another terminal or browser
curl http://localhost:8000

# Check if static files are being served
curl http://localhost:8000/static/admin/css/base.css

# If successful, stop the server (Ctrl+C)
```

**Important Project Structure Notes:**
- Project root contains: `backend/` and `frontend/` directories
- Django app is in: `backend/`
- Templates are in: `backend/templates/` and `frontend/templates/`
- Static files (when USE_S3=False): Collected to `backend/staticfiles/`
- Media files: Stored in `backend/media/`
- Production settings: `backend/ai_trading_engine/settings_production.py`

---

## Phase 4: Redis Setup
**Estimated Time**: 15-20 minutes  
**Status**: ⏳ Pending

### 4.1 Configure Redis
```bash
# Redis should be installed, verify
sudo systemctl status redis-server

# Configure Redis for production
sudo nano /etc/redis/redis.conf

# Update settings:
# maxmemory 512mb
# maxmemory-policy allkeys-lru
# save "" (disable persistence for better performance on limited RAM)

# Restart Redis
sudo systemctl restart redis-server

# Test Redis
redis-cli ping
# Should return: PONG
```

### 4.2 Enable Redis on Boot
```bash
sudo systemctl enable redis-server
```

---

## Phase 5: Celery Setup
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 5.1 Create Celery Service Files
```bash
# Create systemd service for Celery Worker
sudo nano /etc/systemd/system/celery-worker.service
```

**Content for celery-worker.service:**
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
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/celery -A ai_trading_engine worker --loglevel=info --pool=solo --pidfile=/var/run/celery/worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Create systemd service for Celery Beat
sudo nano /etc/systemd/system/celery-beat.service
```

**Content for celery-beat.service:**
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
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/celery -A ai_trading_engine beat --loglevel=info --pidfile=/var/run/celery/beat.pid --logfile=/var/log/celery/beat.log
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 5.2 Create Required Directories
```bash
# Create directories for Celery
sudo mkdir -p /var/run/celery
sudo mkdir -p /var/log/celery
sudo chown tradingengine:tradingengine /var/run/celery
sudo chown tradingengine:tradingengine /var/log/celery
```

### 5.3 Enable and Start Celery Services
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable celery-worker.service
sudo systemctl enable celery-beat.service

# Start services
sudo systemctl start celery-worker
sudo systemctl start celery-beat

# Check status
sudo systemctl status celery-worker
sudo systemctl status celery-beat
```

---

## Phase 6: Gunicorn Setup
**Estimated Time**: 20-30 minutes  
**Status**: ⏳ Pending

### 6.1 Create Gunicorn Service
```bash
# Create systemd service for Gunicorn
sudo nano /etc/systemd/system/gunicorn.service
```

**Content for gunicorn.service:**
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
    --bind unix:/run/gunicorn.sock \
    ai_trading_engine.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Note**: The project includes `gunicorn.conf.py` which already has optimized settings. The service uses this config file. Make sure `settings_production.py` is configured for MySQL (see Phase 3.5).

### 6.2 Create Required Directories
```bash
# Create log directory
sudo mkdir -p /var/log/gunicorn
sudo chown tradingengine:tradingengine /var/log/gunicorn
```

### 6.3 Enable and Start Gunicorn
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable gunicorn

# Start service
sudo systemctl start gunicorn

# Check status
sudo systemctl status gunicorn
```

---

## Phase 7: Nginx Configuration
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 7.1 Create Nginx Configuration

**Option A: Create on Server (using PuTTY terminal):**
```bash
# Create Nginx site configuration
sudo nano /etc/nginx/sites-available/trading-engine
```

**Option B: Create Locally and Upload (Easier for Windows users):**
1. **On Windows**: Create new file `trading-engine` (no extension)
2. **Copy** the configuration below into the file
3. **Use WinSCP** to upload to `/etc/nginx/sites-available/trading-engine`
   - Note: You'll need sudo access, so upload to `/home/tradingengine/` first
   - Then in PuTTY: `sudo mv ~/trading-engine /etc/nginx/sites-available/`

**Content for trading-engine:**
```nginx
server {
    listen 80;
    server_name YOUR_IP_ADDRESS_OR_DOMAIN;

    # Increase timeouts for long-running requests
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;

    # Logging
    access_log /var/log/nginx/trading-engine-access.log;
    error_log /var/log/nginx/trading-engine-error.log;

    # Maximum upload size
    client_max_body_size 10M;

    # Static files
    # Note: Static files are collected to backend/staticfiles/ when USE_S3=False
    # If using S3, static files are served from S3 and this location is not used
    location /static/ {
        alias /home/tradingengine/trading-engine/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias /home/tradingengine/trading-engine/backend/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # WebSocket support (for Channels/WebSockets)
    location /ws/ {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 7.2 Enable Site and Test Configuration
```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/trading-engine /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# If test passes, restart Nginx
sudo systemctl restart nginx

# Enable Nginx on boot
sudo systemctl enable nginx
```

### 7.3 Setup SSL Certificate (Optional but Recommended)
```bash
# Install SSL certificate with Let's Encrypt
sudo certbot --nginx -d your-domain.com

# Or if using IP only, skip SSL for now
# Note: Let's Encrypt requires a domain name
```

---

## Phase 8: Monitoring & Logging
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 8.1 Setup Log Rotation
```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/trading-engine
```

**Content:**
```
/var/log/gunicorn/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 tradingengine tradingengine
    sharedscripts
    postrotate
        systemctl reload gunicorn > /dev/null 2>&1 || true
    endscript
}

/var/log/celery/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 tradingengine tradingengine
    sharedscripts
    postrotate
        systemctl reload celery-worker > /dev/null 2>&1 || true
        systemctl reload celery-beat > /dev/null 2>&1 || true
    endscript
}
```

### 8.2 Setup Basic Monitoring
```bash
# Install monitoring tools
sudo apt install -y htop iotop nethogs

# Check system resources
htop

# Monitor disk usage
df -h

# Monitor memory
free -h
```

### 8.3 Create Health Check Script
```bash
# Create health check script
nano ~/health_check.sh
```

**Content:**
```bash
#!/bin/bash
# Health check script for AI Trading Engine

echo "=== System Health Check ==="
echo "Date: $(date)"
echo ""

echo "=== Disk Usage ==="
df -h | grep -E '^/dev/'

echo ""
echo "=== Memory Usage ==="
free -h

echo ""
echo "=== Service Status ==="
systemctl is-active gunicorn && echo "✓ Gunicorn: Active" || echo "✗ Gunicorn: Inactive"
systemctl is-active celery-worker && echo "✓ Celery Worker: Active" || echo "✗ Celery Worker: Inactive"
systemctl is-active celery-beat && echo "✓ Celery Beat: Active" || echo "✗ Celery Beat: Inactive"
systemctl is-active mysql && echo "✓ MySQL: Active" || echo "✗ MySQL: Inactive"
systemctl is-active redis-server && echo "✓ Redis: Active" || echo "✗ Redis: Inactive"
systemctl is-active nginx && echo "✓ Nginx: Active" || echo "✗ Nginx: Inactive"

echo ""
echo "=== Recent Errors (last 10 lines) ==="
tail -10 /var/log/gunicorn/error.log 2>/dev/null || echo "No Gunicorn errors"
```

```bash
# Make executable
chmod +x ~/health_check.sh
```

---

## Phase 9: Backup Strategy
**Estimated Time**: 30 minutes  
**Status**: ⏳ Pending

### 9.1 Database Backup Script

**Option A: Create on Server (using PuTTY terminal):**
```bash
# Create backup directory
mkdir -p ~/backups

# Create backup script
nano ~/backup_database.sh
```

**Option B: Create Locally and Upload (Easier for Windows users):**
1. **On Windows**: Create `backup_database.sh` file
2. **Copy** the script content below into the file
3. **Use WinSCP** to upload to `/home/tradingengine/backup_database.sh`
4. **In PuTTY terminal**, make it executable:
```bash
chmod +x ~/backup_database.sh
```

**Content:**
```bash
#!/bin/bash
# Database backup script for MySQL

BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME=trading_engine_db
DB_USER=tradingengine_user
DB_PASSWORD='YOUR_DB_PASSWORD_HERE'  # Update with actual password

# Create backup
mysqldump -u $DB_USER -p$DB_PASSWORD -h localhost $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: db_backup_$DATE.sql.gz"
```

**Note**: For better security, create a MySQL credentials file instead of password in script:
```bash
# Create MySQL credentials file
nano ~/.my.cnf
```

**Content:**
```ini
[client]
user=tradingengine_user
password=YOUR_PASSWORD_HERE
host=localhost
```

```bash
# Secure the credentials file
chmod 600 ~/.my.cnf

# Update backup script to use credentials file:
# mysqldump --defaults-file=~/.my.cnf $DB_NAME | gzip > $BACKUP_DIR/db_backup_$DATE.sql.gz
```

```bash
# Make executable
chmod +x ~/backup_database.sh

# Test backup
./backup_database.sh
```

### 9.2 Setup Automated Backups
```bash
# Add to crontab for daily backups at 2 AM
crontab -e

# Add this line:
0 2 * * * /home/tradingengine/backup_database.sh >> /home/tradingengine/backup.log 2>&1
```

---

## Phase 10: Security Hardening
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 10.1 Update Django Security Settings
```python
# In settings.py, ensure these are set:
SECURE_SSL_REDIRECT = True  # If using SSL
SESSION_COOKIE_SECURE = True  # If using SSL
CSRF_COOKIE_SECURE = True  # If using SSL
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # If using SSL
SECURE_HSTS_INCLUDE_SUBDOMAINS = True  # If using SSL
```

### 10.2 Restrict Database Access
```bash
# MySQL is already configured to bind to localhost only
# Verify in MySQL config:
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf

# Ensure:
# bind-address = 127.0.0.1

# Verify MySQL users can only connect from localhost
sudo mysql -u root -p
# Run: SELECT user, host FROM mysql.user;
# All users should have 'localhost' or '127.0.0.1' as host
```

### 10.3 Secure File Permissions
```bash
# Set proper permissions
chmod 600 ~/.env
chmod 700 ~/trading-engine
chmod 600 ~/backups/*.sql.gz
```

---

## Phase 11: Performance Optimization
**Estimated Time**: 30-45 minutes  
**Status**: ⏳ Pending

### 11.1 Optimize Gunicorn Workers
```bash
# For 2GB RAM, use 2 workers (adjust based on monitoring)
# Already configured in gunicorn.service
# Formula: (2 * CPU cores) + 1, but with 2GB RAM, 2 workers is safer
```

### 11.2 Optimize MySQL
```bash
# Already configured in Phase 2
# Monitor and adjust based on actual usage

# Check MySQL status
sudo mysqladmin -u root -p status

# Check MySQL variables
mysql -u root -p -e "SHOW VARIABLES LIKE 'innodb_buffer_pool_size';"
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"
```

### 11.3 Enable Caching
```python
# In settings.py, use Redis for caching:
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### 11.4 Static Files Optimization
```bash
# Ensure static files are collected
python manage.py collectstatic --noinput

# Nginx already configured to serve static files efficiently
```

---

## Phase 12: Final Testing & Go-Live
**Estimated Time**: 1-2 hours  
**Status**: ⏳ Pending

### 12.1 Pre-Launch Checklist
- [ ] All services running (Gunicorn, Celery, MySQL, Redis, Nginx)
- [ ] Database migrations completed
- [ ] Static files collected to `backend/staticfiles/` (or uploaded to S3 if USE_S3=True)
- [ ] Environment variables configured in `.env` file
- [ ] `settings_production.py` updated to use MySQL (not PostgreSQL)
- [ ] Firewall configured
- [ ] SSL certificate installed (if using domain)
- [ ] Backup script tested
- [ ] Health check script working
- [ ] Logs are being written to `backend/logs/`
- [ ] Templates loading from both `backend/templates/` and `frontend/templates/`

### 12.2 Functional Testing
```bash
# Test from server
curl http://localhost
curl http://localhost/api/signals/

# Test from external machine
curl http://YOUR_IP_ADDRESS
```

### 12.3 Performance Testing
```bash
# Monitor resources
htop

# Check service logs
sudo journalctl -u gunicorn -f
sudo journalctl -u celery-worker -f
sudo journalctl -u celery-beat -f
```

### 12.4 Final Verification
- [ ] Application accessible via IP/domain
- [ ] All API endpoints working
- [ ] Celery tasks executing
- [ ] MySQL database connections working (verify not using PostgreSQL)
- [ ] Redis connections working
- [ ] Static files loading from `backend/staticfiles/` (or S3 if configured)
- [ ] Media files accessible from `backend/media/`
- [ ] Templates loading correctly (from both backend and frontend directories)
- [ ] No errors in logs (`backend/logs/` directory)
- [ ] Gunicorn using `settings_production` module

---

## Post-Deployment Maintenance

### Daily Tasks
- Monitor disk usage: `df -h`
- Check service status: `systemctl status gunicorn celery-worker celery-beat`
- Review error logs: `tail -f /var/log/gunicorn/error.log`

### Weekly Tasks
- Review backup logs
- Check disk space
- Review application logs for errors
- Update system packages: `sudo apt update && sudo apt upgrade`

### Monthly Tasks
- Review and rotate old logs
- Check database size and optimize if needed
- Review security updates
- Test backup restoration

---

## Troubleshooting Guide

### PuTTY Connection Issues

**Problem: "Network error: Connection refused"**
- Check if server IP is correct
- Verify port 22 is open
- Check if server is running
- Try pinging the server IP from Windows: `ping <IP_ADDRESS>`

**Problem: "Server unexpectedly closed network connection"**
- Check server firewall settings
- Verify SSH service is running on server
- Check server logs

**Problem: "Authentication failed"**
- Verify username is correct
- If using password: Check password is correct
- If using key: Verify key file path in PuTTY → Connection → SSH → Auth
- Make sure public key is in `~/.ssh/authorized_keys` on server

**Problem: "PuTTY window closes immediately after opening"**
- Check PuTTY → Connection → Data → Auto-login username is set
- Verify key file is correct
- Check PuTTY → Session → Logging (enable to see errors)

**Problem: "Permission denied (publickey)"**
- Verify public key is in `~/.ssh/authorized_keys` on server
- Check file permissions: `chmod 600 ~/.ssh/authorized_keys`
- Verify private key file (.ppk) is correct in PuTTY settings

### Service Won't Start
```bash
# Check service status
sudo systemctl status <service-name>

# Check logs
sudo journalctl -u <service-name> -n 50

# Check configuration
sudo systemctl daemon-reload
```

### Database Connection Issues
```bash
# Test connection
mysql -u tradingengine_user -p trading_engine_db

# Check MySQL status
sudo systemctl status mysql

# Check MySQL logs
sudo tail -f /var/log/mysql/error.log
sudo tail -f /var/log/mysql/slow-query.log
```

### High Memory Usage
```bash
# Check memory usage
free -h
htop

# Reduce Gunicorn workers if needed
# Reduce Celery concurrency
# Check for memory leaks in application
```

### Disk Space Issues
```bash
# Check disk usage
df -h
du -sh ~/backups/*
du -sh /var/log/*

# Clean old logs
sudo journalctl --vacuum-time=7d
```

**Tip**: Use WinSCP to visually browse directories and identify large files/folders

---

## Resource Allocation (2GB RAM)

### Recommended Allocation:
- **System**: 200-300 MB
- **MySQL**: 512 MB (innodb_buffer_pool_size)
- **Redis**: 128 MB
- **Gunicorn (2 workers)**: 400-600 MB
- **Celery Worker**: 200-300 MB
- **Celery Beat**: 50-100 MB
- **Nginx**: 50-100 MB
- **Buffer**: 200-300 MB

**Total**: ~1.7-2.0 GB (within 2GB limit)

### Optimization Tips:
1. Use `--pool=solo` for Celery (already configured)
2. Limit Gunicorn workers to 2
3. Use Redis with memory limits
4. Monitor and adjust based on actual usage

---

## Quick Reference Commands

### PuTTY Connection
1. **Open PuTTY** → Load saved session → Click **Open**
2. **Enter passphrase** if using key authentication
3. **You're connected!** All commands below run in PuTTY terminal

### Service Management
```bash
# Start/Stop/Restart services
sudo systemctl start|stop|restart gunicorn
sudo systemctl start|stop|restart celery-worker
sudo systemctl start|stop|restart celery-beat
sudo systemctl start|stop|restart nginx
sudo systemctl start|stop|restart mysql
sudo systemctl start|stop|restart redis-server

# Check status
sudo systemctl status <service-name>

# View logs
sudo journalctl -u <service-name> -f
# Press Ctrl+C to exit log view
```

**Tip**: Use WinSCP to view log files with a GUI editor instead of command line

### Application Management
```bash
# Activate virtual environment
cd ~/trading-engine/backend
source venv/bin/activate

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser
```

**Tip**: All these commands run in PuTTY terminal. Make sure you're in the correct directory (`~/trading-engine/backend`) and virtual environment is activated.

### Database Management
```bash
# Backup
./backup_database.sh

# Restore (if needed)
gunzip < backup_file.sql.gz | mysql -u tradingengine_user -p trading_engine_db
# Or using credentials file:
# gunzip < backup_file.sql.gz | mysql --defaults-file=~/.my.cnf trading_engine_db
```

### File Management with WinSCP
- **View logs**: Connect with WinSCP → Navigate to `/home/tradingengine/trading-engine/backend/logs/` → Right-click → Edit
- **Edit config files**: Navigate to file → Right-click → Edit → WinSCP opens in Notepad++
- **Upload files**: Drag and drop from Windows to server
- **Download files**: Drag and drop from server to Windows
- **Set permissions**: Right-click file → Properties → Change permissions
```

---

## Windows Tools for Deployment

### Required Tools
1. **PuTTY** - SSH terminal client
   - Download: https://www.putty.org/
   - Used for: Command-line access to server

2. **PuTTYgen** - SSH key generator
   - Usually included with PuTTY
   - Used for: Generating SSH key pairs

3. **WinSCP** (Recommended) - File transfer client
   - Download: https://winscp.net/eng/download.php
   - Used for: Uploading/downloading files, editing files with GUI
   - Alternative: Use PSCP (command-line, included with PuTTY)

### PuTTY Tips for Windows Users

**Copy/Paste in PuTTY:**
- **Copy**: Select text with mouse (automatically copies)
- **Paste**: Right-click in PuTTY window (or Shift+Insert)

**Saving PuTTY Sessions:**
- Configure all settings (host, port, username, key file)
- Go to **Session** → Enter name → Click **Save**
- Next time: Load session → Click **Open**

**PuTTY Window Settings:**
- Increase font: **Window** → **Appearance** → **Font settings**
- Increase window size: **Window** → **Appearance** → **Window**
- Enable scrollback: **Window** → **Selection** → Increase scrollback lines

**Using WinSCP for File Editing:**
- Connect to server with WinSCP
- Right-click any file → **Edit**
- WinSCP will download, open in Notepad++, and upload when saved
- Much easier than using `nano` or `vi` for Windows users

**Using PSCP (Command-line file transfer):**
```powershell
# Upload file
pscp -i "C:\path\to\key.ppk" localfile.txt user@server:/remote/path/

# Download file
pscp -i "C:\path\to\key.ppk" user@server:/remote/path/file.txt ./
```

---

## Notes

1. **IP Address**: Replace `YOUR_IP_ADDRESS_OR_DOMAIN` with actual IP or domain
2. **Passwords**: Use strong, unique passwords for all services
3. **Domain**: If you have a domain, configure DNS A record pointing to IP
4. **SSL**: Highly recommended if using a domain name
5. **Monitoring**: Consider setting up basic monitoring alerts
6. **Backups**: Test backup restoration process before going live
7. **Project Structure**: 
   - Root directory contains `backend/` and `frontend/` folders
   - Django application is in `backend/`
   - Static files collected to `backend/staticfiles/` when USE_S3=False
   - Templates in both `backend/templates/` and `frontend/templates/`
8. **Database**: The deployment plan uses MySQL, but `settings_production.py` defaults to PostgreSQL. **You must update `settings_production.py` to use MySQL** (see Phase 3.5)
9. **Settings Module**: Production uses `ai_trading_engine.settings_production` (configured in `gunicorn.conf.py`)
10. **Static Files**: If `USE_S3=True` in `.env`, static files are served from S3. If `USE_S3=False`, they're served from `backend/staticfiles/`
11. **Windows Users**: This deployment plan is optimized for Windows users using PuTTY/PuTTYgen. All SSH commands are run through PuTTY terminal. Use WinSCP for easier file transfers and editing.

---

## Next Steps

Once you review this plan, let me know:
1. Which phase you want to start with
2. Any specific requirements or constraints
3. If you need help with any particular phase
4. If you want me to create specific configuration files

**Ready to proceed?** 🚀

