"""
Phase 5.5: Production Deployment Configuration
Docker and production deployment configurations for ML models
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Production deployment configuration
PRODUCTION_CONFIG = {
    'docker': {
        'base_image': 'tensorflow/tensorflow:2.10.0-gpu',
        'python_version': '3.9',
        'requirements': [
            'tensorflow>=2.10.0',
            'keras>=2.10.0',
            'scikit-learn>=1.1.0',
            'opencv-python>=4.6.0',
            'pillow>=9.0.0',
            'numpy>=1.21.0',
            'pandas>=1.4.0',
            'django>=4.0.0',
            'redis>=4.0.0',
            'celery>=5.0.0',
            'gunicorn>=20.0.0',
            'nginx>=1.20.0'
        ],
        'ports': {
            'web': 8000,
            'redis': 6379,
            'celery': 5555
        },
        'volumes': [
            '/app/media',
            '/app/logs',
            '/app/models'
        ]
    },
    'kubernetes': {
        'namespace': 'trading-signals',
        'replicas': 3,
        'resources': {
            'requests': {
                'cpu': '500m',
                'memory': '1Gi',
                'nvidia.com/gpu': '1'
            },
            'limits': {
                'cpu': '2000m',
                'memory': '4Gi',
                'nvidia.com/gpu': '1'
            }
        },
        'autoscaling': {
            'min_replicas': 2,
            'max_replicas': 10,
            'target_cpu': 70
        }
    },
    'monitoring': {
        'prometheus': {
            'enabled': True,
            'port': 9090,
            'metrics_path': '/metrics'
        },
        'grafana': {
            'enabled': True,
            'port': 3000,
            'dashboards': [
                'ml_model_performance',
                'signal_generation_metrics',
                'system_health'
            ]
        },
        'alerting': {
            'enabled': True,
            'channels': ['email', 'slack', 'webhook']
        }
    },
    'caching': {
        'redis': {
            'enabled': True,
            'host': 'redis',
            'port': 6379,
            'db': 0,
            'ttl': 3600  # 1 hour
        },
        'model_cache': {
            'enabled': True,
            'max_size': 10,  # Max 10 models in memory
            'ttl': 1800  # 30 minutes
        }
    },
    'security': {
        'ssl': {
            'enabled': True,
            'cert_path': '/etc/ssl/certs/trading-signals.crt',
            'key_path': '/etc/ssl/private/trading-signals.key'
        },
        'authentication': {
            'jwt': {
                'enabled': True,
                'secret_key': 'your-secret-key',
                'expiration': 3600  # 1 hour
            }
        },
        'rate_limiting': {
            'enabled': True,
            'requests_per_minute': 100,
            'burst_size': 20
        }
    }
}


def create_dockerfile():
    """Create Dockerfile for production deployment"""
    dockerfile_content = f"""
# Phase 5.5: Production Dockerfile for ML Trading Signals
FROM {PRODUCTION_CONFIG['docker']['base_image']}

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=settings.production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    libpq-dev \\
    nginx \\
    supervisor \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/media/models /app/logs /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

# Copy nginx configuration
COPY nginx.conf /etc/nginx/sites-available/default

# Copy supervisor configuration
COPY supervisor.conf /etc/supervisor/conf.d/supervisord.conf

# Set permissions
RUN chown -R www-data:www-data /app/media /app/logs

# Expose ports
EXPOSE {PRODUCTION_CONFIG['docker']['ports']['web']}

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
"""
    
    return dockerfile_content


def create_docker_compose():
    """Create docker-compose.yml for production deployment"""
    docker_compose_content = f"""
# Phase 5.5: Production Docker Compose for ML Trading Signals
version: '3.8'

services:
  web:
    build: .
    ports:
      - "{PRODUCTION_CONFIG['docker']['ports']['web']}:8000"
    volumes:
      - ./media:/app/media
      - ./logs:/app/logs
      - ./models:/app/models
    environment:
      - DJANGO_SETTINGS_MODULE=settings.production
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - db
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "{PRODUCTION_CONFIG['docker']['ports']['redis']}:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  celery:
    build: .
    command: celery -A trading_signals worker -l info
    volumes:
      - ./media:/app/media
      - ./logs:/app/logs
    environment:
      - DJANGO_SETTINGS_MODULE=settings.production
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - db
    restart: unless-stopped

  celery-beat:
    build: .
    command: celery -A trading_signals beat -l info
    volumes:
      - ./media:/app/media
      - ./logs:/app/logs
    environment:
      - DJANGO_SETTINGS_MODULE=settings.production
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - db
    restart: unless-stopped

  db:
    image: postgres:14
    environment:
      - POSTGRES_DB=trading_signals
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./media:/app/media
      - ./staticfiles:/app/staticfiles
    depends_on:
      - web
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "{PRODUCTION_CONFIG['monitoring']['prometheus']['port']}:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    ports:
      - "{PRODUCTION_CONFIG['monitoring']['grafana']['port']}:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  grafana_data:
"""
    
    return docker_compose_content


def create_kubernetes_manifests():
    """Create Kubernetes manifests for production deployment"""
    deployment_content = f"""
# Phase 5.5: Kubernetes Deployment for ML Trading Signals
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-signals-web
  namespace: {PRODUCTION_CONFIG['kubernetes']['namespace']}
spec:
  replicas: {PRODUCTION_CONFIG['kubernetes']['replicas']}
  selector:
    matchLabels:
      app: trading-signals-web
  template:
    metadata:
      labels:
        app: trading-signals-web
    spec:
      containers:
      - name: web
        image: trading-signals:latest
        ports:
        - containerPort: 8000
        resources:
          requests:
            cpu: {PRODUCTION_CONFIG['kubernetes']['resources']['requests']['cpu']}
            memory: {PRODUCTION_CONFIG['kubernetes']['resources']['requests']['memory']}
            nvidia.com/gpu: {PRODUCTION_CONFIG['kubernetes']['resources']['requests']['nvidia.com/gpu']}
          limits:
            cpu: {PRODUCTION_CONFIG['kubernetes']['resources']['limits']['cpu']}
            memory: {PRODUCTION_CONFIG['kubernetes']['resources']['limits']['memory']}
            nvidia.com/gpu: {PRODUCTION_CONFIG['kubernetes']['resources']['limits']['nvidia.com/gpu']}
        env:
        - name: DJANGO_SETTINGS_MODULE
          value: "settings.production"
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        volumeMounts:
        - name: media-volume
          mountPath: /app/media
        - name: models-volume
          mountPath: /app/models
      volumes:
      - name: media-volume
        persistentVolumeClaim:
          claimName: media-pvc
      - name: models-volume
        persistentVolumeClaim:
          claimName: models-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: trading-signals-service
  namespace: {PRODUCTION_CONFIG['kubernetes']['namespace']}
spec:
  selector:
    app: trading-signals-web
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: trading-signals-hpa
  namespace: {PRODUCTION_CONFIG['kubernetes']['namespace']}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: trading-signals-web
  minReplicas: {PRODUCTION_CONFIG['kubernetes']['autoscaling']['min_replicas']}
  maxReplicas: {PRODUCTION_CONFIG['kubernetes']['autoscaling']['max_replicas']}
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: {PRODUCTION_CONFIG['kubernetes']['autoscaling']['target_cpu']}
"""
    
    return deployment_content


def create_nginx_config():
    """Create nginx configuration for production"""
    nginx_content = f"""
# Phase 5.5: Nginx Configuration for ML Trading Signals
upstream trading_signals {{
    server web:8000;
}}

server {{
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Static files
    location /static/ {{
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }}
    
    # Media files
    location /media/ {{
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";
    }}
    
    # API endpoints
    location /api/ {{
        proxy_pass http://trading_signals;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }}
    
    # WebSocket support
    location /ws/ {{
        proxy_pass http://trading_signals;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    # Main application
    location / {{
        proxy_pass http://trading_signals;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    # Health check
    location /health/ {{
        access_log off;
        proxy_pass http://trading_signals;
    }}
}}
"""
    
    return nginx_content


def create_supervisor_config():
    """Create supervisor configuration for production"""
    supervisor_content = f"""
# Phase 5.5: Supervisor Configuration for ML Trading Signals
[supervisord]
nodaemon=true
user=root
logfile=/app/logs/supervisord.log
pidfile=/var/run/supervisord.pid

[program:nginx]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
stderr_logfile=/app/logs/nginx.err.log
stdout_logfile=/app/logs/nginx.out.log

[program:gunicorn]
command=gunicorn --bind 0.0.0.0:8000 --workers 4 --worker-class gevent --worker-connections 1000 trading_signals.wsgi:application
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/gunicorn.err.log
stdout_logfile=/app/logs/gunicorn.out.log
user=www-data

[program:celery]
command=celery -A trading_signals worker -l info --concurrency=4
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/celery.err.log
stdout_logfile=/app/logs/celery.out.log
user=www-data

[program:celery-beat]
command=celery -A trading_signals beat -l info
directory=/app
autostart=true
autorestart=true
stderr_logfile=/app/logs/celery-beat.err.log
stdout_logfile=/app/logs/celery-beat.out.log
user=www-data
"""
    
    return supervisor_content


def create_prometheus_config():
    """Create Prometheus configuration for monitoring"""
    prometheus_content = f"""
# Phase 5.5: Prometheus Configuration for ML Trading Signals
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

scrape_configs:
  - job_name: 'trading-signals'
    static_configs:
      - targets: ['web:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx:80']
    metrics_path: '/nginx_status'
    scrape_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
"""
    
    return prometheus_content


def create_grafana_dashboard():
    """Create Grafana dashboard configuration"""
    dashboard_content = {
        "dashboard": {
            "title": "ML Trading Signals Dashboard",
            "panels": [
                {
                    "title": "Model Performance",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "ml_model_accuracy",
                            "legendFormat": "Accuracy"
                        },
                        {
                            "expr": "ml_model_inference_time",
                            "legendFormat": "Inference Time (ms)"
                        }
                    ]
                },
                {
                    "title": "Signal Generation Rate",
                    "type": "graph",
                    "targets": [
                        {
                            "expr": "rate(signals_generated_total[5m])",
                            "legendFormat": "Signals/sec"
                        }
                    ]
                },
                {
                    "title": "System Health",
                    "type": "singlestat",
                    "targets": [
                        {
                            "expr": "up",
                            "legendFormat": "System Status"
                        }
                    ]
                }
            ]
        }
    }
    
    return dashboard_content


def create_production_settings():
    """Create production Django settings"""
    settings_content = f"""
# Phase 5.5: Production Django Settings for ML Trading Signals
import os
from .base import *

# Security
DEBUG = False
ALLOWED_HOSTS = ['*']  # Configure with actual domain in production
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key')

# Database
DATABASES = {{
    'default': {{
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'trading_signals'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'password'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }}
}}

# Redis Cache
CACHES = {{
    'default': {{
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
        'OPTIONS': {{
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }}
    }}
}}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = '/app/staticfiles'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = '/app/media'

# Logging
LOGGING = {{
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {{
        'verbose': {{
            'format': '{{levelname}} {{asctime}} {{module}} {{process:d}} {{thread:d}} {{message}}',
            'style': '{{',
        }},
    }},
    'handlers': {{
        'file': {{
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
            'formatter': 'verbose',
        }},
        'console': {{
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }},
    }},
    'root': {{
        'handlers': ['file', 'console'],
        'level': 'INFO',
    }},
    'loggers': {{
        'django': {{
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        }},
        'apps.signals': {{
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        }},
    }},
}}

# ML Model Configuration
ML_MODEL_CACHE_SIZE = {PRODUCTION_CONFIG['caching']['model_cache']['max_size']}
ML_MODEL_CACHE_TTL = {PRODUCTION_CONFIG['caching']['model_cache']['ttl']}

# Performance Monitoring
ENABLE_PERFORMANCE_MONITORING = True
PERFORMANCE_METRICS_RETENTION_DAYS = {PRODUCTION_CONFIG['monitoring']['metrics_retention_days']}

# A/B Testing
AB_TESTING_ENABLED = True
AB_TESTING_MIN_SAMPLE_SIZE = 100

# Automated Retraining
AUTOMATED_RETRAINING_ENABLED = True
RETRAINING_INTERVAL_DAYS = 7
"""
    
    return settings_content


def create_deployment_scripts():
    """Create deployment scripts"""
    deploy_script = """#!/bin/bash
# Phase 5.5: Production Deployment Script for ML Trading Signals

set -e

echo "Starting production deployment..."

# Build Docker images
echo "Building Docker images..."
docker-compose build

# Run database migrations
echo "Running database migrations..."
docker-compose run --rm web python manage.py migrate

# Collect static files
echo "Collecting static files..."
docker-compose run --rm web python manage.py collectstatic --noinput

# Create superuser (optional)
echo "Creating superuser..."
docker-compose run --rm web python manage.py createsuperuser --noinput || true

# Start services
echo "Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 30

# Health check
echo "Performing health check..."
curl -f http://localhost/health/ || exit 1

echo "Deployment completed successfully!"
"""
    
    return deploy_script


def create_kubernetes_deploy_script():
    """Create Kubernetes deployment script"""
    k8s_deploy_script = """#!/bin/bash
# Phase 5.5: Kubernetes Deployment Script for ML Trading Signals

set -e

echo "Starting Kubernetes deployment..."

# Create namespace
kubectl create namespace trading-signals || true

# Apply secrets
kubectl apply -f k8s/secrets.yaml

# Apply configmaps
kubectl apply -f k8s/configmaps.yaml

# Apply persistent volumes
kubectl apply -f k8s/persistent-volumes.yaml

# Apply services
kubectl apply -f k8s/services.yaml

# Apply deployments
kubectl apply -f k8s/deployments.yaml

# Apply ingress
kubectl apply -f k8s/ingress.yaml

# Wait for deployments to be ready
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/trading-signals-web -n trading-signals

# Run database migrations
echo "Running database migrations..."
kubectl exec -n trading-signals deployment/trading-signals-web -- python manage.py migrate

# Health check
echo "Performing health check..."
kubectl get pods -n trading-signals

echo "Kubernetes deployment completed successfully!"
"""
    
    return k8s_deploy_script


# Export all configurations
PRODUCTION_CONFIGS = {
    'dockerfile': create_dockerfile(),
    'docker_compose': create_docker_compose(),
    'kubernetes_manifests': create_kubernetes_manifests(),
    'nginx_config': create_nginx_config(),
    'supervisor_config': create_supervisor_config(),
    'prometheus_config': create_prometheus_config(),
    'grafana_dashboard': create_grafana_dashboard(),
    'production_settings': create_production_settings(),
    'deploy_script': create_deployment_scripts(),
    'k8s_deploy_script': create_kubernetes_deploy_script()
}























