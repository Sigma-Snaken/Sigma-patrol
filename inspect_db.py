import sqlite3
import os
import sys

# Adjust path based on config.py we saw earlier
# method 1: hardcoded path based on what we saw
db_path = "/home/snaken/Sigma-patrol/data/report/report.db"

if not os.path.exists(db_path):
    print(f"Database not found at: {db_path}")
    sys.exit(1)

print(f"Inspecting Database: {db_path}\n")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("No tables found in the database.")
    
    for table_name in tables:
        t_name = table_name[0]
        if t_name == "sqlite_sequence": continue
        
        print(f"=== Table: {t_name} ===")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {t_name}")
        count = cursor.fetchone()[0]
        print(f"Total Rows: {count}")
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({t_name})")
        columns = [info[1] for info in cursor.fetchall()]
        print(f"Columns: {', '.join(columns)}")
        
        # Get last 3 rows
        print("Last 3 rows:")
        cursor.execute(f"SELECT * FROM {t_name} ORDER BY id DESC LIMIT 3")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
        print("-" * 30 + "\n")
        
    conn.close()

except Exception as e:
    print(f"Error reading database: {e}")
