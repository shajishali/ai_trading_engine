#!/usr/bin/env python
"""Verify DataSource fix"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from apps.data.models import DataSource
from django.db.models import Count

print("=" * 60)
print("DataSource Verification")
print("=" * 60)
print()

# Check for duplicates
duplicates = DataSource.objects.values('name').annotate(
    count=Count('id')
).filter(count__gt=1)

if duplicates:
    print("✗ Found duplicates:")
    for dup in duplicates:
        print(f"  - {dup['name']}: {dup['count']} records")
else:
    print("✓ No duplicates found!")

print()
print("All DataSource records:")
for ds in DataSource.objects.all().order_by('name'):
    print(f"  {ds.id}: {ds.name} ({ds.source_type}) - Active: {ds.is_active}")

print()
print("=" * 60)
print("Verification complete!")
print("=" * 60)

