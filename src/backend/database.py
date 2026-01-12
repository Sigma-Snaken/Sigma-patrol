import sqlite3
from config import DB_FILE

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patrol_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            status TEXT,
            robot_serial TEXT,
            report_content TEXT,
            model_id TEXT,
            token_usage TEXT,
            prompt_tokens INTEGER,
            candidate_tokens INTEGER,
            total_tokens INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspection_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            point_name TEXT,
            coordinate_x REAL,
            coordinate_y REAL,
            prompt TEXT,
            ai_response TEXT,
            is_ng INTEGER,
            ai_description TEXT,
            token_usage TEXT,
            prompt_tokens INTEGER,
            candidate_tokens INTEGER,
            total_tokens INTEGER,
            image_path TEXT,
            timestamp TEXT,
            FOREIGN KEY(run_id) REFERENCES patrol_runs(id)
        )
    ''')
    
    # Simple Migration Check
    try:
        cursor.execute("SELECT is_ng FROM inspection_results LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating Database: Adding new columns to inspection_results...")
        try:
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN is_ng INTEGER")
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN ai_description TEXT")
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN token_usage TEXT")
        except Exception as e:
            print(f"Migration warning (inspection_results): {e}")

    try:
        cursor.execute("SELECT prompt_tokens FROM inspection_results LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating Database: Adding token columns to inspection_results...")
        try:
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN prompt_tokens INTEGER")
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN candidate_tokens INTEGER")
            cursor.execute("ALTER TABLE inspection_results ADD COLUMN total_tokens INTEGER")
        except Exception as e:
            print(f"Migration warning (inspection_results tokens): {e}")

    try:
        cursor.execute("SELECT token_usage FROM patrol_runs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating Database: Adding token_usage to patrol_runs...")
        try:
            cursor.execute("ALTER TABLE patrol_runs ADD COLUMN token_usage TEXT")
        except Exception as e:
            print(f"Migration warning (patrol_runs): {e}")
            
    try:
        cursor.execute("SELECT prompt_tokens FROM patrol_runs LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating Database: Adding token columns to patrol_runs...")
        try:
            cursor.execute("ALTER TABLE patrol_runs ADD COLUMN prompt_tokens INTEGER")
            cursor.execute("ALTER TABLE patrol_runs ADD COLUMN candidate_tokens INTEGER")
            cursor.execute("ALTER TABLE patrol_runs ADD COLUMN total_tokens INTEGER")
        except Exception as e:
            print(f"Migration warning (patrol_runs tokens): {e}")

    conn.commit()
    conn.close()
