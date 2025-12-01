#!/usr/bin/env python
"""Export data from SQLite database"""
import sqlite3
import json
import sys
from pathlib import Path

# Path to SQLite database
sqlite_db = Path("db.sqlite3")
backup_dir = Path("..") / "backups"
backup_dir.mkdir(exist_ok=True)
output_file = backup_dir / "sqlite_data_export.json"

if not sqlite_db.exists():
    print(f"Error: {sqlite_db} not found!")
    sys.exit(1)

print(f"Connecting to SQLite database: {sqlite_db}")
print(f"Database size: {sqlite_db.stat().st_size / (1024*1024):.2f} MB")
print()

try:
    conn = sqlite3.connect(str(sqlite_db))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  - {table}: {count} rows")
    
    print()
    print("Exporting data...")
    
    # Export data from each table
    exported_data = {}
    total_rows = 0
    
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        # Convert rows to dictionaries
        table_data = []
        for row in rows:
            table_data.append(dict(row))
        
        exported_data[table] = table_data
        total_rows += len(table_data)
        print(f"  Exported {table}: {len(table_data)} rows")
    
    # Save to JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(exported_data, f, indent=2, default=str)
    
    conn.close()
    
    file_size = output_file.stat().st_size / (1024*1024)
    print()
    print("=" * 50)
    print("Export completed successfully!")
    print("=" * 50)
    print(f"Total tables: {len(tables)}")
    print(f"Total rows exported: {total_rows}")
    print(f"Output file: {output_file}")
    print(f"File size: {file_size:.2f} MB")
    print("=" * 50)
    
except Exception as e:
    print(f"Error exporting data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)






