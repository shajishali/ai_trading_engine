# Backfill signal_date and signal_hour from created_at for existing rows.
# Ensures "Best Signals by date" only returns signals for that calendar day.

from django.db import migrations


def backfill_signal_date_hour(apps, schema_editor):
    TradingSignal = apps.get_model('signals', 'TradingSignal')
    # Only rows where signal_date is null (legacy or pre-migration)
    qs = TradingSignal.objects.filter(signal_date__isnull=True)
    updated = 0
    for sig in qs.iterator(chunk_size=500):
        if sig.created_at:
            # Use date/hour of created_at (DB stores UTC when USE_TZ=True; .date() is then UTC date)
            sig.signal_date = sig.created_at.date()
            sig.signal_hour = sig.created_at.hour
            sig.save(update_fields=['signal_date', 'signal_hour'])
            updated += 1
    if updated:
        print(f"Backfilled signal_date/signal_hour for {updated} TradingSignal rows.")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0019_signal_date_hour_and_slot'),
    ]

    operations = [
        migrations.RunPython(backfill_signal_date_hour, noop_reverse),
    ]
