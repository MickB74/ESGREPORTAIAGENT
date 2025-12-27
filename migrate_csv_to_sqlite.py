#!/usr/bin/env python3
"""
Migration script to transfer data from verified_links.csv to SQLite database.
This script will:
1. Backup the existing CSV file
2. Read all records from CSV
3. Insert them into the new SQLite database
4. Verify the migration was successful
"""

import os
import shutil
import pandas as pd
from datetime import datetime
import db_handler

def migrate_csv_to_sqlite():
    csv_file = "verified_links.csv"
    
    print("=" * 60)
    print("CSV to SQLite Migration")
    print("=" * 60)
    
    # Check if CSV exists
    if not os.path.exists(csv_file):
        print(f"❌ {csv_file} not found. Nothing to migrate.")
        return
    
    # Create backup
    backup_file = f"verified_links_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print(f"\n📦 Creating backup: {backup_file}")
    shutil.copy2(csv_file, backup_file)
    print(f"✅ Backup created successfully")
    
    # Read CSV
    print(f"\n📖 Reading {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Found {len(df)} records")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return
    
    # Initialize database
    print(f"\n🗄️  Initializing SQLite database...")
    db_handler.init_db()
    print(f"✅ Database initialized: {db_handler.DB_FILE}")
    
    # Migrate records
    print(f"\n🔄 Migrating records...")
    success_count = 0
    error_count = 0
    
    for idx, row in df.iterrows():
        try:
            success, msg = db_handler.save_link(
                company=str(row.get('Company', 'Unknown')),
                title=str(row.get('Title', '')),
                url=str(row.get('URL', '')),
                label=str(row.get('Label', '')),
                description=str(row.get('Description', ''))
            )
            
            if success:
                success_count += 1
                print(f"  ✓ {idx + 1}/{len(df)}: {row.get('Title', 'Untitled')[:50]}")
            else:
                error_count += 1
                print(f"  ✗ {idx + 1}/{len(df)}: {msg}")
                
        except Exception as e:
            error_count += 1
            print(f"  ✗ {idx + 1}/{len(df)}: {e}")
    
    # Verify migration
    print(f"\n🔍 Verifying migration...")
    links, error = db_handler.get_all_links()
    
    if error:
        print(f"❌ Error verifying: {error}")
        return
    
    print(f"✅ Database now contains {len(links)} records")
    
    # Summary
    print(f"\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"CSV Records:        {len(df)}")
    print(f"Successfully Saved: {success_count}")
    print(f"Errors:             {error_count}")
    print(f"Database Total:     {len(links)}")
    
    # Stats
    stats = db_handler.get_stats()
    print(f"\nDatabase Stats:")
    print(f"  Total Links:       {stats['total_links']}")
    print(f"  Unique Companies:  {stats['unique_companies']}")
    
    if success_count == len(df):
        print(f"\n✅ Migration completed successfully!")
        print(f"📁 Backup saved as: {backup_file}")
        print(f"🗄️  Database file: {db_handler.DB_FILE}")
    else:
        print(f"\n⚠️  Migration completed with {error_count} errors")
        print(f"📁 Original CSV backup: {backup_file}")

if __name__ == "__main__":
    migrate_csv_to_sqlite()
