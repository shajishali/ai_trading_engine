#!/bin/bash

# Production Deployment Script for Database-Driven Signal Generation System
# Phase 3: Complete production deployment automation

set -e  # Exit on any error

# Configuration
APP_NAME="ai_trading_engine"
APP_USER="trading"
APP_DIR="/opt/$APP_NAME"
VENV_DIR="/opt/$APP_NAME/venv"
LOG_DIR="/var/log/$APP_NAME"
BACKUP_DIR="/var/backups/$APP_NAME"
NGINX_DIR="/etc/nginx/sites-available"
SYSTEMD_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    apt-get update
    apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        postgresql \
        postgresql-contrib \
        redis-server \
        nginx \
        supervisor \
        git \
        curl \
        wget \
        unzip \
        build-essential \
        libpq-dev \
        libssl-dev \
        libffi-dev \
        libjpeg-dev \
        libpng-dev \
        libfreetype6-dev \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev
    
    log_success "System dependencies installed"
}

# Create application user
create_app_user() {
    log_info "Creating application user..."
    
    if ! id "$APP_USER" &>/dev/null; then
        useradd -r -s /bin/bash -d "$APP_DIR" -m "$APP_USER"
        log_success "Application user created: $APP_USER"
    else
        log_info "Application user already exists: $APP_USER"
    fi
}

# Create directories
create_directories() {
    log_info "Creating application directories..."
    
    mkdir -p "$APP_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$APP_DIR/static"
    mkdir -p "$APP_DIR/media"
    mkdir -p "$APP_DIR/venv"
    
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
    chown -R "$APP_USER:$APP_USER" "$BACKUP_DIR"
    
    log_success "Directories created"
}

# Setup PostgreSQL
setup_postgresql() {
    log_info "Setting up PostgreSQL..."
    
    # Start PostgreSQL
    systemctl start postgresql
    systemctl enable postgresql
    
    # Create database and user
    sudo -u postgres psql << EOF
CREATE DATABASE ai_trading_engine_prod;
CREATE USER trading_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE ai_trading_engine_prod TO trading_user;
ALTER USER trading_user CREATEDB;
EOF
    
    log_success "PostgreSQL configured"
}

# Setup Redis
setup_redis() {
    log_info "Setting up Redis..."
    
    # Configure Redis
    cat > /etc/redis/redis.conf << EOF
# Redis configuration for production
bind 127.0.0.1
port 6379
timeout 300
tcp-keepalive 60
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
    
    systemctl restart redis-server
    systemctl enable redis-server
    
    log_success "Redis configured"
}

# Setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."
    
    cd "$APP_DIR"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    log_success "Python environment configured"
}

# Configure Django settings
configure_django() {
    log_info "Configuring Django settings..."
    
    # Create production settings file
    cat > "$APP_DIR/ai_trading_engine/settings_production.py" << 'EOF'
# Production settings for AI Trading Engine
import os
from pathlib import Path

# Import base settings
from .settings import *

# Production overrides
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com', 'localhost']

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ai_trading_engine_prod',
        'USER': 'trading_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Redis configuration
REDIS_URL = 'redis://localhost:6379/0'
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'

# Security settings
SECRET_KEY = 'your-production-secret-key-here'
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static files
STATIC_ROOT = '/opt/ai_trading_engine/static'
MEDIA_ROOT = '/opt/ai_trading_engine/media'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/ai_trading_engine/django.log',
            'maxBytes': 1024*1024*10,
            'backupCount': 5,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
EOF
    
    log_success "Django settings configured"
}

# Setup database
setup_database() {
    log_info "Setting up database..."
    
    cd "$APP_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Set Django settings
    export DJANGO_SETTINGS_MODULE="ai_trading_engine.settings_production"
    
    # Run migrations
    python manage.py migrate
    
    # Create superuser (optional)
    echo "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.create_superuser('admin', 'admin@example.com', 'admin123')" | python manage.py shell
    
    # Collect static files
    python manage.py collectstatic --noinput
    
    log_success "Database setup completed"
}

# Configure Nginx
configure_nginx() {
    log_info "Configuring Nginx..."
    
    # Create Nginx configuration
    cat > "$NGINX_DIR/$APP_NAME" << EOF
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL configuration (you'll need to add your SSL certificates)
    # ssl_certificate /path/to/your/certificate.crt;
    # ssl_certificate_key /path/to/your/private.key;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # Static files
    location /static/ {
        alias /opt/$APP_NAME/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /opt/$APP_NAME/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Django application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Health check endpoint
    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }
}
EOF
    
    # Enable site
    ln -sf "$NGINX_DIR/$APP_NAME" "/etc/nginx/sites-enabled/$APP_NAME"
    rm -f /etc/nginx/sites-enabled/default
    
    # Test configuration
    nginx -t
    
    # Restart Nginx
    systemctl restart nginx
    systemctl enable nginx
    
    log_success "Nginx configured"
}

# Create systemd services
create_systemd_services() {
    log_info "Creating systemd services..."
    
    # Django application service
    cat > "$SYSTEMD_DIR/$APP_NAME.service" << EOF
[Unit]
Description=AI Trading Engine Django Application
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
ExecStart=$VENV_DIR/bin/gunicorn --bind 127.0.0.1:8000 --workers 4 --timeout 300 ai_trading_engine.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery worker service
    cat > "$SYSTEMD_DIR/$APP_NAME-celery.service" << EOF
[Unit]
Description=AI Trading Engine Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
ExecStart=$VENV_DIR/bin/celery -A ai_trading_engine worker -l info --concurrency=4
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Celery beat service
    cat > "$SYSTEMD_DIR/$APP_NAME-celery-beat.service" << EOF
[Unit]
Description=AI Trading Engine Celery Beat Scheduler
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
ExecStart=$VENV_DIR/bin/celery -A ai_trading_engine beat -l info
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd
    systemctl daemon-reload
    
    log_success "Systemd services created"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    # Start and enable services
    systemctl start "$APP_NAME"
    systemctl enable "$APP_NAME"
    
    systemctl start "$APP_NAME-celery"
    systemctl enable "$APP_NAME-celery"
    
    systemctl start "$APP_NAME-celery-beat"
    systemctl enable "$APP_NAME-celery-beat"
    
    # Check service status
    systemctl status "$APP_NAME" --no-pager
    systemctl status "$APP_NAME-celery" --no-pager
    systemctl status "$APP_NAME-celery-beat" --no-pager
    
    log_success "Services started"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Create monitoring script
    cat > "$APP_DIR/monitor.sh" << 'EOF'
#!/bin/bash

# Monitoring script for AI Trading Engine
LOG_FILE="/var/log/ai_trading_engine/monitor.log"

# Check Django application
if ! systemctl is-active --quiet ai_trading_engine; then
    echo "$(date): Django application is not running" >> "$LOG_FILE"
    systemctl restart ai_trading_engine
fi

# Check Celery worker
if ! systemctl is-active --quiet ai_trading_engine-celery; then
    echo "$(date): Celery worker is not running" >> "$LOG_FILE"
    systemctl restart ai_trading_engine-celery
fi

# Check Celery beat
if ! systemctl is-active --quiet ai_trading_engine-celery-beat; then
    echo "$(date): Celery beat is not running" >> "$LOG_FILE"
    systemctl restart ai_trading_engine-celery-beat
fi

# Check database connection
cd /opt/ai_trading_engine
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production
python manage.py check --deploy

echo "$(date): Health check completed" >> "$LOG_FILE"
EOF
    
    chmod +x "$APP_DIR/monitor.sh"
    
    # Add to crontab
    echo "*/5 * * * * $APP_DIR/monitor.sh" | crontab -u "$APP_USER" -
    
    log_success "Monitoring setup completed"
}

# Setup backup
setup_backup() {
    log_info "Setting up backup..."
    
    # Create backup script
    cat > "$APP_DIR/backup.sh" << 'EOF'
#!/bin/bash

# Backup script for AI Trading Engine
BACKUP_DIR="/var/backups/ai_trading_engine"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
pg_dump -h localhost -U trading_user -d ai_trading_engine_prod > "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Remove old backups (keep last 30 days)
find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +30 -delete

echo "$(date): Backup completed: $BACKUP_FILE.gz" >> /var/log/ai_trading_engine/backup.log
EOF
    
    chmod +x "$APP_DIR/backup.sh"
    
    # Add to crontab (daily at 2 AM)
    echo "0 2 * * * $APP_DIR/backup.sh" | crontab -u "$APP_USER" -
    
    log_success "Backup setup completed"
}

# Main deployment function
main() {
    log_info "Starting production deployment..."
    
    check_root
    install_dependencies
    create_app_user
    create_directories
    setup_postgresql
    setup_redis
    setup_python_env
    configure_django
    setup_database
    configure_nginx
    create_systemd_services
    start_services
    setup_monitoring
    setup_backup
    
    log_success "Production deployment completed successfully!"
    log_info "Application is running at: http://your-domain.com"
    log_info "Admin panel: http://your-domain.com/admin (admin/admin123)"
    log_info "Logs: $LOG_DIR"
    log_info "Backups: $BACKUP_DIR"
    
    echo ""
    log_info "Next steps:"
    log_info "1. Configure SSL certificates"
    log_info "2. Update domain name in Nginx configuration"
    log_info "3. Set up monitoring and alerting"
    log_info "4. Configure firewall rules"
    log_info "5. Test all functionality"
}

# Run main function
main "$@"