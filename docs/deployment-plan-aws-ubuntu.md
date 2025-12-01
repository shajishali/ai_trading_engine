# AWS Ubuntu Deployment Plan - AI Trading Engine
## Server Specifications
- **OS**: Ubuntu (version to be confirmed)
- **Storage**: 50 GB
- **RAM**: 2 GB
- **IP Address**: Provided by supervisor

---

## Deployment Phases Overview

| Phase | Name | Estimated Time | Status |
|-------|------|----------------|--------|
| **Phase 0** | Pre-Deployment Preparation | 30-60 min | ⏳ Pending |
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
**Status**: ⏳ Pending

#### 0.1 Server Access & Information Gathering
- [ ] Confirm Ubuntu version (Ubuntu 20.04 LTS or 22.04 LTS recommended)
- [ ] Get SSH access credentials (username, password, or SSH key)
- [ ] Confirm IP address and ensure it's accessible
- [ ] Check if firewall ports are open (22, 80, 443, 8000)
- [ ] Verify domain name (if available) or use IP address

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

### 1.1 Initial Server Access
```bash
# Connect to server
ssh username@<IP_ADDRESS>

# Update system packages
sudo apt update
sudo apt upgrade -y
```

### 1.2 Create Deployment User
```bash
# Create dedicated user for deployment
sudo adduser tradingengine
sudo usermod -aG sudo tradingengine

# Switch to new user
su - tradingengine
```

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
```bash
# Navigate to home directory
cd ~

# Clone your repository (replace with your repo URL)
git clone <YOUR_REPOSITORY_URL> trading-engine
cd trading-engine/backend

# Or if using SSH:
# git clone git@github.com:username/repo.git trading-engine
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
```bash
# Create .env file for production
nano .env

# Add all required environment variables:
# SECRET_KEY=your-secret-key-here
# DEBUG=False
# ALLOWED_HOSTS=your-ip-address,your-domain.com
# DATABASE_URL=mysql://tradingengine_user:password@localhost:3306/trading_engine_db
# Or use Django settings format:
# DB_NAME=trading_engine_db
# DB_USER=tradingengine_user
# DB_PASSWORD=your-password-here
# DB_HOST=localhost
# DB_PORT=3306
# REDIS_URL=redis://localhost:6379/0
# CELERY_BROKER_URL=redis://localhost:6379/0
# CELERY_RESULT_BACKEND=redis://localhost:6379/0
# ... (all other environment variables)
```

### 3.5 Update Django Settings for Production
```bash
# Edit settings file
nano ai_trading_engine/settings.py
```

**Update Database Configuration:**
```python
# Replace SQLite configuration with MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='trading_engine_db'),
        'USER': config('DB_USER', default='tradingengine_user'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'isolation_level': 'read committed',
        },
        'CONN_MAX_AGE': 600,  # Connection pooling for MySQL
    }
}

# Ensure:
# - DEBUG = False
# - ALLOWED_HOSTS includes your IP and domain
# - Static files configuration
# - Security settings (CSRF, CORS, etc.)
```

**Alternative: Using mysqlclient or PyMySQL:**
```python
# If using PyMySQL (easier to install), add this at the top of settings.py:
# import pymysql
# pymysql.install_as_MySQLdb()

# Then use same DATABASES configuration above
```

### 3.6 Run Migrations
```bash
# Activate virtual environment
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

### 3.7 Test Application Locally
```bash
# Test Django server
python manage.py runserver 0.0.0.0:8000

# Test from another terminal or browser
curl http://localhost:8000

# If successful, stop the server (Ctrl+C)
```

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
ExecStart=/home/tradingengine/trading-engine/backend/venv/bin/gunicorn \
    --workers 2 \
    --worker-class sync \
    --bind unix:/run/gunicorn.sock \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log \
    ai_trading_engine.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

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
```bash
# Create Nginx site configuration
sudo nano /etc/nginx/sites-available/trading-engine
```

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
    location /static/ {
        alias /home/tradingengine/trading-engine/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files (if any)
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
```bash
# Create backup directory
mkdir -p ~/backups

# Create backup script
nano ~/backup_database.sh
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
- [ ] All services running (Gunicorn, Celery, PostgreSQL, Redis, Nginx)
- [ ] Database migrations completed
- [ ] Static files collected
- [ ] Environment variables configured
- [ ] Firewall configured
- [ ] SSL certificate installed (if using domain)
- [ ] Backup script tested
- [ ] Health check script working
- [ ] Logs are being written

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
- [ ] Database connections working
- [ ] Redis connections working
- [ ] Static files loading
- [ ] No errors in logs

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
```

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

### Database Management
```bash
# Backup
./backup_database.sh

# Restore (if needed)
gunzip < backup_file.sql.gz | mysql -u tradingengine_user -p trading_engine_db
# Or using credentials file:
# gunzip < backup_file.sql.gz | mysql --defaults-file=~/.my.cnf trading_engine_db
```
```

---

## Notes

1. **IP Address**: Replace `YOUR_IP_ADDRESS_OR_DOMAIN` with actual IP or domain
2. **Passwords**: Use strong, unique passwords for all services
3. **Domain**: If you have a domain, configure DNS A record pointing to IP
4. **SSL**: Highly recommended if using a domain name
5. **Monitoring**: Consider setting up basic monitoring alerts
6. **Backups**: Test backup restoration process before going live

---

## Next Steps

Once you review this plan, let me know:
1. Which phase you want to start with
2. Any specific requirements or constraints
3. If you need help with any particular phase
4. If you want me to create specific configuration files

**Ready to proceed?** 🚀

