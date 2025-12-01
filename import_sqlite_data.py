#!/usr/bin/env python
"""Import data from SQLite export to MySQL"""
import os
import json
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_trading_engine.settings')
django.setup()

from django.db import connection, transaction
from django.core.management import call_command

# Path to exported data
export_file = Path("..") / "backups" / "sqlite_data_export.json"

if not export_file.exists():
    print(f"Error: {export_file} not found!")
    exit(1)

print("=" * 60)
print("Step 10: Import Data to MySQL")
print("=" * 60)
print()
print(f"Loading data from: {export_file}")
print(f"File size: {export_file.stat().st_size / (1024*1024):.2f} MB")
print()

try:
    # Load JSON data
    print("Loading JSON data...")
    with open(export_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Found {len(data)} tables to import")
    print()
    
    # Get table row counts
    total_rows = sum(len(rows) for rows in data.values())
    print(f"Total rows to import: {total_rows:,}")
    print()
    
    # Import data table by table
    cursor = connection.cursor()
    imported_count = 0
    failed_tables = []
    
    # Disable foreign key checks temporarily
    print("Disabling foreign key checks...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    # Import each table
    for table_name, rows in data.items():
        if not rows:
            print(f"  Skipping {table_name} (empty)")
            continue
        
        try:
            print(f"  Importing {table_name}... ({len(rows)} rows)", end=" ")
            
            # Build INSERT statements
            if rows:
                # Get column names from first row
                columns = list(rows[0].keys())
                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join([f"`{col}`" for col in columns])
                
                # Prepare values
                values_list = []
                for row in rows:
                    values = [row.get(col) for col in columns]
                    values_list.append(values)
                
                # Build INSERT query
                insert_query = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
                
                # Execute in batches to avoid memory issues
                batch_size = 1000
                for i in range(0, len(values_list), batch_size):
                    batch = values_list[i:i+batch_size]
                    cursor.executemany(insert_query, batch)
                
                imported_count += len(rows)
                print(f"✓ ({len(rows)} rows)")
                
        except Exception as e:
            print(f"✗ Error: {str(e)[:100]}")
            failed_tables.append((table_name, str(e)))
            # Continue with next table
    
    # Re-enable foreign key checks
    print()
    print("Re-enabling foreign key checks...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    
    connection.commit()
    cursor.close()
    
    print()
    print("=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"Total rows imported: {imported_count:,}")
    print(f"Tables processed: {len(data)}")
    if failed_tables:
        print(f"Failed tables: {len(failed_tables)}")
        for table, error in failed_tables[:5]:
            print(f"  - {table}: {error[:80]}")
    else:
        print("All tables imported successfully!")
    print("=" * 60)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)






