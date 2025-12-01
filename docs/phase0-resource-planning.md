# Phase 0: Resource Planning & Requirements

## Server Specifications
- **OS**: Ubuntu 20.04 LTS or 22.04 LTS
- **Storage**: 50 GB
- **RAM**: 2 GB
- **CPU**: 1-2 cores (typical for small VPS)

## Storage Requirements Analysis

### Current Local Project Size
- **Backend codebase**: ~3.64 GB (includes virtual environment, ML models, logs)
- **ML Models**: ~50-100 MB (estimated)
- **Static files**: ~10-50 MB (estimated)
- **Database**: Variable (depends on data volume)

### Production Storage Breakdown

| Component | Estimated Size | Notes |
|-----------|---------------|-------|
| **Application Code** | 200-500 MB | Source code, dependencies |
| **Python Virtual Environment** | 500 MB - 1 GB | Installed packages |
| **ML Models** | 50-100 MB | Pre-trained model files (.pkl) |
| **Static Files** | 10-50 MB | Collected static files |
| **Media Files** | Variable | User uploads (if any) |
| **Database** | 1-5 GB | MySQL database (grows over time) |
| **Logs** | 500 MB - 2 GB | Application logs (with rotation) |
| **Backups** | 2-10 GB | Database backups (7-30 day retention) |
| **System Files** | 5-10 GB | OS, system packages |
| **Swap Space** | 2 GB | Virtual memory |
| **Buffer** | 5-10 GB | For growth and temporary files |

**Total Estimated**: 12-30 GB (within 50 GB limit)

### Storage Optimization Recommendations

1. **Log Rotation**: Configure logrotate to keep only 7-14 days of logs
2. **Backup Retention**: Keep only 7-14 days of database backups
3. **Static Files**: Use S3 for static/media files if available (optional)
4. **Database Cleanup**: Regular cleanup of old data
5. **ML Models**: Only deploy production models, remove test models

## Memory (RAM) Requirements - 2GB Total

### Memory Allocation Plan

| Service | Allocated RAM | Notes |
|---------|--------------|-------|
| **System (OS)** | 200-300 MB | Ubuntu base system |
| **MySQL** | 512 MB | `innodb_buffer_pool_size = 512M` |
| **Redis** | 128 MB | `maxmemory 512mb` (with eviction) |
| **Gunicorn (2 workers)** | 400-600 MB | 200-300 MB per worker |
| **Celery Worker** | 200-300 MB | Single worker with `--pool=solo` |
| **Celery Beat** | 50-100 MB | Scheduler process |
| **Nginx** | 50-100 MB | Web server |
| **Buffer/Overhead** | 200-300 MB | For spikes and system processes |

**Total Estimated**: ~1.7-2.0 GB (within 2GB limit)

### Memory Optimization Strategies

1. **Gunicorn Workers**: Limit to 2 workers (formula: (2 × cores) + 1, but constrained by RAM)
2. **Celery Pool**: Use `--pool=solo` instead of prefork (saves ~100-200 MB)
3. **MySQL Buffer Pool**: Set to 512MB (50% of available RAM after system)
4. **Redis Memory Limit**: Set `maxmemory 512mb` with `allkeys-lru` eviction
5. **Swap Space**: Configure 2GB swap file for safety
6. **Connection Pooling**: Use connection pooling to reduce memory per connection

## CPU Requirements

- **Minimum**: 1 core
- **Recommended**: 2 cores
- **Usage Pattern**: 
  - Django: CPU-bound during request processing
  - Celery: CPU-bound during ML model inference
  - MySQL: CPU-bound during queries
  - Redis: Low CPU usage

### CPU Optimization

1. **Worker Processes**: Match workers to CPU cores (2 workers for 2 cores)
2. **Celery Concurrency**: Use `--pool=solo` for single-threaded tasks
3. **Database Indexing**: Ensure proper indexes to reduce CPU usage
4. **Caching**: Use Redis caching to reduce database CPU load

## Network Requirements

### Required Ports

| Port | Service | Protocol | Access |
|------|---------|----------|--------|
| 22 | SSH | TCP | External (restricted) |
| 80 | HTTP | TCP | External |
| 443 | HTTPS | TCP | External |
| 3306 | MySQL | TCP | Localhost only |
| 6379 | Redis | TCP | Localhost only |
| 8000 | Django Dev | TCP | Temporary (remove after Nginx setup) |

### Bandwidth Considerations

- **Inbound**: Low to moderate (API requests, static files)
- **Outbound**: Low to moderate (API calls to external services)
- **Database Replication**: Not applicable (single server)

## Performance Targets

### Response Times
- **API Endpoints**: < 500ms (p95)
- **Static Files**: < 100ms
- **Database Queries**: < 200ms (p95)
- **ML Model Inference**: < 2s (depends on model complexity)

### Throughput
- **Concurrent Users**: 10-50 users
- **Requests per Second**: 10-50 req/s
- **Database Connections**: Max 20 concurrent connections

## Resource Monitoring Plan

### Key Metrics to Monitor

1. **Memory Usage**: `free -h`, `htop`
2. **CPU Usage**: `htop`, `top`
3. **Disk Usage**: `df -h`, `du -sh`
4. **Database Connections**: MySQL `SHOW PROCESSLIST;`
5. **Service Status**: `systemctl status <service>`

### Alert Thresholds

- **Memory**: Alert if > 85% usage
- **CPU**: Alert if > 80% usage for > 5 minutes
- **Disk**: Alert if > 80% usage
- **Database**: Alert if connection pool exhausted
- **Service**: Alert if any service is down

## Scaling Considerations

### When to Scale Up

1. **Memory**: If consistently > 90% usage
2. **CPU**: If consistently > 80% usage
3. **Disk**: If > 80% full
4. **Response Times**: If p95 > 1s consistently
5. **User Growth**: If concurrent users > 50

### Scaling Options

1. **Vertical Scaling**: Upgrade to 4GB RAM, 4 cores
2. **Horizontal Scaling**: Add load balancer + multiple app servers
3. **Database Scaling**: Separate database server
4. **Caching Layer**: Add Redis cluster
5. **CDN**: Use CDN for static files

## Backup Storage Requirements

### Backup Size Estimates

- **Database Backup**: 100-500 MB (compressed)
- **Daily Backups**: 7-14 days retention = 700 MB - 7 GB
- **Weekly Backups**: 4 weeks retention = 400 MB - 2 GB
- **Monthly Backups**: 3 months retention = 300 MB - 1.5 GB

**Total Backup Storage**: 1.4 - 10.5 GB

### Backup Strategy

1. **Daily Backups**: Keep 7-14 days
2. **Weekly Backups**: Keep 4 weeks
3. **Monthly Backups**: Keep 3 months
4. **Off-Server Backups**: Consider S3 or external storage

## Resource Allocation Summary

### Conservative Allocation (Safe)
- **System**: 300 MB
- **MySQL**: 512 MB
- **Redis**: 128 MB
- **Gunicorn**: 400 MB (2 workers × 200 MB)
- **Celery**: 250 MB (worker + beat)
- **Nginx**: 50 MB
- **Buffer**: 360 MB
- **Total**: ~2.0 GB

### Aggressive Allocation (Maximum)
- **System**: 200 MB
- **MySQL**: 512 MB
- **Redis**: 128 MB
- **Gunicorn**: 600 MB (2 workers × 300 MB)
- **Celery**: 300 MB
- **Nginx**: 100 MB
- **Buffer**: 160 MB
- **Total**: ~2.0 GB

## Recommendations

1. ✅ **Start with conservative allocation** and monitor
2. ✅ **Enable swap space** (2GB) for safety
3. ✅ **Configure log rotation** to prevent disk fill
4. ✅ **Set up monitoring** from day one
5. ✅ **Plan for growth** - have scaling plan ready
6. ✅ **Regular cleanup** of old logs and backups
7. ✅ **Database optimization** - proper indexes and query optimization

## Next Steps

After Phase 0 completion:
1. Review and adjust resource allocations based on actual usage
2. Set up monitoring and alerting (Phase 8)
3. Implement backup strategy (Phase 9)
4. Monitor and optimize based on real-world usage patterns

