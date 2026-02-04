# Signals Page – Lifecycle and Business Rules

## Overview

- **Hourly**: Every hour, exactly **5 signals** are generated and stored. Each has one **coin**, **signal_date**, **signal_hour** (0–23 UTC), and score. **24 × 5 = 120 unique coins per day**.
- **DB constraint**: `unique_symbol_per_signal_date` – one row per (symbol, signal_date) when signal_date is set (PostgreSQL; MySQL does not support partial unique constraints, so app logic enforces this).
- **Idempotency**: `SignalGenerationSlot` (date, hour, completed_at). Once a slot is completed, the task **never** regenerates for that hour.
- **Best Signals (date-based)**: User selects a date and sees the **top 10** for that date only (read-only; no generation; never mix dates).

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

## 2. Best Signals (Date-Based) – Read-Only

**When**: User selects a date and clicks “Best Signals”.

**Rules**:

1. **Only that date**: Return only signals whose `created_at` falls on the selected date. **Never** mix signals from other dates.
2. **No generation**: Do not create or recalculate signals. Only read from existing hourly-generated signals for that date.
3. **Past dates**: Use stored `is_best_of_day=True` and `best_of_day_date=target_date`, and **also** filter by `created_at` on that date so no cross-date leakage.
4. **Today**: Take the top 10 by quality from all signals with `created_at` on today (the hourly pool). No new generation.

**Implementation**: `DailyBestSignalsView` in `apps.signals.views`

- Past: `best_of_day_date=target_date`, `is_best_of_day=True`, and `created_at` in [start_dt, end_dt] for that date.
- Today: filter `created_at` on that date, order by quality/confidence, take first 10 (one per symbol+type).

---

## 3. Frontend State

- **View mode**: `hourly` (default) or `best_by_date`.
- **Hourly**: Table shows top 5 from current hour (API `mode=top5`). Auto-refresh (e.g. every 30s) may update the table.
- **Best by date**: Table shows top 10 for the selected date. Auto-refresh must **not** overwrite this view; when `currentViewMode === 'best_by_date'`, the result of `loadSignals()` is ignored for updating the table.
- **Reset**: “Reset filters” sets view back to `hourly` and reloads top 5 from the API.

**Implementation**: `frontend/templates/signals/dashboard.html`

- `currentViewMode`, `selectedBestDate`.
- In `loadSignals()` response handler: if `currentViewMode !== 'hourly'`, return without updating table.
- In `showBestSignals()`: set `currentViewMode = 'best_by_date'`, `selectedBestDate = targetDate`.
- In `resetFilters()`: set `currentViewMode = 'hourly'`, then `loadSignals()`.

---

## 4. Edge Cases and Validation

| Case | Rule / Handling |
|------|------------------|
| No eligible coins left today | Hourly task returns 0 signals; no DB writes. |
| Fewer than 5 candidates in an hour | Only that many signals are kept valid (e.g. 3). |
| Best Signals for a date with no signals | API returns empty list; UI shows “No signals” and stays in best_by_date view. |
| Best Signals for “today” before any run | Empty or partial list from today’s `created_at` only. |
| Duplicate symbol+type in same hour | Backend duplicate cleanup keeps latest per symbol+type. |
| Timezone | All times UTC; `signal_date` / `signal_hour` and `created_at` use timezone.now(). |
| Concurrency | Slot row locked with select_for_update(); only one worker can complete a given (date, hour). |
| Save daily best | `save_daily_best_signals_task` at 23:55 marks top 10 for that day (from signals with signal_date or created_at on that date). |

---

## 5. API Summary

| Endpoint | Purpose |
|----------|--------|
| `GET /signals/api/signals/?mode=top5` | Top 5 signals for the **current clock hour** (and same day). Fetched from DB only. |
| `GET /signals/api/daily-best-signals/?date=YYYY-MM-DD` | Top 10 signals for the given date. Read-only; no generation; date-strict. |
| `GET /signals/api/available-dates/` | Dates that have saved best-of-day data. |

---

## 6. Determinism and Scale

- **Deterministic**: For a given hour and set of eligible symbols, the same “best 5” logic applies (sort by score, take top 5). Symbol order is randomized (`order_by('?')`) so which 50 are tried may vary, but the selection from candidates is deterministic.
- **Scale**: Hourly run is capped at 50 candidate symbols per run to keep duration bounded. For more coverage, increase `max_candidates_to_try` in the task if needed.
