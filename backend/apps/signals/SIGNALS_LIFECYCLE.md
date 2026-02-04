# Signals Page – Lifecycle and Business Rules

## Overview

- **Hourly**: Every hour, exactly **5 signals** are generated and stored. Each has one **coin**, **signal_date**, **signal_hour** (0–23 UTC), and score. **24 × 5 = 120 unique coins per day**.
- **DB constraint**: `unique_symbol_per_signal_date` – one row per (symbol, signal_date) when signal_date is set (PostgreSQL; MySQL does not support partial unique constraints, so app logic enforces this).
- **Idempotency**: `SignalGenerationSlot` (date, hour, completed_at). Once a slot is completed, the task **never** regenerates for that hour.

---

## 1. Hourly Signal Generation

**When**: Celery beat runs `generate_signals_for_all_symbols` every hour (e.g. at :00 UTC).

**Rules**:

1. **Slot lock**: Get or create `SignalGenerationSlot(signal_date=today, signal_hour=current_hour)`. If `completed_at` is set, **return immediately** (never regenerate for that hour).
2. **Daily uniqueness**: Exclude all coins that already have a signal on today (`signal_date=today` or `created_at.date()=today`). Only consider coins that have **not** appeared that day.
3. **Candidates**: From remaining coins (up to 50 per run), generate candidates; rank by score; select **top 5**.
4. **Persist**: Set `signal_date=today`, `signal_hour=current_hour` on the 5; invalidate the rest. Mark slot `completed_at=now()`. On `IntegrityError` (duplicate symbol/date), do not mark completed and invalidate the 5.

**Implementation**: `apps.signals.tasks.generate_signals_for_all_symbols`

- Uses `_symbol_ids_with_signal_on_date(today)` to exclude symbols (uses signal_date or created_at.date).
- Builds (score, signal) from eligible symbols, sorts, takes top 5, sets signal_date/signal_hour, marks slot completed.

---

## 2. Frontend State

- Table shows top 5 from current hour (API `mode=top5`). Auto-refresh (e.g. every 30s) may update the table.
- "Reset filters" clears symbol/timeframe filters and reloads top 5 from the API.

---

## 3. Edge Cases and Validation

| Case | Rule / Handling |
|------|------------------|
| No eligible coins left today | Hourly task returns 0 signals; no DB writes. |
| Fewer than 5 candidates in an hour | Only that many signals are kept valid (e.g. 3). |
| Duplicate symbol+type in same hour | Backend duplicate cleanup keeps latest per symbol+type. |
| Timezone | All times UTC; `signal_date` / `signal_hour` and `created_at` use timezone.now(). |
| Concurrency | Slot row locked with select_for_update(); only one worker can complete a given (date, hour). |

---

## 4. API Summary

| Endpoint | Purpose |
|----------|--------|
| `GET /signals/api/signals/?mode=top5` | Top 5 signals for the **current clock hour** (and same day). Fetched from DB only. |

---

## 5. Determinism and Scale

- **Deterministic**: For a given hour and set of eligible symbols, the same "best 5" logic applies (sort by score, take top 5). Symbol order is randomized (`order_by('?')`) so which 50 are tried may vary, but the selection from candidates is deterministic.
- **Scale**: Hourly run is capped at 50 candidate symbols per run to keep duration bounded. For more coverage, increase `max_candidates_to_try` in the task if needed.
