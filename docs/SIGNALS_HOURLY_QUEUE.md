# Signal Generation Queue – Every Day

This is the **canonical flow** for hourly (or 4-hourly) signal generation. Keep this as the project queue.

---

## Schedule

- **Testing:** Every **1 hour** (Celery beat: `crontab(minute=0)`).
- **Production (optional):** Every **4 hours** (Celery beat: `crontab(minute=0, hour='*/4')`).

Task: `apps.signals.tasks.generate_signals_for_all_symbols`.

---

## Queue Steps (every run)

### Step 1 – Ignore coins that already generated signals (previous hours today)

- Before generating, **exclude** any coin that already has **at least one signal created today** (any hour).
- So: **one signal per coin per day**. Same coin does not appear again until the next day.
- Log: `[Signal Queue] Step 1 – Ignore coins with signal today/active: N symbols excluded. Examples: [BTC, SOL, ...]`

### Step 2 – Generate signals

- From the **remaining** coins (active, crypto, Binance-futures eligible, not excluded in Step 1), pick up to **5** at random.
- Generate signals for those 5 (or fewer if not enough eligible).
- Max **5 new signals per run**. Some runs may have fewer.
- Log: `[Signal Queue] Step 2 done – Generated N signals. Symbols: [SYM1, SYM2, ...]`

### Step 3 – Show best signals in the UI

- **Main signals page:** Shows the **top 5 signals from the last hour** (by quality + confidence). So the UI displays the best of what was just generated (or from the last 24h if fewer than 5 in the last hour).
- No extra “queue” step in code; the API `mode=top5` does this.

---

## Summary

| Step | Action |
|------|--------|
| 1 | Ignore coins that already have a signal **created today** (any previous hour). |
| 2 | Generate up to 5 new signals from the rest. |
| 3 | UI shows best 5 from last hour (main page). |

---

## Production checks

1. **Celery worker** must consume the `signals` queue:  
   `celery -A ai_trading_engine worker -Q default,signals ...`
2. **Celery beat** must be running so the task runs every hour (or every 4 hours).
3. In worker logs, look for `[Signal Queue]` to verify:
   - Step 1: how many symbols were excluded and examples.
   - Step 2: how many signals generated and which symbols.

If the **same** symbols keep appearing every hour, check:

- Worker is running the **latest** code (restart after deploy).
- Step 1 log: excluded count should include the symbols from the previous run (e.g. SIREN, SOL, 1INCH, GMX, CLANKER after the first run).
