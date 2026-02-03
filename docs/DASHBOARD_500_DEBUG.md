# Debugging 500 Server Error on Dashboard

## If `/dashboard/` returns 500

The dashboard view now logs the full exception before re-raising, so the **cause** will appear in your server logs.

### 1. Check Gunicorn logs (recommended)

On the server:

```bash
# Last 100 lines of gunicorn service (includes Python tracebacks)
sudo journalctl -u gunicorn -n 100 --no-pager

# Or if using a file log
tail -100 /path/to/trading-engine/backend/logs/gunicorn_error.log
```

Look for lines like:

- `Dashboard view error: ...`
- Full Python traceback (e.g. `AttributeError`, `OperationalError`, `DoesNotExist`)

### 2. Common causes and fixes

| Cause | What you see | Fix |
|-------|----------------|-----|
| **Orphaned signal** | `AttributeError: 'NoneType' object has no attribute 'name'` (or `'symbol'`) | The view now skips signals whose `symbol` or `signal_type` was deleted; deploy the updated `apps/dashboard/views.py`. To clean data: remove or fix `TradingSignal` rows with missing symbol/signal_type. |
| **Database** | `OperationalError`, `InterfaceError`, connection errors | Check DB is up, migrations applied, and `DATABASES` / env vars correct in production settings. |
| **Missing migration** | `DoesNotExist`, `ProgrammingError`, or column/table errors | Run `python manage.py migrate` on the server. |
| **Template / static** | `TemplateDoesNotExist`, `TemplateSyntaxError` | Ensure `frontend/templates` is in `TEMPLATES[]['DIRS']` and static files are collected. |

### 3. Code changes that help avoid 500s

- **Dashboard view** (`apps/dashboard/views.py`):
  - Wrapped in try/except with `logger.exception(...)` so every failure is logged with traceback.
  - Only signals with valid `symbol` and `signal_type` are passed to the template (avoids `AttributeError` when a related row was deleted).

After deploying, reproduce the 500 and then run the `journalctl` (or log file) command above to see the exact error and fix it.
