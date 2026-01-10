# Signals Not Loading - Production Fix

## Problem
Signals were not loading in production. The API was returning `success: true` but with empty `signals: []` and `count: 0`. This was caused by:

1. **Stale empty cache**: The API was returning cached empty results even when signals existed in the database
2. **Cache logic issue**: Empty cache results were being returned before checking the database
3. **No diagnostic tools**: There was no way to check database status or clear cache

## Fixes Applied

### 1. Fixed Cache Logic (backend/apps/signals/views.py)

**Before:**
- API returned any cached data, even if it was empty
- Empty cache results blocked fresh database queries

**After:**
- API only returns cached data if it contains signals (`count > 0`)
- Empty cache results are cleared automatically and database is queried
- Empty results are cached for only 60 seconds (instead of 5 minutes) to allow quick recovery

**Changes:**
```python
# Only return cached data if it has signals
if cached_data and cached_data.get('count', 0) > 0:
    # Return cached data
elif cached_data and cached_data.get('count', 0) == 0:
    # Clear empty cache and check database
    cache.delete(cache_key)
```

### 2. Added Better Logging

Added diagnostic logging to identify when signals are not found:
- Logs query parameters (symbol, signal_type, is_valid, limit)
- Logs number of signals found
- Logs total signals in database when query returns empty (valid/invalid breakdown)

### 3. Added Cache Clearing Endpoint

**Endpoint:** `POST /signals/api/clear-cache/`

Clears all signal-related cache keys to force fresh database queries.

**Usage:**
```bash
curl -X POST http://your-domain.com/signals/api/clear-cache/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Cleared X cache key(s)",
  "cleared_count": X
}
```

### 4. Added Diagnostic Endpoint

**Endpoint:** `GET /signals/api/diagnostic/`

Provides comprehensive diagnostic information about signals database and cache status.

**Usage:**
```bash
curl http://your-domain.com/signals/api/diagnostic/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "database": {
    "status": "connected",
    "total_signals": 100,
    "valid_signals": 5,
    "invalid_signals": 95,
    "executed_signals": 10
  },
  "cache": {
    "exists": true,
    "count": 5,
    "cached_at": "2026-01-10T03:54:07.879978+00:00"
  },
  "recent_signals": [...],
  "timestamp": "2026-01-10T03:54:07.879978+00:00"
}
```

## How to Verify the Fix

### 1. Check Current Status
```bash
curl http://your-domain.com/signals/api/diagnostic/
```

This will show:
- How many signals are in the database
- How many are valid
- Cache status

### 2. Clear Cache (if needed)
```bash
curl -X POST http://your-domain.com/signals/api/clear-cache/
```

### 3. Verify Signals Load
After clearing cache, check the signals API:
```bash
curl http://your-domain.com/signals/api/signals/
```

## Root Cause Analysis

The issue occurred because:

1. **Cache was set with empty results**: At some point, the API cached an empty result (when there were no signals)
2. **Cache took precedence**: The API logic returned cached data before checking the database
3. **Background refresh failed silently**: The background cache refresh was failing silently, so empty cache persisted

## Prevention

The fix prevents this issue by:
- Not returning empty cached results
- Clearing empty cache automatically
- Caching empty results for shorter duration (60s vs 300s)
- Adding diagnostic tools to identify issues quickly

## Next Steps

1. **Verify signals are generating**: Check if signal generation is running in production
   ```bash
   # Check logs for signal generation
   tail -f /var/log/signals/generate.log
   ```

2. **Generate signals if needed**: If no valid signals exist, generate them:
   ```bash
   curl -X POST http://your-domain.com/signals/api/generate/ \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTCUSDT"}'
   ```

3. **Monitor cache**: Use the diagnostic endpoint periodically to monitor cache status

## Files Modified

- `backend/apps/signals/views.py`: Fixed cache logic, added logging, added diagnostic endpoints
- `backend/apps/signals/urls.py`: Added routes for cache clearing and diagnostic endpoints

