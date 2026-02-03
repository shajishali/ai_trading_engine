# Old signals on the page – what to do

## Why you still see old signals

- **Main signals page** is supposed to show only the **top 5 from the last hour** (or last 24h if fewer).
- If you still see many old signals, common causes:
  1. Updated frontend not deployed (page still loads all signals instead of `mode=top5`).
  2. Browser cache (old API response).
  3. Expired signals still marked `is_valid=True` until cleanup runs.

---

## Fix (do in order)

### 1. Deploy the updated dashboard

- Make sure the **updated** `frontend/templates/signals/dashboard.html` is on the server (the one that loads with `?mode=top5`).
- Restart the app / web server if needed.

### 2. Hard refresh the page

- **Ctrl+F5** (Windows/Linux) or **Cmd+Shift+R** (Mac) so the browser doesn’t use cached data.

### 3. Mark expired signals as invalid (no deletion)

Run on the server:

```bash
cd ~/trading-engine/backend && source venv/bin/activate && python manage.py shell -c "
from apps.signals.tasks import cleanup_expired_signals
cleanup_expired_signals()
print('Done.')
"
```

- Old signals past their expiry (or older than 48h if no expiry) will be set to `is_valid=False`.
- They stay in the DB but won’t show as “active” and won’t appear in the main top‑5 view.

### 4. Optional: delete old invalid signals from the DB

Only if you want to **remove** them from the database (e.g. to shorten History).  
Example: delete invalid signals older than **30 days**:

```bash
cd ~/trading-engine/backend && source venv/bin/activate && python manage.py shell -c "
from apps.signals.models import TradingSignal
from django.utils import timezone
from datetime import timedelta
cutoff = timezone.now() - timedelta(days=30)
deleted, _ = TradingSignal.objects.filter(is_valid=False, created_at__lt=cutoff).delete()
print(f'Deleted {deleted} old invalid signals.')
"
```

- Change `days=30` if you want a different cutoff.
- This does **not** run automatically; run it only when you want a one‑off cleanup.

---

## Do old signals “automatically go”?

- **From the main page:** Yes, once the updated code is deployed and you use the top‑5 logic. The main view only shows top 5 from the last hour (or last 24h), so old ones drop off as new signals are generated.
- **From the database:** No automatic deletion. The scheduled task only sets `is_valid=False` (step 3). To actually delete old rows, run the optional command in step 4 when you want.
