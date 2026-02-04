# Generated migration: signal_date, signal_hour on TradingSignal + SignalGenerationSlot
# Enforces: one coin per day (DB constraint), idempotent hourly generation (slot).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0018_add_daily_best_signals_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradingsignal',
            name='signal_date',
            field=models.DateField(blank=True, db_index=True, help_text='Calendar date (UTC) this signal was generated for', null=True),
        ),
        migrations.AddField(
            model_name='tradingsignal',
            name='signal_hour',
            field=models.IntegerField(blank=True, db_index=True, help_text='Hour of day (0-23 UTC) this signal was generated for', null=True),
        ),
        migrations.AddIndex(
            model_name='tradingsignal',
            index=models.Index(fields=['signal_date', 'signal_hour'], name='signals_tra_signal_6a0b0d_idx'),
        ),
        migrations.AddConstraint(
            model_name='tradingsignal',
            constraint=models.UniqueConstraint(condition=models.Q(('signal_date__isnull', False)), fields=('symbol', 'signal_date'), name='unique_symbol_per_signal_date'),
        ),
        migrations.CreateModel(
            name='SignalGenerationSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signal_date', models.DateField(db_index=True)),
                ('signal_hour', models.IntegerField()),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Signal Generation Slot',
                'verbose_name_plural': 'Signal Generation Slots',
            },
        ),
        migrations.AddConstraint(
            model_name='signalgenerationslot',
            constraint=models.UniqueConstraint(fields=('signal_date', 'signal_hour'), name='unique_signal_slot_date_hour'),
        ),
        migrations.AddIndex(
            model_name='signalgenerationslot',
            index=models.Index(fields=['signal_date', 'signal_hour'], name='signals_sig_signal_8c4e2a_idx'),
        ),
    ]
