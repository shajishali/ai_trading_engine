"""
Gunicorn configuration file for AI Trading Engine production deployment

This file configures Gunicorn WSGI server with production-optimized settings
"""

import multiprocessing
import os
import time

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Timeout settings
timeout = 30
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "ai_trading_engine"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# SSL (if using direct SSL termination)
# keyfile = "ssl/private.key"
# certfile = "ssl/certificate.crt"

# Performance tuning
worker_tmp_dir = "/dev/shm"
max_requests_jitter = 50

# Health checks
check_config = True

# Environment variables
raw_env = [
    "DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production",
]

# Pre-fork hooks
def on_starting(server):
    server.log.info("Starting AI Trading Engine production server")

def on_reload(server):
    server.log.info("Reloading AI Trading Engine production server")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_exit(server, worker):
    server.log.info("Worker exited (pid: %s)", worker.pid)

def child_exit(server, worker):
    server.log.info("Child exited (pid: %s)", worker.pid)

def on_exit(server):
    server.log.info("Server exiting")

# Custom settings for trading engine
def post_request(worker, req, environ, resp):
    """Log request processing time"""
    if hasattr(req, 'start_time'):
        duration = time.time() - req.start_time
        worker.log.info(f"Request processed in {duration:.3f}s")

def pre_request(worker, req):
    """Record request start time"""
    req.start_time = time.time()
