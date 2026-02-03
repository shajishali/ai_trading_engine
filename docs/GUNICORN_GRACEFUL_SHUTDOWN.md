# Gunicorn Graceful Shutdown (Stop Timeout Fix)

## What the logs mean

When you see in `journalctl -u gunicorn`:

- **`State 'stop-sigterm' timed out. Killing.`** – systemd sent SIGTERM to gunicorn but the process did not exit within the stop timeout, so systemd sent SIGKILL.
- **`Failed with result 'timeout'.`** – The service is marked as having failed because of that timeout (even though it was then restarted).
- **`Failed to kill control group ... Invalid argument`** – Usually harmless; it can occur when the cgroup is already torn down.

So the service **does** come back up after restart; the “failure” is only that the **stop** phase timed out.

## Why it happens

1. On `systemctl restart gunicorn` (or stop/start), systemd sends **SIGTERM** to gunicorn.
2. Gunicorn tries to shut down gracefully: it stops accepting new work and waits for workers to finish their current requests (up to **graceful_timeout** in gunicorn config).
3. If workers are busy (e.g. handling `/signals/`, `/dashboard/`, or slow DB/Redis), they may not exit within systemd’s **stop timeout** (default **90 seconds**).
4. After that timeout, systemd sends **SIGKILL** and you see “timed out. Killing” and “Failed with result 'timeout'”.

So timeouts usually happen when the server is under load or requests are slow at the moment of restart.

## Fix: give systemd more time for shutdown

On the **production server**, edit the gunicorn unit and add an explicit stop timeout so systemd waits long enough for graceful shutdown:

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

In the **`[Service]`** section, add (or adjust):

```ini
[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/trading-engine/backend
Environment="PATH=/home/ubuntu/trading-engine/backend/venv/bin"
Environment="DJANGO_SETTINGS_MODULE=ai_trading_engine.settings_production"
ExecStart=...
Restart=always
RestartSec=10

# Allow up to 2 minutes for graceful shutdown before SIGKILL
TimeoutStopSec=120
```

Use whatever user/path you actually use (e.g. `tradingengine` and `/home/tradingengine/trading-engine/backend`). Then:

```bash
sudo systemctl daemon-reload
```

No need to restart gunicorn just for this; the new timeout applies the next time systemd stops the service.

## Optional: Gunicorn graceful timeout

Your `gunicorn.conf.py` should have something like:

```python
timeout = 30
graceful_timeout = 30
```

- **timeout** – max seconds a worker may spend on a single request before being killed.
- **graceful_timeout** – max seconds gunicorn waits for workers to finish current requests after SIGTERM.

If you increase **TimeoutStopSec** in systemd (e.g. to 120), ensure **graceful_timeout** is less than that (e.g. 60) so gunicorn has time to clean up before systemd’s timeout.

## Summary

| Setting            | Where        | Purpose |
|--------------------|-------------|---------|
| **TimeoutStopSec** | systemd     | How long systemd waits after SIGTERM before SIGKILL (default 90s). Set to 120 or 180 to avoid stop timeouts. |
| **graceful_timeout** | gunicorn  | How long gunicorn waits for workers to finish after SIGTERM. Keep &lt; TimeoutStopSec. |

After adding **TimeoutStopSec=120** (or 180) and reloading systemd, future `systemctl restart gunicorn` or deploys should stop cleanly without “State 'stop-sigterm' timed out” and “Failed with result 'timeout'”, as long as requests finish within the graceful window.
