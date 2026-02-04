import sqlite3
import os
import json

db_path = "/home/snaken/visual-patrol/data/report/report.db"

if not os.path.exists(db_path):
    print(f"Database not found at: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print(f"{'ID':<4} | {'Start Time':<20} | {'Status':<10} | {'Model':<20} | {'Tokens (Total)'}")
print("-" * 80)

try:
    cursor.execute("SELECT * FROM patrol_runs ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    
    for row in rows:
        # Handle potential None values smoothly
        r_id = row['id']
        start = row['start_time'] if row['start_time'] else "N/A"
        status = row['status'] if row['status'] else "Unknown"
        model = row['model_id'] if row['model_id'] else "N/A"
        total_tokens = row['total_tokens'] if row['total_tokens'] is not None else "N/A"
        
        print(f"{r_id:<4} | {start:<20} | {status:<10} | {model:<20} | {total_tokens}")

except Exception as e:
    print(f"Error querying database: {e}")

conn.close()
